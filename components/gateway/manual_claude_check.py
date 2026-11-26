"""Offline CLI compatibility check using the shared synthetic fixtures."""

import asyncio
import logging
import secrets
import shutil
import sys
import tempfile
import time
from pathlib import Path

import certifi
import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

import broker
import gateway
from foundation import public_jwk
from lab_fixtures import Client, reply, routes

LOG = logging.getLogger("uvicorn.error")


async def check(claude):
    print("Using offline signing metadata and synthetic Converse responses", flush=True)
    proof = broker.ProofClient()
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = public_jwk(key.public_key())
    now = int(time.time())
    token = jwt.encode({
        "iss": gateway.ISSUER, "aud": gateway.TARGET, "sub": "synthetic-cli-check",
        "client_id": gateway.CLIENT, "scope": gateway.SCOPE,
        "iat": now, "exp": now + 120, "jti": secrets.token_urlsafe(24),
        "cnf": {"jkt": proof.jkt},
    }, key, algorithm="RS256", headers={"typ": "at+jwt", "kid": jwk["kid"]})

    def trust(request):
        if str(request.url) == gateway.DISCOVERY:
            return reply({"issuer": gateway.ISSUER, "jwks_uri": gateway.JWKS,
                          "dpop_signing_alg_values_supported": ["ES256"]})
        assert str(request.url) == gateway.JWKS
        return reply({"keys": [jwk]})

    calls = []

    def sdk(region):
        fixture = Client()
        calls.append(fixture)
        return fixture

    with tempfile.TemporaryDirectory(prefix="offline-claude-") as directory:
        directory = Path(directory)
        directory.chmod(0o700)
        nonce = directory / "nonce.key"
        nonce.write_bytes(secrets.token_bytes(32))
        nonce.chmod(0o600)
        app = gateway.create_app(
            certifi.where(), "", trust_transport=httpx.MockTransport(trust),
            dpop_nonce_key=nonce, dpop_replay_dir=directory,
            bedrock_routes=routes(), bedrock_client_factory=sdk,
        )
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                         trust_env=False) as upstream:
                async with asyncio.timeout(15):
                    code = await broker.launch(claude, "lab-claude-text",
                                               broker.Session(token, proof, now + 120),
                                               upstream, text_only=True)
                if code != 0 or not any(client.calls for client in calls):
                    raise ValueError("CLI did not complete a supported Converse invocation")
    print("Offline Claude Code adapter check passed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    try:
        executable = shutil.which("claude")
        if executable is None:
            raise ValueError("Claude Code unavailable")
        asyncio.run(check(executable))
    except (ValueError, OSError, TimeoutError):
        print("Offline Claude Code adapter check incomplete", file=sys.stderr)
        raise SystemExit(1)
