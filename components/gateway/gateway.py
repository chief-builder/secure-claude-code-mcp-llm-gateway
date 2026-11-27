"""Loopback inference gateway for the synthetic lab."""

import argparse
import asyncio
import json
import logging
import os
import re
import sqlite3
import ssl
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import jwt
import uvicorn
from fastapi import FastAPI, Request
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect
from starlette.responses import JSONResponse, Response, StreamingResponse

# The issuer and the verifier share the lab's strict JWT and JWKS parsing.
from dpop import InvalidProof, NonceRequired, Verifier, nonce_key, valid_thumbprint
from exchange import CLIENT, SCOPE, TARGET, ReplayStore, digest, signing_keys, token_parts, verify
from foundation import ISSUER, MAX_BYTES, FoundationError, checked_rsa_keys, read_object, unique_fields

DISCOVERY = ISSUER + "/.well-known/oauth-authorization-server"
JWKS = ISSUER + "/jwks"
MOCK = "http://127.0.0.1:8765/v1/messages"
BODY_LIMIT = RESPONSE_LIMIT = 1024 * 1024
AUTH_LIMIT = 16 * 1024
DEADLINE = 60
TRUST_TTL = 60
REFRESH_INTERVAL = 5
LOG = logging.getLogger("uvicorn.error")
GATEWAY_REPLAY_DATABASE = "llm-gateway-request-proof-replay.sqlite3"

ERRORS = {
    400: ("invalid_request_error", "Invalid request"),
    401: ("authentication_error", "Authentication required"),
    403: ("permission_error", "Invocation denied"),
    413: ("request_too_large", "Request body too large"),
    415: ("invalid_request_error", "Unsupported media type or encoding"),
    429: ("rate_limit_error", "Inference capacity or provider rate limit reached"),
    431: ("invalid_request_error", "Authorization field too large"),
    502: ("api_error", "Invalid or unavailable inference upstream"),
    503: ("api_error", "Authorization service unavailable"),
    504: ("api_error", "Inference upstream timed out"),
}


class Failure(Exception):
    def __init__(self, status, event, challenge=None, nonce=None):
        self.status = status
        self.event = event
        self.challenge = challenge
        self.nonce = nonce


def audit(event, request_id):
    LOG.info("gateway event=%s request_id=%s", event, request_id)


def error_response(failure, request_id):
    kind, message = ERRORS[failure.status]
    headers = {"request-id": request_id, "cache-control": "no-store"}
    if failure.challenge:
        headers["www-authenticate"] = failure.challenge
    if failure.nonce is not None:
        headers["dpop-nonce"] = failure.nonce
    return JSONResponse({"type": "error", "error": {"type": kind, "message": message},
                         "request_id": request_id}, failure.status, headers)


class Trust:
    def __init__(self, client, *, dpop=False):
        self.dpop = dpop
        self.client = client
        self.keys = {}
        self.valid_until = 0
        self.refresh_after = 0
        self.lock = asyncio.Lock()

    async def fetch(self, url):
        async with self.client.stream("GET", url, headers={"accept-encoding": "identity"}) as response:
            response.raise_for_status()
            if response.headers.get("content-encoding", "identity") != "identity":
                raise FoundationError("Unsupported trust encoding")
            body = bytearray()
            async for chunk in response.aiter_raw():
                if len(body) + len(chunk) > MAX_BYTES:
                    raise FoundationError("Oversized trust response")
                body.extend(chunk)
            return read_object(body)

    async def key(self, kid):
        async with self.lock:
            now = time.monotonic()
            if now >= self.refresh_after and (now >= self.valid_until or kid not in self.keys):
                try:
                    async with asyncio.timeout(5):
                        metadata = await self.fetch(DISCOVERY)
                        if metadata.get("issuer") != ISSUER or metadata.get("jwks_uri") != JWKS:
                            raise FoundationError("Metadata violates configured pins")
                        algorithms = metadata.get("dpop_signing_alg_values_supported")
                        if algorithms != (["ES256"] if self.dpop else None):
                            raise FoundationError("Authorization server profile does not match gateway")
                        jwks = await self.fetch(JWKS)
                        checked_rsa_keys(jwks)
                        self.keys = signing_keys(jwks)
                    self.valid_until = time.monotonic() + TRUST_TTL
                except (httpx.HTTPError, FoundationError, TimeoutError):
                    # A previously validated cache may serve known keys up to its original expiry.
                    pass
                finally:
                    self.refresh_after = time.monotonic() + REFRESH_INTERVAL
            if time.monotonic() >= self.valid_until:
                raise Failure(503, "trust_unavailable")
            return self.keys.get(kid)


