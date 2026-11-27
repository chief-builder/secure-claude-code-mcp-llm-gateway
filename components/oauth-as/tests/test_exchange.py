import asyncio
import json
import logging
import secrets
import sqlite3
import time

import certifi
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from app import create_app
from dpop import Verifier, encode, thumbprint
from exchange import ACCESS, ASSERTION, ASSERTION_TYPE, CLIENT, GRANT, SCOPE, TARGET
from foundation import EXCHANGE_CANDIDATE as CANDIDATE
from foundation import ISSUER, UPSTREAM, public_jwk
from test_foundation import issuer_transport, reply, running

SUBJECT = "synthetic-employee-id"
MAPPED = "opaque-synthetic-gateway-id"


@pytest.fixture
def profile(local, upstream_key):
    directory, policy = local
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    registered = public_jwk(key.public_key())
    (directory / "exchange-client-jwks.json").write_text(json.dumps({"keys": [registered]}))
    policy.write_text(json.dumps({
        "exchange_enabled": True, "issuance_enabled": True, "candidate": CANDIDATE,
        "subjects": {SUBJECT: MAPPED},
    }))

    def app(transport=None, *, dpop_nonce_key=None):
        return create_app(directory, certifi.where(), exchange_policy=policy,
                          dpop_nonce_key=dpop_nonce_key, transport=transport or issuer_transport(upstream_key))

    def form(subject=None, *, source_claims=None, client_claims=None, client_key=key,
             client_type=ASSERTION_TYPE):
        now = int(time.time())
        if subject is None:
            subject = jwt.encode({
                "iss": UPSTREAM, "sub": SUBJECT, "aud": CANDIDATE["source_audience"],
                "typ": "ID", "iat": now, "exp": now + 120,
                "nonce": secrets.token_urlsafe(32), **(source_claims or {}),
            }, upstream_key, algorithm="RS256",
                headers={"kid": public_jwk(upstream_key.public_key())["kid"]})
        assertion = jwt.encode({
            "iss": CLIENT, "sub": CLIENT, "aud": ISSUER, "iat": now,
            "exp": now + 30, "jti": secrets.token_urlsafe(24), **(client_claims or {}),
        }, client_key, algorithm="RS256", headers={"kid": registered["kid"], "typ": client_type})
        return {"grant_type": GRANT, "audience": TARGET, "scope": SCOPE,
                "client_assertion_type": ASSERTION, "client_assertion": assertion,
                "subject_token": subject, "subject_token_type": CANDIDATE["subject_token_type"]}

    return app, form


def rejected(response, code="invalid_request", status=400):
    assert response.status_code == status
    assert response.json() == {"error": code}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"


