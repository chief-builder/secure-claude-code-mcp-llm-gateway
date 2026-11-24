"""Read-only HTTPS authorization-server foundation for the synthetic lab."""

import argparse
import asyncio
import ssl
import time
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from dpop import Verifier, nonce_key
from exchange import Exchange, GRANT, signing_keys, token_endpoint
from foundation import (
    DISCOVERY, ISSUER, MAX_BYTES, UPSTREAM, UPSTREAM_JWKS, FoundationError,
    checked_rsa_keys, load_local, provision, read_object,
)

POLICY_PATH = Path(__file__).with_name("policy.json")
TRUST_TTL = 60
RETRY_DELAY = 5


class UpstreamTrust:
    def __init__(self, client, excluded_keys):
        self.client = client
        self.excluded_keys = excluded_keys
        self.valid_until = 0
        self.retry_after = 0
        self.refresh_after = 0
        self.keys = {}
        self.lock = asyncio.Lock()

    async def fetch(self, url):
        async with self.client.stream("GET", url, headers={"Accept-Encoding": "identity"}) as response:
            response.raise_for_status()
            if response.headers.get("content-encoding", "identity") != "identity":
                raise FoundationError("Unexpected upstream content encoding")
            body = bytearray()
            async for chunk in response.aiter_raw(chunk_size=8192):
                body.extend(chunk)
                if len(body) > MAX_BYTES:
                    raise FoundationError("Oversized upstream response")
        return read_object(body)

    async def ready(self, kid=None):
        async with self.lock:
            now = time.monotonic()
            if now < self.valid_until and (kid is None or kid in self.keys or now < self.refresh_after):
                return True
            if now < self.retry_after:
                return False
            try:
                async with asyncio.timeout(5):
                    discovery = await self.fetch(DISCOVERY)
                    if discovery.get("issuer") != UPSTREAM or discovery.get("jwks_uri") != UPSTREAM_JWKS:
                        raise FoundationError("Upstream metadata does not match pins")
                    document = await self.fetch(UPSTREAM_JWKS)
                    keys = checked_rsa_keys(document)
                    if keys & self.excluded_keys:
                        raise FoundationError("Upstream key overlaps lab signing material")
                    self.keys = signing_keys(document)
            except (httpx.HTTPError, FoundationError, TimeoutError):
                self.valid_until = 0
                self.retry_after = time.monotonic() + RETRY_DELAY
                return False
            self.refresh_after = time.monotonic() + RETRY_DELAY
            self.valid_until = time.monotonic() + TRUST_TTL
            return True


def create_app(key_dir, upstream_ca, policy_path=POLICY_PATH, *, exchange_policy=None, dpop_nonce_key=None, transport=None):
    if dpop_nonce_key is not None and exchange_policy is None:
        raise ValueError("DPoP requires an exchange policy")

    @asynccontextmanager
    async def lifespan(app):
        try:
            local = load_local(key_dir, exchange_policy or policy_path, exchange=exchange_policy is not None)
            jwk, client_keys = local[:2]
            tls = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            tls.load_verify_locations(cafile=upstream_ca)
        except (OSError, FoundationError):
            raise RuntimeError("2B local key, CA, or policy configuration invalid") from None
        async with httpx.AsyncClient(
            verify=tls, follow_redirects=False, trust_env=False, timeout=3, transport=transport,
        ) as client:
            trust = UpstreamTrust(client, {jwk["kid"], *client_keys})
            if not await trust.ready():
                raise RuntimeError("2B pinned upstream trust unavailable") from None
            app.state.jwk = jwk
            app.state.trust = trust
            if exchange_policy is not None:
                verifier = None
                if dpop_nonce_key is not None:
                    verifier = Verifier(ISSUER + "/token", nonce_key(dpop_nonce_key))
                app.state.exchange = Exchange(exchange_policy, key_dir, local[2], jwk, local[3], trust,
                                              verifier=verifier)
            yield

    app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None,
                  redirect_slashes=False, lifespan=lifespan)

    if exchange_policy is not None:
        app.post("/token")(token_endpoint)

    def unavailable():
        return JSONResponse({"detail": "Service unavailable"}, status_code=503,
                            headers={"Cache-Control": "no-store"})

    exchange_metadata = {} if exchange_policy is None else {
        "token_endpoint": ISSUER + "/token",
        "token_endpoint_auth_methods_supported": ["private_key_jwt"],
        "token_endpoint_auth_signing_alg_values_supported": ["RS256"],
    }

    if dpop_nonce_key is not None:
        exchange_metadata["dpop_signing_alg_values_supported"] = ["ES256"]

    @app.get("/.well-known/oauth-authorization-server")
    async def metadata():
        if not await app.state.trust.ready():
            return unavailable()
        return JSONResponse({
            "issuer": ISSUER,
            "jwks_uri": ISSUER + "/jwks",
            "response_types_supported": [],
            "grant_types_supported": [GRANT] if exchange_policy is not None else [],
            **exchange_metadata,
        }, headers={"Cache-Control": "no-store"})

    @app.get("/jwks")
    async def jwks():
        if not await app.state.trust.ready():
            return unavailable()
        return JSONResponse({"keys": [app.state.jwk]}, headers={"Cache-Control": "no-store"})

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init-keys")
    init.add_argument("key_dir", type=Path)
    serve = commands.add_parser("serve")
    serve.add_argument("--key-dir", type=Path, required=True)
    serve.add_argument("--exchange-policy", type=Path)
    serve.add_argument("--dpop-nonce-key", type=Path, help="Enable required DPoP for token exchange")
    serve.add_argument("--upstream-ca", type=Path, required=True)
    serve.add_argument("--tls-cert", type=Path, required=True)
    serve.add_argument("--tls-key", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "init-keys":
        try:
            provision(args.key_dir)
        except OSError:
            parser.exit(1, "Could not provision keys in the requested new directory\n")
        return
    if args.dpop_nonce_key is not None and args.exchange_policy is None:
        parser.error("--dpop-nonce-key requires --exchange-policy")
    app = create_app(args.key_dir, args.upstream_ca, exchange_policy=args.exchange_policy,
                     dpop_nonce_key=args.dpop_nonce_key)
    uvicorn.run(app, host="127.0.0.1", port=8081,
                ssl_certfile=str(args.tls_cert), ssl_keyfile=str(args.tls_key),
                access_log=False, proxy_headers=False)


if __name__ == "__main__":
    main()
