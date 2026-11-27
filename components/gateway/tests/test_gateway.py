import asyncio
import json
import logging
import sqlite3
import time

import certifi
import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

import gateway
from lab_invoke import GATEWAY, ProofClient
from foundation import MCP_RESOURCE, MCP_SCOPE
from lab_fixtures import MOCK_SECRET, Bytes, reply

REQUEST = {"model": "lab", "messages": [{"role": "user", "content": "prompt-canary"}],
           "max_tokens": 16}


def test_json_sse_and_diagnostics(lab, caplog):
    caplog.set_level(logging.INFO, logger="uvicorn.error")

    async def check(client):
        token = lab.token()
        headers = {"authorization": f"Bearer {token}", "x-request-id": "forged-canary",
                   "x-forwarded-host": "external-canary", "x-custom": "header-canary"}
        response = await client.post("/v1/messages?beta=true", json=REQUEST, headers=headers)
        assert response.status_code == 200
        assert response.json()["content"][0]["text"] == "MOCK_OK"
        streamed = await client.post("/v1/messages", json={**REQUEST, "stream": True}, headers=headers)
        assert streamed.status_code == 200
        assert streamed.text == "event: message_start\n\nevent: message_stop\n\n"
        assert response.headers["request-id"] != streamed.headers["request-id"]
        for request in lab.mock_calls:
            assert request.url.host == "127.0.0.1"
            assert request.headers["authorization"] == f"Bearer {MOCK_SECRET}"
            assert set(request.headers) == {"host", "authorization", "content-type", "accept",
                                            "accept-encoding", "content-length"}
        assert str(lab.mock_calls[0].url) == gateway.MOCK + "?beta=true"
        denial = await client.post("/v1/messages", json=REQUEST,
                                   headers={"authorization": f"Bearer {token}corrupt"})
        assert denial.status_code == 401
        assert denial.json()["request_id"] == denial.headers["request-id"]
        for outcome in (response, streamed, denial):
            assert outcome.headers["request-id"] in caplog.text
        for canary in (token, MOCK_SECRET, "prompt-canary", "forged-canary", "header-canary"):
            assert canary not in caplog.text and canary not in denial.text

    lab.run(check)


@pytest.mark.parametrize(("claims", "header", "status"), [
    ({"iss": "wrong"}, {}, 401), ({"aud": ["urn:lab:llm-gateway"]}, {}, 401),
    ({"exp": 0}, {}, 401), ({"iat": int(time.time()) + 120}, {}, 401),
    ({"jti": ""}, {}, 401), ({}, {"typ": "JWT"}, 401),
    ({}, {"kid": "unknown"}, 401), ({}, {"jku": "https://invalid.example/keys"}, 401),
    ({"scope": "llm:read"}, {}, 403), ({"client_id": "other"}, {}, 403),
])
def test_rejects_token_before_mock(lab, claims, header, status):
    async def check(client):
        response = await client.post("/v1/messages", json=REQUEST,
                                     headers={"authorization": f"Bearer {lab.token(header, **claims)}"})
        assert response.status_code == status
        assert not lab.mock_calls
    lab.run(check)


def test_request_boundaries(lab, monkeypatch):
    monkeypatch.setattr(gateway, "BODY_LIMIT", 128)

    async def check(client):
        auth = ("authorization", f"Bearer {lab.token()}")
        json_type = ("content-type", "application/json")
        cases = [
            ("/v1/messages", [], b"", 401),
            ("/v1/messages", [auth, auth], b"", 400),
            ("/v1/messages", [auth, ("cookie", "token=canary")], b"", 400),
            ("/v1/messages", [auth, ("x-api-key", "canary")], b"", 400),
            ("/v1/messages?access_token=canary", [auth], b"", 400),
            ("/v1/messages?url=https://invalid.example", [auth, json_type], b"{}", 400),
            ("/v1/messages", [auth], b"{}", 415),
            ("/v1/messages", [auth, json_type, ("content-encoding", "gzip")], b"{}", 415),
            ("/v1/messages", [auth, json_type], b'{"access_token":"canary"}', 400),
            ("/v1/messages", [auth, json_type], b'{"a":1,"a":2}', 400),
            ("/v1/messages", [auth, json_type], b'{' + b' ' * 128, 413),
            ("/v1/messages", [("authorization", "x" * (gateway.AUTH_LIMIT + 1))], b"", 431),
        ]
        for url, headers, body, status in cases:
            response = await client.post(url, headers=headers, content=body)
            assert response.status_code == status
        assert not lab.mock_calls
        accepted = await client.post("/v1/messages", headers=[auth, json_type],
                                     content=b"{}" + b" " * 126)
        assert accepted.status_code == 200

    lab.run(check)