def test_exchange_replay_restart_and_diagnostics(profile, upstream_key, caplog):
    app, form = profile
    caplog.set_level(logging.INFO, logger="uvicorn.error")

    async def check():
        request = form()
        subject = request["subject_token"]
        async with running(app()) as client:
            metadata = (await client.get("/.well-known/oauth-authorization-server")).json()
            assert metadata["grant_types_supported"] == [GRANT]
            assert metadata["token_endpoint"] == ISSUER + "/token"
            assert metadata["token_endpoint_auth_methods_supported"] == ["private_key_jwt"]
            assert metadata["token_endpoint_auth_signing_alg_values_supported"] == ["RS256"]
            assert (await client.get("/authorize")).status_code == 404
            results = await asyncio.gather(*(
                client.post("/token", data=attempt, headers={"X-Request-ID": "forged-canary"})
                for attempt in (request, form(subject))
            ))
            assert sorted(r.status_code for r in results) == [200, 400]
            for response in results:
                assert response.headers["x-request-id"] in caplog.text
            success = next(r for r in results if r.status_code == 200)
            result = success.json()
            assert success.headers["cache-control"] == "no-store"
            token = result.pop("access_token")
            assert result == {"token_type": "Bearer", "issued_token_type": ACCESS,
                              "scope": SCOPE, "expires_in": result["expires_in"]}
            jwk, = (await client.get("/jwks")).json()["keys"]
            assert jwt.get_unverified_header(token) == {"typ": "at+jwt", "kid": jwk["kid"], "alg": "RS256"}
            claims = jwt.decode(token, jwt.PyJWK.from_dict(jwk).key, algorithms=["RS256"],
                                issuer=ISSUER, audience=TARGET)
            assert set(claims) == {"iss", "sub", "aud", "iat", "exp", "scope", "jti", "client_id"}
            assert (claims["sub"], claims["client_id"], claims["scope"]) == (MAPPED, CLIENT, SCOPE)
            assert 0 < claims["exp"] - claims["iat"] == result["expires_in"] <= 120
            with pytest.raises(jwt.InvalidSignatureError):
                jwt.decode(token, upstream_key.public_key(), algorithms=["RS256"], audience=TARGET)
            rejected(await client.post("/token", data=form(token)))
            rejected(await client.post("/token", data=request), "invalid_client")

        async with running(app()) as client:
            rejected(await client.post("/token", data=form(subject)))
        for value in (subject, request["client_assertion"], token, "forged-canary"):
            assert value not in caplog.text
        for event in ("exchange_succeeded", "subject_replay", "client_replay", "subject_rejected"):
            assert f"event={event}" in caplog.text

    asyncio.run(check())


def test_bad_requests_and_client_consumption(profile, upstream_key):
    app, form = profile

    async def check():
        async with running(app()) as client:
            for overrides, code in [
                ({"scope": "llm:invoke admin"}, "invalid_scope"),
                ({"scope": None}, "invalid_scope"),
                ({"audience": "other"}, "invalid_target"),
                ({"grant_type": "client_credentials"}, "unsupported_grant_type"),
                ({"actor_token": "actor"}, "invalid_request"),
                ({"client_assertion": None}, "invalid_client"),
                ({"client_id": CANDIDATE["source_audience"]}, "invalid_client"),
                ({"requested_token_type": "other"}, "invalid_request"),
            ]:
                request = form()
                for key, value in overrides.items():
                    if value is None:
                        del request[key]
                    else:
                        request[key] = value
                rejected(await client.post("/token", data=request), code)

            bad_scope = {**form(), "scope": "bad"}
            rejected(await client.post("/token", data=bad_scope), "invalid_scope")
            rejected(await client.post("/token", data={**bad_scope, "scope": SCOPE}), "invalid_client")
            for request in (form(client_key=upstream_key), form(client_claims={"aud": ISSUER + "/token"}),
                            form(client_claims={"aud": [ISSUER]}),
                            form(client_claims={"aud": [ISSUER, ISSUER + "/token"]}),
                            form(client_claims={"exp": int(time.time()) - 1})):
                rejected(await client.post("/token", data=request), "invalid_client")
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            for data in ("scope=a&scope=b", "scope=%ZZ", "scope=%FF", "scope=" + "x" * 32768):
                rejected(await client.post("/token", content=data, headers=headers))
            rejected(await client.post("/token", json=form()))
            rejected(await client.post("/token", data=form(), headers={"Authorization": "Basic lab"}))
            rejected(await client.post("/token", data=form(client_claims={"aud": "https://else/token"}),
                                       headers={"X-Forwarded-Host": "else", "X-Forwarded-Proto": "https"}),
                     "invalid_client")

    asyncio.run(check())


def header_type(request):
    return jwt.get_unverified_header(request["client_assertion"]).get("typ", "absent")