def access_credential(request, scheme):
    values = request.headers.getlist("authorization")
    if any(len(value) > AUTH_LIMIT for value in values):
        raise Failure(431, "header_too_large")
    if (len(values) > 1 or (values and "," in values[0])
            or "cookie" in request.headers or "x-api-key" in request.headers
            or "access_token" in request.query_params):
        raise Failure(400, "ambiguous_credentials", f'{scheme} error="invalid_request"')
    if not values:
        raise Failure(401, "authentication_failed", scheme)
    match = re.fullmatch(rf"{scheme} +([A-Za-z0-9_.-]+)", values[0], re.IGNORECASE | re.ASCII)
    if match is None:
        raise Failure(401, "authentication_failed", f'{scheme} error="invalid_token"')
    return match[1]


async def validate_access_token(token, trust, scheme, audience=TARGET):
    invalid = Failure(401, "authentication_failed", f'{scheme} error="invalid_token"')
    try:
        header, claims = token_parts(token)
        if header.get("typ") != "at+jwt":
            raise ValueError
        key = await trust.key(header["kid"])
        if key is None:
            raise ValueError
        verify(token, key)
        issued, expiry = claims.get("iat"), claims.get("exp")
        now = time.time()
        if (claims.get("iss") != ISSUER or claims.get("aud") != audience
                or not all(isinstance(claims.get(name), str) and claims[name].strip()
                           for name in ("sub", "jti"))
                or type(issued) is not int or type(expiry) is not int
                or not 0 < expiry - issued <= 300 or issued > now + 5 or now >= expiry
                or "nbf" in claims):
            raise ValueError
        binding = claims.get("cnf")
        if scheme == "DPoP":
            if not isinstance(binding, dict) or set(binding) != {"jkt"} or not valid_thumbprint(binding["jkt"]):
                raise ValueError
        elif "cnf" in claims:
            raise ValueError
    except (ValueError, jwt.PyJWTError):
        raise invalid from None
    return claims


def enforce_policy(claims, scheme, scope=SCOPE):
    if claims.get("client_id") != CLIENT:
        raise Failure(403, "policy_denied")
    if claims.get("scope") != scope:
        raise Failure(403, "policy_denied", f'{scheme} error="insufficient_scope", scope="{scope}"')


def proof_failure():
    return Failure(401, "dpop_rejected", 'DPoP error="invalid_dpop_proof"')


def record_proof(store, proof, expiry):
    def check_time(now):
        proof.check_time(now)
        if time.time() >= expiry:
            raise Failure(401, "authentication_failed", 'DPoP error="invalid_token"')

    store.reserve(digest("dpop-gateway", proof.jkt, proof.jti), proof.replay_until,
                  InvalidProof(), check_time)


def reject_constant(_):
    raise ValueError("Non-JSON numeric constant")


def strict_json(body):
    result = json.loads(body.decode("utf-8"), object_pairs_hook=unique_fields,
                        parse_constant=reject_constant)
    if not isinstance(result, dict):
        raise ValueError("Expected a JSON object")
    return result


async def read_messages(request):
    content_types = request.headers.getlist("content-type")
    encodings = request.headers.getlist("content-encoding")
    if (len(content_types) != 1 or content_types[0].split(";", 1)[0].strip().lower() != "application/json"
            or (encodings and [value.lower() for value in encodings] != ["identity"])):
        raise Failure(415, "unsupported_media")
    if request.url.query not in ("", "beta=true"):
        raise Failure(400, "invalid_query")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > BODY_LIMIT:
            raise Failure(413, "body_too_large")
        body.extend(chunk)
    try:
        data = strict_json(body)
    except (FoundationError, ValueError, RecursionError):
        raise Failure(400, "invalid_json") from None
    if ("access_token" in data or "api_key" in data
            or type(data.get("stream", False)) is not bool):
        raise Failure(400, "invalid_body")
    return bytes(body), data.get("stream", False)


async def bounded_bytes(upstream):
    size = 0
    async for chunk in upstream.aiter_raw():
        size += len(chunk)
        if size > RESPONSE_LIMIT:
            raise Failure(502, "mock_response_too_large")
        yield chunk


