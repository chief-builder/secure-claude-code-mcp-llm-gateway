import asyncio
import logging
import socket
import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

import broker
from dpop import Verifier, token_hash

HOST = "127.0.0.1:54321"
PAYLOAD = {"model": "lab", "messages": [{"role": "user", "content": "prompt-canary"}]}


class Chunks(httpx.AsyncByteStream):
    def __init__(self, *chunks):
        self.chunks = chunks
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk

    async def aclose(self):
        self.closed = True


def run_app(check, upstream):
    async def run():
        session = broker.Session("upstream-token-canary", broker.ProofClient(), int(time.time()) + 120)
        async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as gateway:
            app = broker.create_app(session, gateway, HOST)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                         base_url=f"http://{HOST}") as client:
                await check(client, session)
    asyncio.run(run())


def test_nonce_retry_json_sse_and_audit(caplog):
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    seen = []
    challenge_body = Chunks(b"challenge")
    verifier = Verifier(broker.GATEWAY, b"k" * 32)
    state = {}

    def upstream(request):
        proof = request.headers["dpop"]
        claims = jwt.decode(proof, options={"verify_signature": False})
        assert request.headers["authorization"] == "DPoP upstream-token-canary"
        assert claims["ath"] == token_hash("upstream-token-canary")
        assert claims["htu"] == broker.GATEWAY
        assert set(request.headers) == {"host", "authorization", "dpop", "content-type",
                                        "accept", "accept-encoding", "content-length"}
        seen.append(claims)
        request_id = f"{len(seen):032x}"
        if len(seen) == 1:
            assert "nonce" not in claims
            nonce = verifier.new_nonce(state["jkt"], int(time.time()))
            return httpx.Response(401, stream=challenge_body,
                                  headers={"www-authenticate": 'DPoP error="use_dpop_nonce"',
                                           "dpop-nonce": nonce, "request-id": request_id})
        verifier.validate([proof], token="upstream-token-canary", binding=state["jkt"])
        if request.headers["accept"] == "text/event-stream":
            return httpx.Response(200, stream=Chunks(b"event: message_start\n\n",
                                                   b"event: message_stop\n\n"),
                                  headers={"content-type": "text/event-stream", "request-id": request_id})
        return httpx.Response(200, stream=Chunks(b'{"answer":"MOCK_OK"}'),
                              headers={"content-type": "application/json", "request-id": request_id})

    async def check(client, session):
        state["jkt"] = session.proof.jkt
        headers = {"authorization": f"Bearer {session.secret}", "request-id": "caller-canary"}
        reply = await client.post("/v1/messages", json=PAYLOAD, headers=headers)
        streamed = await client.post("/v1/messages?beta=true", json={**PAYLOAD, "stream": True},
                                     headers=headers)
        assert reply.json() == {"answer": "MOCK_OK"}
        assert streamed.text.endswith("event: message_stop\n\n")
        assert challenge_body.closed
        assert len({claims["jti"] for claims in seen}) == 3
        for number in (1, 2):
            assert f"broker_request_id={reply.headers['request-id']} gateway_request_id={number:032x}" in caplog.text
        assert streamed.headers["request-id"] != reply.headers["request-id"]
        for canary in ("upstream-token-canary", "caller-canary", "prompt-canary", session.secret,
                       session.proof.nonces[broker.GATEWAY]):
            assert canary not in caplog.text

    run_app(check, upstream)


def test_rejects_local_requests_and_expiry_before_forwarding():
    def unexpected(_request):
        pytest.fail("Rejected request was forwarded")

    async def check(client, session):
        auth = ("authorization", f"Bearer {session.secret}")
        for headers, status in [
            ([], 401), ([("authorization", "Bearer wrong")], 401),
            ([auth, auth], 400), ([auth, ("host", "other")], 400),
            ([auth, ("origin", "https://browser.invalid")], 400),
            ([auth, ("x-forwarded-host", "untrusted")], 400),
            ([auth, ("dpop", "unexpected")], 400),
            ([auth, ("cookie", "token=canary")], 400),
        ]:
            assert (await client.post("/v1/messages", json=PAYLOAD, headers=headers)).status_code == status
        assert (await client.post("/token", json=PAYLOAD, headers=[auth])).status_code == 404
        assert (await client.post("/v1/messages?url=https://example.invalid", json=PAYLOAD,
                                  headers=[auth])).status_code == 400
        assert (await client.post("/v1/messages", json={"x": "a" * (1024 * 1024)},
                                  headers=[auth])).status_code == 413
        session.expiry = 0
        assert (await client.post("/v1/messages", json=PAYLOAD, headers=[auth])).status_code == 401

    run_app(check, unexpected)


@pytest.mark.parametrize("event", ["transport", "bad_nonce", "repeated_nonce"])
def test_only_retries_explicit_well_formed_nonce_challenge(event):
    calls = []
    nonce = "a" * 75

    def upstream(request):
        calls.append(request)
        if event == "transport":
            raise httpx.ReadTimeout("unsafe upstream text")
        return httpx.Response(401, stream=Chunks(), headers={
            "www-authenticate": 'DPoP error="use_dpop_nonce"',
            "dpop-nonce": nonce if event == "repeated_nonce" else "bad",
        })

    async def check(client, session):
        response = await client.post("/v1/messages", json=PAYLOAD,
                                     headers={"authorization": f"Bearer {session.secret}"})
        assert response.status_code == (504 if event == "transport" else 502)
        assert len(calls) == (2 if event == "repeated_nonce" else 1)
        assert nonce not in response.text and "unsafe upstream text" not in response.text

    run_app(check, upstream)