def test_client_assertion_type(profile):
    app, form = profile

    async def check():
        async with running(app()) as client:
            # RFC 10070: accept the explicit type, and do not reject untyped assertions.
            # RFC 7515: the type is a media type name, so case and "application/" do not matter.
            for accepted, sent in (
                (ASSERTION_TYPE, "client-authentication+jwt"), ("JWT", "JWT"), (None, "absent"),
                ("jwt", "jwt"), ("application/jwt", "application/jwt"),
                ("Application/Client-Authentication+JWT", "Application/Client-Authentication+JWT"),
            ):
                request = form(client_type=accepted)
                assert header_type(request) == sent
                assert (await client.post("/token", data=request)).status_code == 200
            # An assertion that declares itself another kind of token is refused, and
            # refusing it spends neither its identifier nor the subject token: the same
            # identifier and subject token are accepted once the type is right.
            for other in ("at+jwt", "dpop+jwt", "application/at+jwt", "client-authentication+jwt ",
                          "JWT+client-authentication", "application/"):
                identifier = secrets.token_urlsafe(24)
                request = form(client_type=other, client_claims={"jti": identifier})
                rejected(await client.post("/token", data=request), "invalid_client")
                retry = form(request["subject_token"], client_claims={"jti": identifier})
                assert (await client.post("/token", data=retry)).status_code == 200
                rejected(await client.post("/token", data=retry), "invalid_client")

    asyncio.run(check())


@pytest.mark.parametrize("value", [0, 1, True, False, ["JWT"], [], {"a": 1}, {}, ""])
def test_assertion_type_must_be_a_known_string_or_absent(value):
    from exchange import accepted_assertion_type
    assert accepted_assertion_type(value) is False
    assert accepted_assertion_type(None) is True


def test_subject_claims_and_dependencies(profile, monkeypatch):
    app, form = profile

    async def check():
        instance = app()
        async with running(instance) as client:
            # Pin both times for the lifetime case: the form's own clock may tick past this one.
            start = int(time.time())
            for claims in [
                {"iss": ISSUER}, {"aud": "else"}, {"azp": "else"}, {"sub": "unknown"},
                {"typ": "Bearer"}, {"nonce": ""}, {"iat": start, "exp": start + 301},
                {"iat": start - 61}, {"iat": True},
            ]:
                rejected(await client.post("/token", data=form(source_claims=claims)))
            rejected(await client.post("/token", data=form("bad.token.parts")))

            request = form()
            with monkeypatch.context() as patch:
                original = jwt.encode

                def fail_sign(*args, **kwargs):
                    if kwargs.get("headers", {}).get("typ") == "at+jwt":
                        raise ValueError
                    return original(*args, **kwargs)

                patch.setattr(jwt, "encode", fail_sign)
                rejected(await client.post("/token", data=request), "temporarily_unavailable", 503)
            assert (await client.post("/token", data=form(request["subject_token"]))).status_code == 200

            store = instance.state.exchange.store
            with monkeypatch.context() as patch:
                def unavailable():
                    raise sqlite3.OperationalError
                patch.setattr(store, "connect", unavailable)
                rejected(await client.post("/token", data=form()), "temporarily_unavailable", 503)

            async def no_trust(_kid):
                return False
            with monkeypatch.context() as patch:
                patch.setattr(instance.state.trust, "ready", no_trust)
                rejected(await client.post("/token", data=form()), "temporarily_unavailable", 503)

            with sqlite3.connect(store.path) as db:
                db.execute("UPDATE clock SET high = ?", (int(time.time()) + 30,))
            rejected(await client.post("/token", data=form()), "temporarily_unavailable", 503)

    asyncio.run(check())


def test_placeholder_cannot_enable_exchange(profile, local):
    app, _ = profile
    (local[0] / "exchange-client-jwks.json").unlink()

    async def check():
        with pytest.raises(RuntimeError):
            async with running(app()):
                pytest.fail("Started without registered exchange key")

    asyncio.run(check())