class Invocation(Response):
    """Own the upstream connection until the response or disconnect completes."""

    upstream_name = "mock"

    def __init__(self, client, credential, body, stream, query, request_id):
        super().__init__()
        self.client = client
        self.credential = credential
        self.body = body
        self.stream = stream
        self.query = query
        self.request_id = request_id

    async def __call__(self, scope, receive, send):
        started = False
        event = "invocation_succeeded"

        async def track_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        async def fail(failure):
            if not started:
                await error_response(failure, self.request_id)(scope, receive, send)
                return
            # Headers are already sent, so tell a streaming client the response is incomplete.
            # The blank line ends any event the upstream left unfinished.
            body = b""
            if self.stream:
                kind, message = ERRORS[failure.status]
                body = b"\n\nevent: error\ndata: " + json.dumps(
                    {"type": "error", "error": {"type": kind, "message": message}}).encode() + b"\n\n"
            await send({"type": "http.response.body", "body": body, "more_body": False})

        async def forward():
            nonlocal event
            try:
                async with asyncio.timeout(DEADLINE):
                    await self.forward(scope, receive, track_send)
            except Failure as failure:
                event = failure.event
                await fail(failure)
            except (TimeoutError, httpx.HTTPError) as exc:
                status = 504 if isinstance(exc, (TimeoutError, httpx.TimeoutException)) else 502
                event = f"{self.upstream_name}_timeout" if status == 504 else f"{self.upstream_name}_failed"
                await fail(Failure(status, event))

        async def wait_disconnect():
            while (await receive())["type"] != "http.disconnect":
                pass

        work = asyncio.create_task(forward())
        disconnect = asyncio.create_task(wait_disconnect())
        try:
            done, _ = await asyncio.wait({work, disconnect}, return_when=asyncio.FIRST_COMPLETED)
            if work in done:
                await work
            else:
                event = "client_disconnected"
        except (asyncio.CancelledError, OSError):
            event = "client_disconnected"
            raise
        finally:
            for task in (work, disconnect):
                task.cancel()
            await asyncio.gather(work, disconnect, return_exceptions=True)
            self.report(event)

    def report(self, event):
        audit(event, self.request_id)

    async def open_upstream(self, media):
        headers = {"authorization": f"Bearer {self.credential}", "content-type": "application/json",
                   "accept": media, "accept-encoding": "identity"}
        url = MOCK + ("?beta=true" if self.query else "")
        request = httpx.Request("POST", url, headers=headers, content=self.body)
        return await self.client.send(request, stream=True)

    async def forward(self, scope, receive, send):
        media = "text/event-stream" if self.stream else "application/json"
        upstream = await self.open_upstream(media)
        try:
            if (upstream.status_code != 200
                    or upstream.headers.get("content-type", "").split(";", 1)[0].strip().lower() != media
                    or upstream.headers.get("content-encoding", "identity").lower() != "identity"):
                raise Failure(502, f"invalid_{self.upstream_name}_response")
            outgoing = {"request-id": self.request_id, "cache-control": "no-store"}
            if self.stream:
                response = StreamingResponse(bounded_bytes(upstream), media_type=media, headers=outgoing)
                await response.stream_response(send)
            else:
                body = b"".join([chunk async for chunk in bounded_bytes(upstream)])
                try:
                    strict_json(body)
                except (FoundationError, ValueError, RecursionError):
                    raise Failure(502, f"invalid_{self.upstream_name}_response") from None
                await Response(body, media_type=media, headers=outgoing)(scope, receive, send)
        finally:
            await upstream.aclose()


class BedrockInvocation(Invocation):
    upstream_name = "bedrock"

    async def open_upstream(self, media):
        request = httpx.Request("POST", MOCK, content=self.body,
                                headers={"x-gateway-request-id": self.request_id})
        response = await self.client.send(request, stream=True)
        if response.status_code != 200:
            status = response.status_code if response.status_code in (400, 413, 429, 503, 504) else 502
            await response.aclose()
            raise Failure(status, "bedrock_rejected")
        return response


