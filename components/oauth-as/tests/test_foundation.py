import asyncio
import copy
import json
from contextlib import asynccontextmanager

import certifi
import httpx
import jwt
import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app import create_app
from foundation import (
    DISCOVERY, ISSUER, POLICY, UPSTREAM, UPSTREAM_JWKS, FoundationError, load_local,
    provision, public_jwk,
)


@pytest.fixture
def local(tmp_path):
    keys = tmp_path / "keys"
    provision(keys)
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps(POLICY))
    return keys, policy


@pytest.fixture(scope="module")
def upstream_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def reply(document, status=200, **headers):
    return httpx.Response(status, stream=httpx.ByteStream(json.dumps(document).encode()),
                          headers=headers)


def issuer_transport(key):
    def request(req):
        if str(req.url) == DISCOVERY:
            return reply({"issuer": UPSTREAM, "jwks_uri": UPSTREAM_JWKS})
        assert str(req.url) == UPSTREAM_JWKS
        return reply({"keys": [public_jwk(key.public_key())]})
    return httpx.MockTransport(request)


def lab_app(local, transport, ca=certifi.where()):
    keys, policy = local
    return create_app(keys, ca, policy, transport=transport)


@asynccontextmanager
async def running(app):
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url=ISSUER) as client:
            yield client


def test_metadata_jwks_and_disabled_routes(local, upstream_key, caplog):
    async def check():
        app = lab_app(local, issuer_transport(upstream_key))
        async with running(app) as client:
            metadata = await client.get("/.well-known/oauth-authorization-server")
            assert metadata.json() == {"issuer": ISSUER, "jwks_uri": ISSUER + "/jwks",
                                       "grant_types_supported": [], "response_types_supported": []}
            jwks = await client.get("/jwks")
            assert jwks.status_code == 200
            (jwk,) = jwks.json()["keys"]
            assert set(jwk) == {"kid", "kty", "use", "alg", "n", "e"}
            assert jwk["kid"] != public_jwk(upstream_key.public_key())["kid"]

            for grant in ("urn:ietf:params:oauth:grant-type:token-exchange", "client_credentials",
                          "authorization_code", "refresh_token"):
                response = await client.post("/token", data={"grant_type": grant,
                                                             "subject_token": "synthetic-secret"})
                assert response.status_code == 404 and response.json() == {"detail": "Not Found"}
            for path in ("/authorize", "/login", "/register", "/sign", "/openapi.json",
                         "/docs", "/.well-known/openid-configuration", "/jwks/"):
                assert (await client.get(path)).status_code == 404
                assert (await client.post(path)).status_code == 404
            assert (await client.post("/jwks")).status_code == 405
        assert "synthetic-secret" not in caplog.text
        return jwk

    jwk = asyncio.run(check())
    assert asyncio.run(check()) == jwk
    key = serialization.load_pem_private_key((local[0] / "signing.key").read_bytes(), None)
    challenge = b"component-02b signing verification challenge"
    signature = key.sign(challenge, padding.PKCS1v15(), hashes.SHA256())
    jwt.PyJWK.from_dict(jwk).key.verify(signature, challenge, padding.PKCS1v15(), hashes.SHA256())
    with pytest.raises(InvalidSignature):
        upstream_key.public_key().verify(signature, challenge, padding.PKCS1v15(), hashes.SHA256())


@pytest.mark.parametrize("problem", ["missing", "mode", "directory-mode", "invalid", "symlink"])
def test_invalid_signing_material_fails_startup(local, upstream_key, problem):
    directory, _ = local
    key = directory / "signing.key"
    if problem == "missing":
        key.unlink()
    elif problem == "mode":
        key.chmod(0o644)
    elif problem == "directory-mode":
        directory.chmod(0o755)
    elif problem == "invalid":
        key.write_text("synthetic-secret")
    else:
        key.rename(directory / "other.key")
        key.symlink_to("other.key")

    async def check():
        with pytest.raises(RuntimeError, match="local key, CA, or policy"):
            async with running(lab_app(local, issuer_transport(upstream_key))):
                pytest.fail("invalid key allowed service startup")
    asyncio.run(check())