def test_failed_subject_commit_does_not_return_token(profile, monkeypatch):
    app, form = profile

    class RejectSubjectCommit(sqlite3.Connection):
        def __exit__(self, exc_type, exc, traceback):
            if exc_type is None and self.execute("SELECT count(*) FROM spent").fetchone()[0] == 2:
                self.rollback()
                raise sqlite3.OperationalError("fixture commit failure")
            return super().__exit__(exc_type, exc, traceback)

    async def check():
        instance = app()
        async with running(instance) as client:
            store = instance.state.exchange.store
            request = form()
            with monkeypatch.context() as patch:
                patch.setattr(store, "connect",
                              lambda: sqlite3.connect(store.path, factory=RejectSubjectCommit))
                rejected(await client.post("/token", data=request), "temporarily_unavailable", 503)
            rejected(await client.post("/token", data=request), "invalid_client")
            assert (await client.post("/token", data=form(request["subject_token"]))).status_code == 200

    asyncio.run(check())


def test_replay_with_resigned_subject_and_unknown_key(profile, upstream_key):
    app, form = profile

    async def check():
        async with running(app()) as client:
            nonce = secrets.token_urlsafe(32)
            assert (await client.post("/token", data=form(source_claims={"nonce": nonce}))).status_code == 200
            rejected(await client.post("/token", data=form(source_claims={"nonce": nonce, "jti": "new"})))

            claims = jwt.decode(form()["subject_token"], options={"verify_signature": False})
            unknown = jwt.encode(claims, upstream_key, algorithm="RS256", headers={"kid": "unknown"})
            rejected(await client.post("/token", data=form(unknown)))

    asyncio.run(check())


def exchange_in_worker(directory, policy, upstream_jwk, form, barrier, result,
                       nonce_path=None, proof=None):
    """Run one request in an independent AS process."""
    import os

    import httpx

    from foundation import DISCOVERY, UPSTREAM_JWKS

    def upstream(request):
        if str(request.url) == DISCOVERY:
            return reply({"issuer": UPSTREAM, "jwks_uri": UPSTREAM_JWKS})
        assert str(request.url) == UPSTREAM_JWKS
        return reply({"keys": [upstream_jwk]})

    async def check():
        app = create_app(directory, certifi.where(), exchange_policy=policy,
                         dpop_nonce_key=nonce_path, transport=httpx.MockTransport(upstream))
        async with running(app) as client:
            ready = app.state.trust.ready

            async def synchronize_subject_validation(kid):
                trusted = await ready(kid)
                barrier.wait(timeout=10)
                return trusted

            app.state.trust.ready = synchronize_subject_validation
            headers = {"DPoP": proof} if proof is not None else {}
            response = await client.post("/token", data=form, headers=headers)
            body = response.json()
            result.put((os.getpid(), response.status_code, "access_token" in body,
                        body.get("error")))

    asyncio.run(check())


@pytest.mark.parametrize("bound", [False, True])
def test_exchange_replay_across_processes(profile, local, upstream_key, bound):
    import multiprocessing

    _, form = profile
    directory, policy = local
    first = form()
    second = form() if bound else form(first["subject_token"])
    path, proof = (None, None)
    if bound:
        path, verifier, key, jwk = setup_dpop(directory)
        proof = sign_proof(key, jwk, nonce=verifier.new_nonce(thumbprint(jwk), int(time.time())))
    assert first["client_assertion"] != second["client_assertion"]

    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(2)
    result = context.Queue()
    upstream_jwk = public_jwk(upstream_key.public_key())
    workers = [
        context.Process(target=exchange_in_worker,
                        args=(directory, policy, upstream_jwk, request, barrier, result, path, proof))
        for request in (first, second)
    ]
    try:
        for worker in workers:
            worker.start()
        outcomes = [result.get(timeout=15) for _ in workers]
        for worker in workers:
            worker.join(timeout=5)
            assert worker.exitcode == 0
        assert len({outcome[0] for outcome in outcomes}) == 2
        assert sorted(outcome[1:] for outcome in outcomes) == [
            (200, True, None),
            (400, False, "invalid_dpop_proof" if bound else "invalid_request"),
        ]
    finally:
        for worker in workers:
            if worker.pid is not None:
                if worker.is_alive():
                    worker.terminate()
                worker.join(timeout=5)
        result.close()