def create_app(as_ca, mock_credential, *, trust_transport=None, mock_transport=None,
               dpop_nonce_key=None, dpop_replay_dir=None, bedrock_routes=None, bedrock_client_factory=None):
    if bedrock_routes is None and not re.fullmatch(r"[A-Za-z0-9_-]{22,128}", mock_credential):
        raise ValueError("Set a separate disposable gateway mock credential")
    if (dpop_nonce_key is None) != (dpop_replay_dir is None):
        raise ValueError("DPoP requires a nonce key and replay directory")
    dpop = dpop_nonce_key is not None
    scheme = "DPoP" if dpop else "Bearer"
    adapter = None
    if bedrock_routes is not None:
        from bedrock import BedrockTransport
        if not dpop:
            raise ValueError("Bedrock profile requires DPoP")
        options = {} if bedrock_client_factory is None else {"client_factory": bedrock_client_factory}
        adapter = BedrockTransport(bedrock_routes, **options)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    tls.load_verify_locations(cafile=as_ca)

    @asynccontextmanager
    async def lifespan(app):
        async with (
            httpx.AsyncClient(verify=tls, trust_env=False, follow_redirects=False,
                              timeout=3, transport=trust_transport) as authority,
            httpx.AsyncClient(trust_env=False, follow_redirects=False,
                              timeout=httpx.Timeout(15, connect=2), transport=adapter or mock_transport) as mock,
        ):
            if dpop:
                app.state.verifier = Verifier("https://127.0.0.1:8082/v1/messages",
                                              nonce_key(dpop_nonce_key))
                app.state.replay = ReplayStore(dpop_replay_dir, GATEWAY_REPLAY_DATABASE)
            app.state.trust = Trust(authority, dpop=dpop)
            app.state.mock = mock
            yield

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None,
                  redirect_slashes=False)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/v1/messages")
    async def messages(request: Request):
        request_id = uuid.uuid4().hex
        try:
            token = access_credential(request, scheme)
            claims = await validate_access_token(token, app.state.trust, scheme)
            proof_headers = request.headers.getlist("dpop")
            proof = None
            if dpop:
                if request.scope["scheme"] != "https":
                    raise InvalidProof
                proof = app.state.verifier.validate(proof_headers, token=token,
                                                     binding=claims["cnf"]["jkt"])
            elif proof_headers:
                raise Failure(400, "ambiguous_credentials", 'Bearer error="invalid_request"')
            enforce_policy(claims, scheme)
            body, stream = await read_messages(request)
            if adapter is not None:
                from bedrock import AdapterError, prepare
                try:
                    prepare(body, adapter.routes)
                except AdapterError as error:
                    raise Failure(error.status, "bedrock_request_rejected") from None
            if proof is not None:
                await run_in_threadpool(record_proof, app.state.replay, proof, claims["exp"])
        except Failure as failure:
            audit(failure.event, request_id)
            return error_response(failure, request_id)
        except NonceRequired as challenge:
            audit("dpop_nonce_required", request_id)
            return error_response(Failure(401, "dpop_nonce_required", 'DPoP error="use_dpop_nonce"',
                                          challenge.nonce), request_id)
        except InvalidProof:
            failure = proof_failure()
            audit(failure.event, request_id)
            return error_response(failure, request_id)
        except (FoundationError, sqlite3.Error, OSError):
            audit("replay_unavailable", request_id)
            return error_response(Failure(503, "replay_unavailable"), request_id)
        except ClientDisconnect:
            audit("client_disconnected", request_id)
            return Response(status_code=400)
        invocation = BedrockInvocation if adapter is not None else Invocation
        return invocation(app.state.mock, mock_credential, body, stream,
                          request.url.query, request_id)

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-ca", required=True)
    parser.add_argument("--tls-cert", required=True)
    parser.add_argument("--tls-key", required=True)
    parser.add_argument("--dpop-nonce-key", type=Path)
    parser.add_argument("--dpop-replay-dir", type=Path)
    parser.add_argument("--backend", choices=("mock", "bedrock"), default="mock")
    parser.add_argument("--bedrock-routes", type=Path)
    args = parser.parse_args()
    if (args.backend == "bedrock") != (args.bedrock_routes is not None):
        parser.error("Select bedrock with --bedrock-routes, or mock without it")
    try:
        routes = None
        if args.bedrock_routes is not None:
            from bedrock import load_routes
            routes = load_routes(args.bedrock_routes)
        app = create_app(args.as_ca, os.environ.get("GATEWAY_MOCK_TOKEN", ""),
                         dpop_nonce_key=args.dpop_nonce_key, dpop_replay_dir=args.dpop_replay_dir, bedrock_routes=routes)
    except (OSError, ValueError, FoundationError):
        parser.exit(1, "Gateway CA or disposable mock credential configuration invalid\n")
    uvicorn.run(app, host="127.0.0.1", port=8082, ssl_certfile=args.tls_cert,
                ssl_keyfile=args.tls_key, proxy_headers=False, access_log=False)


if __name__ == "__main__":
    main()