def test_child_environment_has_only_local_credential(tmp_path, monkeypatch):
    for key in ("AWS_SECRET_ACCESS_KEY", "ANTHROPIC_API_KEY", "HTTPS_PROXY", "ANTHROPIC_CUSTOM_HEADERS"):
        monkeypatch.setenv(key, "untrusted-canary")
    env = broker.child_env("http://127.0.0.1:43210", "local-only", tmp_path)
    assert env["ANTHROPIC_AUTH_TOKEN"] == "local-only"
    assert env["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:43210"
    assert env["CLAUDE_CONFIG_DIR"] == str(tmp_path)
    assert "untrusted-canary" not in env.values()


def test_lab_exchange_key_requires_safe_path_and_permissions(tmp_path):
    tmp_path.chmod(0o700)
    key_path = tmp_path / "assertion.key"
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                          serialization.NoEncryption()))
    key_path.chmod(0o600)
    assert broker.read_exchange_key(tmp_path).public_key().public_numbers() == key.public_key().public_numbers()
    key_path.chmod(0o644)
    with pytest.raises(ValueError):
        broker.read_exchange_key(tmp_path)


def test_software_key_custody_baseline():
    signer = broker.ProofClient()
    exported = signer.key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
                                        serialization.NoEncryption())
    second = serialization.load_der_private_key(exported, None)
    assert isinstance(second, ec.EllipticCurvePrivateKey)
    signature = jwt.encode({"synthetic": True}, second, algorithm="ES256")
    assert jwt.decode(signature, signer.key.public_key(), algorithms=["ES256"]) == {"synthetic": True}


def test_second_local_client_with_secret_can_invoke_until_shutdown():
    def upstream(_request):
        return httpx.Response(200, stream=Chunks(b"{}"), headers={"content-type": "application/json"})

    async def check(client, session):
        second = {"authorization": f"Bearer {session.secret}"}
        assert (await client.post("/v1/messages", json=PAYLOAD, headers=second)).status_code == 200
        session.active = False
        assert (await client.post("/v1/messages", json=PAYLOAD, headers=second)).status_code == 401

    run_app(check, upstream)


@pytest.mark.parametrize("cancel", [False, True])
def test_child_exit_or_cancellation_releases_listener(tmp_path, monkeypatch, cancel):
    import os
    import shlex
    import sys

    script = tmp_path / "client"
    report = tmp_path / "port"
    code = f"""#!/bin/sh
exec {shlex.quote(sys.executable)} - <<'PYTHON'
import json, os, time, urllib.request
from pathlib import Path
url = os.environ["ANTHROPIC_BASE_URL"]
request = urllib.request.Request(url + "/v1/messages", data=b'{{}}', headers={{
    "Content-Type": "application/json",
    "Authorization": "Bearer " + os.environ["ANTHROPIC_AUTH_TOKEN"],
}})
assert json.load(urllib.request.urlopen(request, timeout=3)) == {{"ok": True}}
Path({str(report)!r}).write_text(url)
if {cancel!r}:
    time.sleep(30)
PYTHON
"""
    script.write_text(code)
    script.chmod(0o700)
    monkeypatch.setenv("PATH", os.environ["PATH"])

    def upstream(_request):
        return httpx.Response(200, stream=Chunks(b'{"ok":true}'), headers={"content-type": "application/json"})

    async def check():
        session = broker.Session("token", broker.ProofClient(), int(time.time()) + 120)
        async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as gateway:
            task = asyncio.create_task(broker.launch(str(script), "sonnet", session, gateway))
            if cancel:
                async with asyncio.timeout(5):
                    while not report.exists():
                        if task.done():
                            await task
                            pytest.fail("Synthetic child exited before reporting its listener")
                        await asyncio.sleep(0.01)
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            else:
                assert await task == 0
            assert not session.active
        port = int(report.read_text().rsplit(":", 1)[1])
        with socket.socket() as check_listener:
            check_listener.settimeout(1)
            assert check_listener.connect_ex(("127.0.0.1", port)) != 0

    asyncio.run(check())


def test_adapts_single_inline_system_message_for_text_mock():
    import json

    user = {"role": "user", "content": "synthetic prompt"}
    system = {"role": "system", "content": [{"type": "text", "text": "synthetic context"}]}
    payload = {"messages": [user, system], "system": "existing context"}
    adapted = json.loads(broker.mock_compatible_body(json.dumps(payload).encode()))
    assert adapted["messages"] == [user]
    assert adapted["system"] == [{"type": "text", "text": "existing context"}, *system["content"]]
    with pytest.raises(broker.Failure):
        broker.mock_compatible_body(json.dumps({"messages": [user, user, system]}).encode())


def test_text_only_profile_is_explicit_and_bounded(tmp_path):
    normal = broker.child_env("http://127.0.0.1:12345", "local", tmp_path)
    assert "CLAUDE_CODE_MAX_OUTPUT_TOKENS" not in normal
    restricted = broker.child_env("http://127.0.0.1:12345", "local", tmp_path, text_only=True)
    assert restricted["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] == "128"
    assert restricted["CLAUDE_CODE_DISABLE_THINKING"] == "1"
    assert restricted["MAX_THINKING_TOKENS"] == "0"
    assert restricted["CLAUDE_CODE_EFFORT_LEVEL"] == "unset"
    assert restricted["DISABLE_PROMPT_CACHING"] == "1"
    assert restricted["CLAUDE_CODE_DISABLE_STRUCTURED_OUTPUTS"] == "1"
    assert restricted["CLAUDE_CODE_MAX_RETRIES"] == "0"