@pytest.mark.parametrize("bound", [False, True], ids=["bearer", "dpop"])
def test_exchange_lost_response_after_commit(profile, local, bound):
    import socket
    from urllib.parse import urlencode

    import httpx
    import uvicorn

    app, form = profile
    path = None
    if bound:
        path, verifier, key, public = setup_dpop(local[0])
        nonce = verifier.new_nonce(thumbprint(public), int(time.time()))

    def proof_headers():
        return {"DPoP": sign_proof(key, public, nonce=nonce)} if bound else {}

    async def check(listener):
        response_ready = asyncio.Event()
        disconnected = asyncio.Event()
        exchange_app = app(dpop_nonce_key=path)

        async def drop_response(scope, receive, send):
            # Model HTTPS at the application boundary while testing a real TCP disconnect.
            if scope["type"] == "http":
                scope = {**scope, "scheme": "https"}
            if scope["type"] != "http" or (b"x-drop-response", b"1") not in scope["headers"]:
                await exchange_app(scope, receive, send)
                return

            async def hold_response(message):
                if message["type"] == "http.response.start":
                    assert message["status"] == 200
                    response_ready.set()
                    assert (await receive())["type"] == "http.disconnect"
                    disconnected.set()

            await exchange_app(scope, receive, hold_response)

        server = uvicorn.Server(uvicorn.Config(
            drop_response, lifespan="on", access_log=False, log_config=None,
            proxy_headers=False, timeout_graceful_shutdown=2,
        ))
        task = asyncio.create_task(server.serve(sockets=[listener]))
        host, port = listener.getsockname()
        try:
            async with asyncio.timeout(10):
                while not server.started:
                    if task.done():
                        await task
                        pytest.fail("Test server stopped before startup")
                    await asyncio.sleep(0.01)

                original = form()
                body = urlencode(original).encode("ascii")
                headers = proof_headers()
                proof_fields = "".join(f"{name}: {value}\r\n" for name, value in headers.items())
                _, writer = await asyncio.open_connection(host, port)
                try:
                    writer.write(
                        f"POST /token HTTP/1.1\r\nHost: {host}:{port}\r\n"
                        f"X-Drop-Response: 1\r\n{proof_fields}"
                        "Content-Type: application/x-www-form-urlencoded\r\n"
                        f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body
                    )
                    await writer.drain()
                    await response_ready.wait()
                finally:
                    writer.close()
                    await writer.wait_closed()
                await disconnected.wait()

                async with httpx.AsyncClient(trust_env=False) as client:
                    endpoint = f"http://{host}:{port}/token"
                    fresh_headers = proof_headers()
                    if bound:
                        assert fresh_headers != headers
                    retry = await client.post(endpoint, data=form(original["subject_token"]),
                                              headers=fresh_headers)
                    rejected(retry)
                    if bound:
                        # Use a different unspent subject to isolate the original proof's replay record.
                        repeated_proof = await client.post(endpoint, data=form(), headers=headers)
                        rejected(repeated_proof, "invalid_dpop_proof")
        finally:
            server.should_exit = True
            await asyncio.wait_for(task, timeout=5)

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        asyncio.run(check(listener))


def setup_dpop(directory):
    path = directory / "dpop.key"
    path.write_bytes(secrets.token_bytes(32))
    path.chmod(0o600)
    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_numbers()
    jwk = {"kty": "EC", "crv": "P-256", "x": encode(public.x.to_bytes(32, "big")),
           "y": encode(public.y.to_bytes(32, "big"))}
    return path, Verifier(ISSUER + "/token", path.read_bytes()), key, jwk