@pytest.mark.parametrize("field,value", [
    ("client_id", "*"), ("client_id", "macos-oauth-client"),
    ("source_audience", "another-client"), ("target", "*"), ("scope", "llm:*"),
    ("issuer", "https://other.invalid"), ("authentication", "none"),
    ("subject_token_type", "urn:ietf:params:oauth:token-type:access_token"),
    ("exchange_enabled", True), ("issuance_enabled", True), ("exchange_enabled", 0),
])
def test_policy_defaults_to_deny(local, field, value):
    directory, path = local
    load_local(directory, path)
    policy = copy.deepcopy(POLICY)
    (policy if field in policy else policy["candidate"])[field] = value
    path.write_text(json.dumps(policy))
    with pytest.raises(FoundationError, match="disabled lab profile"):
        load_local(directory, path)


@pytest.mark.parametrize("problem", [
    "wrong issuer", "changed jwks", "off loopback", "redirect discovery", "redirect jwks",
    "unavailable", "tls failure", "malformed jwks", "duplicate kid", "duplicate key",
    "as key overlap", "oversized", "private jwk",
])
def test_rejects_untrusted_upstream(local, upstream_key, problem):
    calls = []
    good_key = public_jwk(upstream_key.public_key())
    as_key, _ = load_local(*local)
    def request(req):
        url = str(req.url)
        calls.append(url)
        if url == DISCOVERY:
            if problem in ("tls failure", "unavailable"):
                raise httpx.ConnectError("synthetic upstream error", request=req)
            if problem == "redirect discovery":
                return reply({}, 302, location="https://outside.invalid")
            issuer = ISSUER if problem == "wrong issuer" else UPSTREAM
            jwks = {"changed jwks": UPSTREAM + "/other",
                    "off loopback": "https://outside.invalid/jwks"}.get(problem, UPSTREAM_JWKS)
            return reply({"issuer": issuer, "jwks_uri": jwks})
        assert url == UPSTREAM_JWKS
        if problem == "redirect jwks":
            return reply({}, 302, location="https://outside.invalid")
        key_sets = {
            "malformed jwks": [{"kid": "x", "kty": "RSA"}],
            "duplicate kid": [good_key, good_key],
            "duplicate key": [good_key, {**good_key, "kid": "alias"}],
            "as key overlap": [good_key, {**as_key, "kid": "renamed"}],
            "private jwk": [{**good_key, "d": "synthetic-secret"}],
        }
        if problem == "oversized":
            return reply({"oversized": "x" * 70000})
        return reply({"keys": key_sets[problem]})

    async def check():
        with pytest.raises(RuntimeError, match="pinned upstream trust"):
            async with running(lab_app(local, httpx.MockTransport(request))):
                pytest.fail("untrusted upstream allowed startup")
    asyncio.run(check())
    assert calls[0] == DISCOVERY and set(calls) <= {DISCOVERY, UPSTREAM_JWKS}


def test_expired_trust_fails_closed_and_recovers(local, upstream_key):
    valid = issuer_transport(upstream_key).handler
    offline = False
    attempts = 0

    def request(req):
        nonlocal attempts
        attempts += 1
        if offline:
            raise httpx.ConnectError("offline", request=req)
        return valid(req)

    async def check():
        nonlocal offline
        app = lab_app(local, httpx.MockTransport(request))
        async with running(app) as client:
            assert (await client.get("/jwks")).status_code == 200
            assert attempts == 2
            app.state.trust.valid_until = 0
            offline = True
            assert (await client.get("/jwks")).status_code == 503
            assert (await client.get("/.well-known/oauth-authorization-server")).status_code == 503
            assert attempts == 3
            offline = False
            app.state.trust.retry_after = 0
            assert (await client.get("/jwks")).status_code == 200
            assert attempts == 5
    asyncio.run(check())