def test_rotation_rate_limit_and_expired_trust(lab):
    async def check(client):
        async def invoke(token):
            return await client.post("/v1/messages", json=REQUEST,
                                     headers={"authorization": f"Bearer {token}"})

        old = lab.token()
        assert (await invoke(old)).status_code == 200
        lab.rotate()
        new = lab.token()
        assert (await invoke(new)).status_code == 401
        assert lab.trust_calls == [gateway.DISCOVERY, gateway.JWKS]
        trust = lab.app.state.trust
        trust.refresh_after = 0
        assert (await invoke(new)).status_code == 200
        assert (await invoke(old)).status_code == 401

        trust.valid_until = trust.refresh_after = 0
        lab.trust_response = lambda _: httpx.Response(
            302, headers={"location": "https://invalid.example/jwks"})
        assert (await invoke(new)).status_code == 503
        assert lab.trust_calls[-1] == gateway.DISCOVERY
        assert len(lab.mock_calls) == 2

    lab.run(check)


@pytest.mark.parametrize(("failure", "status"), [
    (httpx.ConnectError("upstream-canary"), 502),
    (httpx.ConnectTimeout("upstream-canary"), 504),
    (httpx.ReadTimeout("upstream-canary"), 504),
])
def test_mock_transport_error(lab, failure, status):
    def fail(_):
        raise failure

    async def check(client):
        lab.mock_response = fail
        response = await client.post("/v1/messages", json=REQUEST,
                                     headers={"authorization": f"Bearer {lab.token()}"})
        assert response.status_code == status and "upstream-canary" not in response.text

    lab.run(check)


def test_stream_failure_after_start_sends_error_event(lab, caplog):
    caplog.set_level(logging.INFO, logger="uvicorn.error")

    class Broken(Bytes):
        async def __aiter__(self):
            yield b"event: message_start\n\n"
            raise httpx.ReadError("upstream-canary")

    async def check(client):
        lab.mock_response = lambda _: httpx.Response(
            200, stream=Broken(), headers={"content-type": "text/event-stream"})
        response = await client.post("/v1/messages", json={**REQUEST, "stream": True},
                                     headers={"authorization": f"Bearer {lab.token()}"})
        assert response.status_code == 200
        first, _, last = response.text.partition("event: error\ndata: ")
        assert first == "event: message_start\n\n\n\n"
        assert json.loads(last) == {"type": "error", "error": {
            "type": "api_error", "message": "Invalid or unavailable inference upstream"}}
        assert "message_stop" not in response.text and "upstream-canary" not in response.text

    lab.run(check)
    assert "event=mock_failed" in caplog.text