def sign_proof(key, jwk, **overrides):
    return jwt.encode({"jti": secrets.token_urlsafe(24), "htm": "POST", "htu": ISSUER + "/token",
                       "iat": int(time.time()), **overrides},
                      key, algorithm="ES256", headers={"typ": "dpop+jwt", "jwk": jwk})


def test_dpop_exchange_challenge_binding_and_replay(profile, local):
    app, form = profile
    path, _, key, public = setup_dpop(local[0])

    async def check():
        original = form()
        subject = original["subject_token"]
        async with running(app(dpop_nonce_key=path)) as client:
            metadata = (await client.get("/.well-known/oauth-authorization-server")).json()
            assert metadata["dpop_signing_alg_values_supported"] == ["ES256"]
            missing = await client.post("/token", data=form(subject))
            rejected(missing, "invalid_dpop_proof")
            challenge = await client.post("/token", data=original,
                                          headers={"DPoP": sign_proof(key, public)})
            rejected(challenge, "use_dpop_nonce")
            nonce, = challenge.headers.get_list("dpop-nonce")
            proof = sign_proof(key, public, nonce=nonce)
            # The first authenticated request consumes its client assertion, even on challenge.
            rejected(await client.post("/token", data=original, headers={"DPoP": proof}),
                     "invalid_client")
            success = await client.post("/token", data=form(subject), headers={"DPoP": proof})
            assert success.status_code == 200 and success.json()["token_type"] == "DPoP"
            jwk, = (await client.get("/jwks")).json()["keys"]
            claims = jwt.decode(success.json()["access_token"], jwt.PyJWK.from_dict(jwk).key,
                                algorithms=["RS256"], issuer=ISSUER, audience=TARGET)
            assert claims["cnf"] == {"jkt": thumbprint(public)}
            fresh_subject = form()
            rejected(await client.post("/token", data=fresh_subject, headers={"DPoP": proof}),
                     "invalid_dpop_proof")
            # Rejecting a proof replay leaves the new subject usable.
            updated = await client.post("/token", data=form(fresh_subject["subject_token"]),
                                        headers={"DPoP": sign_proof(key, public, nonce=nonce)})
            assert updated.status_code == 200

        async with running(app(dpop_nonce_key=path)) as client:
            rejected(await client.post("/token", data=form(), headers={"DPoP": proof}),
                     "invalid_dpop_proof")

    asyncio.run(check())


@pytest.mark.parametrize("binding", ["wrong_method", "wrong_endpoint", "stale", "future",
                                    "private_jwk", "invalid_signature", "duplicate", "oversize",
                                    "unexpected_ath", "invalid_nonce", "expired_nonce"])
def test_dpop_exchange_invalid_proofs(profile, local, binding):
    app, form = profile
    path, verifier, key, public = setup_dpop(local[0])
    now = int(time.time())
    nonce = verifier.new_nonce(thumbprint(public), now)
    claims = {"nonce": nonce}
    if binding == "wrong_method":
        claims["htm"] = "GET"
    elif binding == "wrong_endpoint":
        claims["htu"] = "https://127.0.0.1:8082/v1/messages"
    elif binding == "stale":
        claims["iat"] = now - 31
    elif binding == "future":
        claims["iat"] = now + 60
    elif binding == "private_jwk":
        public = {**public, "d": encode(secrets.token_bytes(32))}
    elif binding == "invalid_signature":
        key = ec.generate_private_key(ec.SECP256R1())
    elif binding == "unexpected_ath":
        claims["ath"] = "unexpected"
    elif binding == "invalid_nonce":
        claims["nonce"] = "invalid"
    elif binding == "expired_nonce":
        claims["nonce"] = verifier.new_nonce(thumbprint(public), now - 61)
    proof = sign_proof(key, public, **claims)
    headers = [("dpop", proof)]
    if binding == "duplicate":
        headers *= 2
    elif binding == "oversize":
        headers = [("dpop", "a" * 8193)]

    async def check():
        async with running(app(dpop_nonce_key=path)) as client:
            response = await client.post("/token", data=form(), headers=headers)
            code = "use_dpop_nonce" if binding in ("invalid_nonce", "expired_nonce") else "invalid_dpop_proof"
            rejected(response, code)
            assert ("dpop-nonce" in response.headers) == (code == "use_dpop_nonce")

    asyncio.run(check())


