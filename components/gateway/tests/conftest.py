import asyncio
import secrets
import time

import certifi
import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

import gateway
from foundation import public_jwk
from lab_fixtures import MOCK_SECRET, Bytes, reply


@pytest.fixture
def lab():
    class Lab:
        def __init__(self):
            self.rotate()
            self.trust_calls = []
            self.mock_calls = []
            self.trust_response = None
            self.mock_response = None
            self.app = gateway.create_app(
                certifi.where(), MOCK_SECRET, trust_transport=httpx.MockTransport(self.trust),
                mock_transport=httpx.MockTransport(self.mock),
            )

        def enable_dpop(self, directory):
            path = directory / "nonce.key"
            if not path.exists():
                path.write_bytes(secrets.token_bytes(32))
                path.chmod(0o600)
            directory.chmod(0o700)
            self.app = gateway.create_app(
                certifi.where(), MOCK_SECRET, trust_transport=httpx.MockTransport(self.trust),
                mock_transport=httpx.MockTransport(self.mock), dpop_nonce_key=path,
                dpop_replay_dir=directory,
            )

        def rotate(self):
            self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            self.jwk = public_jwk(self.key.public_key())

        def token(self, header=None, **claims):
            now = int(time.time())
            return jwt.encode(
                {"iss": gateway.ISSUER, "aud": gateway.TARGET, "sub": "synthetic",
                 "jti": "synthetic-jti", "iat": now, "exp": now + 120,
                 "client_id": gateway.CLIENT, "scope": gateway.SCOPE, **claims},
                self.key, algorithm="RS256",
                headers={"typ": "at+jwt", "kid": self.jwk["kid"], **(header or {})},
            )

        def trust(self, request):
            self.trust_calls.append(str(request.url))
            if self.trust_response:
                return self.trust_response(request)
            if str(request.url) == gateway.DISCOVERY:
                return reply({"issuer": gateway.ISSUER, "jwks_uri": gateway.JWKS})
            assert str(request.url) == gateway.JWKS
            return reply({"keys": [self.jwk]})

        def mock(self, request):
            self.mock_calls.append(request)
            if self.mock_response:
                return self.mock_response(request)
            if request.headers["accept"] == "text/event-stream":
                return httpx.Response(200, stream=Bytes(b"event: message_start\n\n",
                                                       b"event: message_stop\n\n"),
                                      headers={"content-type": "text/event-stream"})
            return reply({"content": [{"text": "MOCK_OK"}]})

        def run(self, check):
            async def test():
                async with self.app.router.lifespan_context(self.app):
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),
                                                 base_url="https://gateway") as client:
                        await check(client)
            asyncio.run(test())

    return Lab()