def test_stream_backpressure_and_disconnect(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="uvicorn.error")

    async def check():
        first_write = asyncio.Event()
        disconnect = asyncio.Event()
        requested = []

        class Stream(Bytes):
            async def __aiter__(self):
                requested.append(1)
                yield b"first"
                requested.append(2)
                yield b"second"

        stream = Stream()

        async def receive():
            await disconnect.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            if message["type"] == "http.response.body":
                first_write.set()
                await asyncio.Future()

        def mock(_):
            return httpx.Response(200, stream=stream, headers={"content-type": "text/event-stream"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(mock)) as client:
            response = gateway.Invocation(client, MOCK_SECRET, b"{}", True, "", "request-id")
            task = asyncio.create_task(response({}, receive, send))
            async with asyncio.timeout(2):
                await first_write.wait()
                assert requested == [1]
                disconnect.set()
                await task
        assert stream.closed

    asyncio.run(check())
    assert "client_disconnected" in caplog.text


@pytest.mark.parametrize("redirected_url", ["https://invalid.example/jwks",
                                            "https://127.0.0.1:8081/other"])
def test_discovery_must_match_pins(lab, redirected_url):
    lab.trust_response = lambda _: reply({"issuer": gateway.ISSUER, "jwks_uri": redirected_url})

    async def check(client):
        response = await client.post("/v1/messages", json=REQUEST,
                                     headers={"authorization": f"Bearer {lab.token()}"})
        assert response.status_code == 503
        assert lab.trust_calls == [gateway.DISCOVERY]
        assert not lab.mock_calls

    lab.run(check)


def test_overall_deadline_before_and_after_headers(lab, monkeypatch, caplog):
    monkeypatch.setattr(gateway, "DEADLINE", 0.1)
    caplog.set_level(logging.INFO, logger="uvicorn.error")

    class Stalled(Bytes):
        async def __aiter__(self):
            yield b"partial"
            await asyncio.Future()

    async def check(client):
        headers = {"authorization": f"Bearer {lab.token()}"}
        for streamed in (False, True):
            body = Stalled()
            media = "text/event-stream" if streamed else "application/json"
            lab.mock_response = lambda _: httpx.Response(200, stream=body,
                                                         headers={"content-type": media})
            response = await client.post("/v1/messages", headers=headers,
                                         json={**REQUEST, "stream": streamed})
            assert response.status_code == (200 if streamed else 504)
            if streamed:
                partial, _, error = response.content.partition(b"\n\nevent: error\ndata: ")
                assert partial == b"partial"
                assert json.loads(error)["error"]["message"] == "Inference upstream timed out"
            assert body.closed
        assert caplog.text.count("event=mock_timeout") == 2

    lab.run(check)


def test_rejects_substitution_even_with_known_key_id(lab):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    claims = jwt.decode(lab.token(), options={"verify_signature": False})
    substituted = jwt.encode(claims, other, algorithm="RS256",
                             headers={"typ": "at+jwt", "kid": lab.jwk["kid"]})

    async def check(client):
        response = await client.post("/v1/messages", json=REQUEST,
                                     headers={"authorization": f"Bearer {substituted}"})
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == 'Bearer error="invalid_token"'
        assert not lab.mock_calls

    lab.run(check)


def setup_gateway_dpop(lab, directory):
    lab.enable_dpop(directory)
    standard = lab.trust_response

    def upstream(request):
        if str(request.url) == gateway.DISCOVERY:
            return reply({"issuer": gateway.ISSUER, "jwks_uri": gateway.JWKS,
                          "dpop_signing_alg_values_supported": ["ES256"]})
        if standard is not None:
            return standard(request)
        assert str(request.url) == gateway.JWKS
        return reply({"keys": [lab.jwk]})

    lab.trust_response = upstream


def dpop_headers(token, proof):
    return {"authorization": f"DPoP {token}", "dpop": proof}


def test_dpop_gateway_challenge_concurrent_use_restart_and_diagnostics(lab, tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    setup_gateway_dpop(lab, tmp_path)
    signer = ProofClient()
    token = lab.token(cnf={"jkt": signer.jkt})
    first = signer.sign(GATEWAY, token)
    retained = {}

    async def check(client):
        challenge = await client.post("/v1/messages", json=REQUEST, headers=dpop_headers(token, first))
        assert challenge.status_code == 401
        assert challenge.headers["www-authenticate"] == 'DPoP error="use_dpop_nonce"'
        assert challenge.headers["cache-control"] == "no-store"
        assert not lab.mock_calls
        signer.remember_nonce(GATEWAY, challenge)

        proof = signer.sign(GATEWAY, token)
        retained["proof"] = proof
        headers = dpop_headers(token, proof)
        outcomes = await asyncio.gather(*[
            client.post("/v1/messages?beta=true", json=REQUEST, headers=headers) for _ in range(2)
        ])
        assert sorted(response.status_code for response in outcomes) == [200, 401]
        denied = next(response for response in outcomes if response.status_code == 401)
        assert denied.headers["www-authenticate"] == 'DPoP error="invalid_dpop_proof"'
        assert len(lab.mock_calls) == 1
        streamed = await client.post("/v1/messages", json={**REQUEST, "stream": True},
                                     headers=dpop_headers(token, signer.sign(GATEWAY, token)))
        assert streamed.status_code == 200 and "message_stop" in streamed.text
        assert len(lab.mock_calls) == 2
        for request in lab.mock_calls:
            assert request.headers["authorization"] == f"Bearer {MOCK_SECRET}"
            assert "dpop" not in request.headers
        for canary in (token, proof, first, signer.nonces[GATEWAY], signer.jkt, "prompt-canary"):
            assert canary not in caplog.text and canary not in denied.text

    lab.run(check)
    lab.enable_dpop(tmp_path)

    async def restart(client):
        response = await client.post("/v1/messages", json=REQUEST,
                                     headers=dpop_headers(token, retained["proof"]))
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == 'DPoP error="invalid_dpop_proof"'
        assert len(lab.mock_calls) == 2

    lab.run(restart)


def test_dpop_gateway_rejects_substitution_and_downgrade(lab, tmp_path):
    setup_gateway_dpop(lab, tmp_path)
    signer, other = ProofClient(), ProofClient()
    token = lab.token(cnf={"jkt": signer.jkt})

    async def check(client):
        for headers, challenge in [
            ({"authorization": f"Bearer {token}"}, 'DPoP error="invalid_token"'),
            ({"authorization": f"DPoP {token}"}, 'DPoP error="invalid_dpop_proof"'),
            (dpop_headers(token, other.sign(GATEWAY, token)), 'DPoP error="invalid_dpop_proof"'),
            (dpop_headers(token, signer.sign(GATEWAY, "other-token")), 'DPoP error="invalid_dpop_proof"'),
            (dpop_headers(token, signer.sign(gateway.ISSUER + "/token", token)),
             'DPoP error="invalid_dpop_proof"'),
            (dpop_headers(lab.token(), signer.sign(GATEWAY, token)), 'DPoP error="invalid_token"'),
        ]:
            response = await client.post("/v1/messages", json=REQUEST, headers=headers)
            assert response.status_code == 401
            assert response.headers["www-authenticate"] == challenge
        assert not lab.mock_calls

    lab.run(check)


def test_dpop_gateway_spends_proof_on_upstream_failure_and_fails_closed(lab, tmp_path):
    setup_gateway_dpop(lab, tmp_path)
    signer = ProofClient()
    token = lab.token(cnf={"jkt": signer.jkt})

    async def check(client):
        challenge = await client.post("/v1/messages", json=REQUEST,
                                      headers=dpop_headers(token, signer.sign(GATEWAY, token)))
        signer.remember_nonce(GATEWAY, challenge)
        headers = dpop_headers(token, signer.sign(GATEWAY, token))

        def fail(_request):
            raise httpx.ReadTimeout("synthetic upstream timeout")

        lab.mock_response = fail
        assert (await client.post("/v1/messages", json=REQUEST, headers=headers)).status_code == 504
        assert (await client.post("/v1/messages", json=REQUEST, headers=headers)).status_code == 401
        assert len(lab.mock_calls) == 1

        store = lab.app.state.replay
        with sqlite3.connect(store.path) as db:
            db.execute("UPDATE clock SET high = ?", (int(time.time()) + 30,))
        for unavailable in (False, True):
            if unavailable:
                store.path.unlink()
            fresh = dpop_headers(token, signer.sign(GATEWAY, token))
            response = await client.post("/v1/messages", json=REQUEST, headers=fresh)
            assert response.status_code == 503
            assert len(lab.mock_calls) == 1

    lab.run(check)


def test_gateway_required_mode_mismatch_stops_dispatch(lab, tmp_path):
    lab.enable_dpop(tmp_path)
    signer = ProofClient()
    token = lab.token(cnf={"jkt": signer.jkt})

    async def check(client):
        response = await client.post("/v1/messages", json=REQUEST,
                                     headers=dpop_headers(token, signer.sign(GATEWAY, token)))
        assert response.status_code == 503
        assert lab.trust_calls == [gateway.DISCOVERY]
        assert not lab.mock_calls

    lab.run(check)


def invoke_in_worker(directory, jwk, headers, barrier, result):
    async def check():
        def trust(request):
            if str(request.url) == gateway.DISCOVERY:
                return reply({"issuer": gateway.ISSUER, "jwks_uri": gateway.JWKS,
                              "dpop_signing_alg_values_supported": ["ES256"]})
            assert str(request.url) == gateway.JWKS
            return reply({"keys": [jwk]})

        mock_calls = []

        def mock(request):
            mock_calls.append(request)
            return reply({"ok": True})

        app = gateway.create_app(certifi.where(), MOCK_SECRET,
                                 dpop_nonce_key=directory / "nonce.key", dpop_replay_dir=directory,
                                 trust_transport=httpx.MockTransport(trust),
                                 mock_transport=httpx.MockTransport(mock))
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                         base_url="https://127.0.0.1:8082") as client:
                barrier.wait(timeout=10)
                response = await client.post("/v1/messages", headers=headers, json=REQUEST)
                result.put((response.status_code, len(mock_calls)))

    asyncio.run(check())


def test_gateway_dpop_replay_across_processes(lab, tmp_path):
    import multiprocessing

    setup_gateway_dpop(lab, tmp_path)
    signer = ProofClient()
    token = lab.token(cnf={"jkt": signer.jkt})
    verifier = gateway.Verifier(GATEWAY, (tmp_path / "nonce.key").read_bytes())
    signer.nonces[GATEWAY] = verifier.new_nonce(signer.jkt, int(time.time()))
    headers = dpop_headers(token, signer.sign(GATEWAY, token))
    context = multiprocessing.get_context("spawn")
    barrier, result = context.Barrier(2), context.Queue()
    workers = [context.Process(target=invoke_in_worker,
                               args=(tmp_path, lab.jwk, headers, barrier, result)) for _ in range(2)]
    try:
        for worker in workers:
            worker.start()
        outcomes = [result.get(timeout=15) for _ in workers]
        for worker in workers:
            worker.join(timeout=5)
            assert worker.exitcode == 0
        assert sorted(outcomes) == [(200, 1), (401, 0)]
    finally:
        for worker in workers:
            if worker.pid is not None:
                if worker.is_alive():
                    worker.terminate()
                worker.join(timeout=5)
        result.close()


def test_lab_client_assertion_follows_rfc_10070(monkeypatch):
    """The client the probe and the broker use marks its assertion as RFC 10070 recommends."""
    import lab_invoke
    from types import SimpleNamespace

    sent = []

    def token_endpoint(request):
        sent.append(dict(httpx.QueryParams(request.content.decode())))
        return httpx.Response(200, json={"access_token": "synthetic", "token_type": "Bearer"})

    monkeypatch.setattr(lab_invoke, "tls_client",
                        lambda _: httpx.Client(transport=httpx.MockTransport(token_endpoint)))
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = lab_invoke.exchange_token(SimpleNamespace(as_ca=None), "subject-token", None, signing_key=key)
    assert token == "synthetic" and len(sent) == 1
    assert (sent[0]["audience"], sent[0]["scope"], "resource" in sent[0]) == (gateway.TARGET, gateway.SCOPE, False)
    lab_invoke.exchange_token(SimpleNamespace(as_ca=None), "subject-token", None, signing_key=key, mcp=True)
    assert (sent[1]["resource"], sent[1]["scope"], "audience" in sent[1]) == (MCP_RESOURCE, MCP_SCOPE, False)
    assertion = sent[0]["client_assertion"]
    assert jwt.get_unverified_header(assertion)["typ"] == "client-authentication+jwt"
    claims = jwt.decode(assertion, key.public_key(), algorithms=["RS256"], audience=gateway.ISSUER)
    assert claims["aud"] == gateway.ISSUER and claims["iss"] == claims["sub"] == gateway.CLIENT


def test_model_gateway_refuses_a_token_issued_for_the_mcp_gateway(lab):
    async def check(client):
        for claims in ({"aud": MCP_RESOURCE, "scope": MCP_SCOPE}, {"aud": MCP_RESOURCE},
                       {"aud": [gateway.TARGET, MCP_RESOURCE]}):
            response = await client.post("/v1/messages", json=REQUEST,
                                         headers={"authorization": f"Bearer {lab.token(**claims)}"})
            assert response.status_code == 401
            assert response.headers["www-authenticate"] == 'Bearer error="invalid_token"'
        # The right audience with the MCP scope is authenticated but not permitted.
        response = await client.post("/v1/messages", json=REQUEST,
                                     headers={"authorization": f"Bearer {lab.token(scope=MCP_SCOPE)}"})
        assert response.status_code == 403
        assert not lab.mock_calls

    lab.run(check)


def test_dpop_model_gateway_refuses_a_token_issued_for_the_mcp_gateway(lab, tmp_path):
    """The shape the authorization server really issues for MCP: bound to a key."""
    setup_gateway_dpop(lab, tmp_path)
    signer = ProofClient()
    binding = {"cnf": {"jkt": signer.jkt}}

    async def attempt(client, **claims):
        token = lab.token(**binding, **claims)
        return await client.post("/v1/messages", json=REQUEST,
                                 headers=dpop_headers(token, signer.sign(GATEWAY, token)))

    async def check(client):
        for claims in ({"aud": MCP_RESOURCE, "scope": MCP_SCOPE}, {"aud": MCP_RESOURCE},
                       {"aud": [gateway.TARGET, MCP_RESOURCE]}, {"aud": [gateway.TARGET]}):
            response = await attempt(client, **claims)
            assert response.status_code == 401
            assert response.headers["www-authenticate"] == 'DPoP error="invalid_token"'
        assert not lab.mock_calls

    lab.run(check)



def test_another_gateway_can_name_its_own_audience_and_scope(lab):
    async def check(client):
        trust = lab.app.state.trust
        claims = await gateway.validate_access_token(lab.token(aud=MCP_RESOURCE), trust, "Bearer", MCP_RESOURCE)
        assert claims["aud"] == MCP_RESOURCE
        for token, audience in ((lab.token(), MCP_RESOURCE), (lab.token(aud=MCP_RESOURCE), gateway.TARGET),
                                (lab.token(aud=[MCP_RESOURCE]), MCP_RESOURCE)):
            with pytest.raises(gateway.Failure) as refused:
                await gateway.validate_access_token(token, trust, "Bearer", audience)
            assert refused.value.status == 401

    lab.run(check)
    gateway.enforce_policy({"client_id": gateway.CLIENT, "scope": MCP_SCOPE}, "DPoP", MCP_SCOPE)
    with pytest.raises(gateway.Failure) as refused:
        gateway.enforce_policy({"client_id": gateway.CLIENT, "scope": gateway.SCOPE}, "DPoP", MCP_SCOPE)
    assert refused.value.status == 403
    assert refused.value.challenge == 'DPoP error="insufficient_scope", scope="mcp:invoke"'