def test_dpop_exchange_signing_failure_rolls_back_proof_and_subject(profile, local, monkeypatch):
    app, form = profile
    path, verifier, key, public = setup_dpop(local[0])
    nonce = verifier.new_nonce(thumbprint(public), int(time.time()))
    proof = sign_proof(key, public, nonce=nonce)
    original = form()

    async def check():
        async with running(app(dpop_nonce_key=path)) as client:
            encode_jwt = jwt.encode

            def fail_sign(*args, **kwargs):
                if kwargs.get("headers", {}).get("typ") == "at+jwt":
                    raise ValueError("fixture signing failure")
                return encode_jwt(*args, **kwargs)

            with monkeypatch.context() as patch:
                patch.setattr(jwt, "encode", fail_sign)
                rejected(await client.post("/token", data=original, headers={"DPoP": proof}),
                         "temporarily_unavailable", 503)
            response = await client.post("/token", data=form(original["subject_token"]),
                                         headers={"DPoP": proof})
            assert response.status_code == 200

    asyncio.run(check())


def test_dpop_exchange_token_authorizes_gateway_invocation(profile, local, monkeypatch, tmp_path):
    import httpx

    import gateway
    from lab_invoke import GATEWAY, ProofClient, REQUEST

    app, form = profile
    path, _, _, _ = setup_dpop(local[0])
    gateway_dir = tmp_path / "gateway"
    gateway_dir.mkdir(mode=0o700)
    gateway_nonce, _, _, _ = setup_dpop(gateway_dir)
    signer = ProofClient()
    endpoint = ISSUER + "/token"
    subject = form()["subject_token"]
    upstream_credential = "synthetic_gateway_mock_credential"
    calls = []

    def mock(request):
        calls.append(request)
        return reply({"content": [{"text": "MOCK_OK"}]}, **{"content-type": "application/json"})


    async def check():
        authority = app(dpop_nonce_key=path)
        async with running(authority) as exchange:
            challenge = await exchange.post("/token", data=form(subject),
                                            headers={"DPoP": signer.sign(endpoint)})
            rejected(challenge, "use_dpop_nonce")
            signer.remember_nonce(endpoint, challenge)
            issued = await exchange.post("/token", data=form(subject),
                                         headers={"DPoP": signer.sign(endpoint)})
            assert issued.status_code == 200
            token = issued.json()["access_token"]

            gateway_app = gateway.create_app(
                certifi.where(), upstream_credential, dpop_nonce_key=gateway_nonce,
                dpop_replay_dir=gateway_dir, trust_transport=httpx.ASGITransport(app=authority),
                mock_transport=httpx.MockTransport(mock),
            )

            def headers():
                return {"Authorization": f"DPoP {token}", "DPoP": signer.sign(GATEWAY, token)}

            async with running(gateway_app) as client:
                denied = await client.post("/v1/messages", json=REQUEST, headers=headers())
                assert denied.status_code == 401
                assert denied.headers["www-authenticate"] == 'DPoP error="use_dpop_nonce"'
                assert not calls
                signer.remember_nonce(GATEWAY, denied)
                response = await client.post("/v1/messages", json=REQUEST, headers=headers())
                assert response.status_code == 200
                assert response.json()["content"][0]["text"] == "MOCK_OK"
                assert len(calls) == 1
                assert calls[0].headers["authorization"] == f"Bearer {upstream_credential}"
                assert "dpop" not in calls[0].headers

    asyncio.run(check())
