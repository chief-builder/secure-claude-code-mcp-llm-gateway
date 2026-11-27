"""The MCP gateway, tested against the SDK-built mock tool server and hand-made fakes."""

import asyncio
import base64
import json
import logging
import secrets
import time

import certifi
import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

import gateway
import mcp_gateway
import mock_mcp
from foundation import MCP_RESOURCE, MCP_SCOPE, public_jwk
from lab_fixtures import Bytes, reply
from lab_invoke import GATEWAY, ProofClient, mcp_probe
from starlette.testclient import TestClient

UPSTREAM_SECRET = "synthetic_tool_server_secret_canary"
SUBJECT = "synthetic-gateway-subject-01"
VERSION = "2026-07-28"
META = {mcp_gateway.PROTOCOL_VERSION: VERSION,
        mcp_gateway.CAPABILITIES: {"elicitation": {"form": {}, "url": {}}, "roots": {}}}
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
JWK = public_jwk(KEY.public_key())
HINT = f'scope="mcp:invoke", resource_metadata="{mcp_gateway.METADATA}"'
NONCE = f'DPoP error="use_dpop_nonce", {HINT}'


class Upstream(httpx.AsyncBaseTransport):
    """Records what the gateway sends, then answers with a fake or the real mock server."""

    def __init__(self, lab):
        self.lab = lab
        self.real = httpx.ASGITransport(app=lab.tool_server)

    async def handle_async_request(self, request):
        await request.aread()
        self.lab.sent.append(request)
        if self.lab.fake is not None:
            return self.lab.fake(request)
        return await self.real.handle_async_request(request)


class Lab:
    def __init__(self, directory, policy):
        directory.chmod(0o700)
        nonce = directory / "nonce.key"
        nonce.write_bytes(secrets.token_bytes(32))
        nonce.chmod(0o600)
        self.sent, self.fake = [], None
        self.signer = ProofClient()
        self.tool_server = mock_mcp.create_app(UPSTREAM_SECRET)
        self.app = mcp_gateway.create_app(
            certifi.where(), UPSTREAM_SECRET, policy, dpop_nonce_key=nonce, dpop_replay_dir=directory,
            trust_transport=httpx.MockTransport(self.trust), upstream_transport=Upstream(self))

    def trust(self, request):
        if str(request.url) == gateway.DISCOVERY:
            return reply({"issuer": gateway.ISSUER, "jwks_uri": gateway.JWKS,
                          "dpop_signing_alg_values_supported": ["ES256"]})
        return reply({"keys": [JWK]})

    def token(self, **claims):
        now = int(time.time())
        return jwt.encode(
            {"iss": gateway.ISSUER, "aud": MCP_RESOURCE, "sub": SUBJECT, "jti": "synthetic-jti",
             "iat": now, "exp": now + 120, "client_id": gateway.CLIENT, "scope": MCP_SCOPE,
             "cnf": {"jkt": self.signer.jkt}, **claims},
            KEY, algorithm="RS256", headers={"typ": "at+jwt", "kid": JWK["kid"]})

    async def post(self, client, body, headers, *, token=None, proof=None, content=None):
        """Send one request with a fresh proof, answering the first nonce challenge."""
        token = token or self.token()
        for _ in range(2):
            credentials = {"authorization": f"DPoP {token}",
                           "dpop": proof or self.signer.sign(MCP_RESOURCE, token)}
            sent = {key: value for key, value in {**credentials, **headers}.items() if value is not None}
            if content is None:
                response = await client.post("/mcp", json=body, headers=sent)
            else:
                response = await client.post("/mcp", content=content,
                                             headers={"content-type": "application/json", **sent})
            if response.headers.get("www-authenticate") != NONCE or proof is not None:
                return response
            self.signer.remember_nonce(MCP_RESOURCE, response)
        return response

    def run(self, check):
        async def session():
            async with self.tool_server.router.lifespan_context(self.tool_server):
                async with self.app.router.lifespan_context(self.app):
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),
                                                 base_url="https://127.0.0.1:8083") as client:
                        await check(client)
        asyncio.run(session())


@pytest.fixture
def lab(tmp_path):
    return Lab(tmp_path, {SUBJECT: frozenset({"lab_echo"})})


def rpc(method, params=None, *, name=None, headers=None, meta=META, call_id=7):
    body = {"jsonrpc": "2.0", "id": call_id, "method": method,
            "params": {**(params or {}), **({"_meta": meta} if meta is not None else {})}}
    sent = {"MCP-Protocol-Version": VERSION, "Mcp-Method": method}
    if name is not None:
        sent["Mcp-Name"] = name
    sent.update(headers or {})
    return body, sent


def call(tool, arguments, **options):
    return rpc("tools/call", {"name": tool, "arguments": arguments}, name=tool, **options)


def error_of(response):
    return response.status_code, response.json()["error"]["code"]


def test_discover_list_and_call_an_allowed_tool(lab, caplog):
    caplog.set_level(logging.INFO, logger="uvicorn.error")

    async def check(client):
        discovered = await lab.post(client, *rpc("server/discover"))
        assert discovered.status_code == 200 and discovered.headers["cache-control"] == "no-store"
        result = discovered.json()["result"]
        assert result["capabilities"] == {"tools": {"listChanged": False}}
        assert result["supportedVersions"] == [VERSION] and result["resultType"] == "complete"
        assert result["_meta"][mcp_gateway.SERVER_INFO]["name"] == "lab-mcp-gateway"
        assert (result["cacheScope"], result["ttlMs"]) == ("private", 0)
        assert not lab.sent  # answered by the gateway itself

        listed = (await lab.post(client, *rpc("tools/list"))).json()
        assert listed["id"] == 7
        # The tool server offers two tools and says its list is public; this user may see one.
        assert [tool["name"] for tool in listed["result"]["tools"]] == ["lab_echo"]
        assert (listed["result"]["cacheScope"], listed["result"]["ttlMs"]) == ("private", 0)
        assert listed["result"]["tools"][0]["inputSchema"]["required"] == ["text"]

        called = await lab.post(client, *call("lab_echo", {"text": "argument-canary"}, call_id="abc"))
        assert called.json() == {"jsonrpc": "2.0", "id": "abc", "result": {
            "resultType": "complete", "isError": False,
            "content": [{"type": "text", "text": "argument-canary"}],
            "structuredContent": {"result": "argument-canary"}}}
        encoded = "=?base64?" + base64.b64encode(b"lab_echo").decode() + "?="
        assert (await lab.post(client, *call("lab_echo", {"text": "x"}, headers={"Mcp-Name": encoded}))).status_code == 200

    lab.run(check)
    token, nonce = lab.token(), lab.signer.nonces[MCP_RESOURCE]
    assert [request.headers["mcp-method"] for request in lab.sent] == ["tools/list", "tools/call", "tools/call"]
    for request in lab.sent:
        # Its own credential and the current revision's headers, by POST; nothing of the caller's.
        assert request.method == "POST" and str(request.url) == mcp_gateway.UPSTREAM
        assert request.headers["authorization"] == f"Bearer {UPSTREAM_SECRET}"
        assert request.headers["mcp-protocol-version"] == VERSION
        assert "dpop" not in request.headers and "cookie" not in request.headers
        sent = json.loads(request.content)
        assert sent["params"]["_meta"] == {mcp_gateway.PROTOCOL_VERSION: VERSION, mcp_gateway.CAPABILITIES: {}}
        for canary in (token, nonce, lab.signer.jkt, "elicitation"):
            assert canary.encode() not in request.content and canary not in str(request.headers)
    assert json.loads(lab.sent[1].content)["params"] == {
        "name": "lab_echo", "arguments": {"text": "argument-canary"},
        "_meta": {mcp_gateway.PROTOCOL_VERSION: VERSION, mcp_gateway.CAPABILITIES: {}}}
    lines = [record.getMessage() for record in caplog.records if "mcp_gateway" in record.getMessage()]
    assert any("event=tool_called request_id=" in line and line.endswith(f"subject={SUBJECT} tool=lab_echo")
               for line in lines)
    assert any("event=tools_listed" in line and line.endswith(f"subject={SUBJECT}") for line in lines)
    for canary in ("argument-canary", token, UPSTREAM_SECRET, nonce, lab.signer.jkt):
        assert canary not in caplog.text


def test_a_hidden_tool_and_a_missing_tool_are_refused_identically(lab, caplog):
    caplog.set_level(logging.INFO, logger="uvicorn.error")

    async def check(client):
        hidden = await lab.post(client, *call("lab_add", {"a": 1, "b": 2}))
        missing = await lab.post(client, *call("no_such_tool", {"a": 1, "b": 2}))
        assert hidden.status_code == missing.status_code == 200
        assert hidden.content == missing.content
        assert hidden.json() == {"jsonrpc": "2.0", "id": 7, "error": {"code": -32602, "message": "Unknown tool"}}
        # Filtering the list is not the enforcement: the call itself is refused, and never forwarded.
        assert not lab.sent

    lab.run(check)
    assert "event=tool_refused" in caplog.text
    assert "lab_add" not in caplog.text and "no_such_tool" not in caplog.text


def test_a_user_the_policy_does_not_name_has_no_tools(tmp_path):
    lab = Lab(tmp_path, {"someone-else": frozenset({"lab_echo", "lab_add"})})

    async def check(client):
        assert (await lab.post(client, *rpc("tools/list"))).json()["result"]["tools"] == []
        assert error_of(await lab.post(client, *call("lab_echo", {"text": "x"}))) == (200, -32602)
        assert (await lab.post(client, *rpc("server/discover"))).status_code == 200
        assert len(lab.sent) == 1

    lab.run(check)


@pytest.mark.parametrize(("claims", "status", "challenge"), [
    ({"aud": gateway.TARGET}, 401, 'DPoP error="invalid_token"'),
    ({"aud": gateway.TARGET, "scope": gateway.SCOPE}, 401, 'DPoP error="invalid_token"'),
    ({"aud": [MCP_RESOURCE]}, 401, 'DPoP error="invalid_token"'),
    ({"iat": int(time.time()) - 400, "exp": int(time.time()) - 200}, 401, 'DPoP error="invalid_token"'),
    ({"iss": "https://elsewhere.example"}, 401, 'DPoP error="invalid_token"'),
    ({"cnf": None}, 401, 'DPoP error="invalid_token"'),
    ({"scope": gateway.SCOPE}, 403, 'DPoP error="insufficient_scope", scope="mcp:invoke"'),
    ({"client_id": "another-client"}, 403, None),
])
def test_refuses_a_token_that_is_not_a_valid_mcp_token(lab, claims, status, challenge, caplog):
    async def check(client):
        # Obtain a nonce with a good token first, so the refusal is for the token alone.
        assert (await lab.post(client, *rpc("server/discover"))).status_code == 200
        caplog.clear()
        caplog.set_level(logging.INFO, logger="uvicorn.error")
        refused = await lab.post(client, *call("lab_echo", {"text": "x"}), token=lab.token(**claims))
        assert refused.status_code == status and refused.content == b""
        expected = challenge and (f"{challenge}, {HINT}" if "scope=" not in challenge else
                                  f'{challenge}, resource_metadata="{mcp_gateway.METADATA}"')
        assert refused.headers.get("www-authenticate") == expected
        assert refused.headers["cache-control"] == "no-store"
        assert not lab.sent

    lab.run(check)
    # A caller refused before its client and scope are accepted is not named in the log.
    assert SUBJECT not in caplog.text


def test_refuses_wrong_or_ambiguous_credentials(lab):
    metadata = HINT

    async def check(client):
        token = lab.token()
        body, headers = call("lab_echo", {"text": "x"})
        missing = await client.post("/mcp", json=body, headers=headers)
        assert (missing.status_code, missing.headers["www-authenticate"]) == (401, f"DPoP {metadata}")
        bearer = await lab.post(client, body, {**headers, "authorization": f"Bearer {token}"})
        assert bearer.status_code == 401
        assert bearer.headers["www-authenticate"] == f'DPoP error="invalid_token", {metadata}'
        for extra in ({"x-api-key": "anything"}, {"cookie": "a=b"}):
            assert (await lab.post(client, body, {**headers, **extra})).status_code == 400
        assert (await client.post("/mcp?access_token=" + token, json=body, headers={
            **headers, "authorization": f"DPoP {token}", "dpop": lab.signer.sign(MCP_RESOURCE, token)})).status_code == 400
        assert not lab.sent

    lab.run(check)


def test_refuses_a_missing_wrong_or_replayed_proof(lab):
    async def check(client):
        token = lab.token()
        body, headers = call("lab_echo", {"text": "x"})
        credential = {**headers, "authorization": f"DPoP {token}"}

        # The first proof has no nonce: it is challenged, and the challenge carries one.
        first = lab.signer.sign(MCP_RESOURCE, token)
        challenged = await client.post("/mcp", json=body, headers={**credential, "dpop": first})
        assert (challenged.status_code, challenged.headers["www-authenticate"]) == (401, NONCE)
        lab.signer.remember_nonce(MCP_RESOURCE, challenged)

        invalid = f'DPoP error="invalid_dpop_proof", {HINT}'
        no_proof = await client.post("/mcp", json=body, headers=credential)
        assert (no_proof.status_code, no_proof.headers["www-authenticate"]) == (401, invalid)

        # A proof made for the LLM gateway's address, or for no token, or by another key.
        lab.signer.nonces[GATEWAY] = lab.signer.nonces[MCP_RESOURCE]
        other = ProofClient()
        other.nonces = dict(lab.signer.nonces)
        for proof in (lab.signer.sign(GATEWAY, token), lab.signer.sign(MCP_RESOURCE),
                      other.sign(MCP_RESOURCE, token), lab.signer.sign(MCP_RESOURCE, lab.token(jti="another"))):
            refused = await client.post("/mcp", json=body, headers={**credential, "dpop": proof})
            assert (refused.status_code, refused.headers["www-authenticate"]) == (401, invalid)

        # A nonce this gateway did not issue is challenged again.
        lab.signer.nonces[MCP_RESOURCE] = "A" * 75
        stale = await client.post("/mcp", json=body, headers={
            **credential, "dpop": lab.signer.sign(MCP_RESOURCE, token)})
        assert (stale.status_code, stale.headers["www-authenticate"]) == (401, NONCE)
        lab.signer.remember_nonce(MCP_RESOURCE, stale)
        assert not lab.sent

        # A proof works once.
        proof = lab.signer.sign(MCP_RESOURCE, token)
        outcomes = await asyncio.gather(*[
            client.post("/mcp", json=body, headers={**credential, "dpop": proof}) for _ in range(2)])
        assert sorted(response.status_code for response in outcomes) == [200, 401]
        again = await client.post("/mcp", json=body, headers={**credential, "dpop": proof})
        assert (again.status_code, again.headers["www-authenticate"]) == (401, invalid)
        assert len(lab.sent) == 1

    lab.run(check)


@pytest.mark.parametrize("headers", [
    {"MCP-Protocol-Version": None},
    {"MCP-Protocol-Version": "2025-11-25"},
    {"MCP-Protocol-Version": "2026-07-28 "},
    {"Mcp-Method": None},
    {"Mcp-Method": "tools/list"},
    {"Mcp-Name": None},
    {"Mcp-Name": "lab_add"},
    {"Mcp-Name": "LAB_ECHO"},
    {"Mcp-Name": "=?base64?bm90LWJhc2U2NA?="},
    # The attack the headers invite: they name one request, the body makes another.
    {"Mcp-Method": "tools/list", "Mcp-Name": None},
])
def test_headers_must_agree_with_the_body(lab, headers):
    async def check(client):
        refused = await lab.post(client, *call("lab_echo", {"text": "x"}, headers=headers))
        assert error_of(refused) == (400, -32020) and refused.json()["id"] == 7
        assert not lab.sent

    lab.run(check)


def test_headers_naming_an_allowed_tool_do_not_cover_a_call_to_another(tmp_path):
    lab = Lab(tmp_path, {SUBJECT: frozenset({"lab_echo"})})

    async def check(client):
        body, headers = call("lab_add", {"a": 1, "b": 2}, headers={"Mcp-Name": "lab_echo"})
        assert error_of(await lab.post(client, body, headers)) == (400, -32020)
        # A list request must not carry a tool name at all.
        assert error_of(await lab.post(client, *rpc("tools/list", name="lab_echo"))) == (400, -32020)
        # An older revision named consistently in header and body is unsupported, not a mismatch.
        old = {**META, mcp_gateway.PROTOCOL_VERSION: "2025-11-25"}
        unsupported = await lab.post(client, *rpc(
            "tools/list", meta=old, headers={"MCP-Protocol-Version": "2025-11-25"}))
        assert error_of(unsupported) == (400, -32022)
        assert unsupported.json()["error"]["data"] == {"supported": [VERSION], "requested": "2025-11-25"}
        assert not lab.sent

    lab.run(check)


def test_refuses_everything_else(lab):
    async def check(client):
        for method in ("prompts/list", "resources/list", "subscriptions/listen", "initialize", "ping"):
            assert error_of(await lab.post(client, *rpc(method))) == (404, -32601)
        for meta in (None, {mcp_gateway.PROTOCOL_VERSION: VERSION}, "text"):
            assert error_of(await lab.post(client, *rpc("tools/list", meta=meta))) == (400, -32602)
        assert error_of(await lab.post(client, *rpc("tools/list", {"cursor": 5}))) == (400, -32602)
        body, headers = call("lab_echo", {"text": "x"})
        body["params"]["arguments"] = ["not", "an", "object"]
        assert error_of(await lab.post(client, body, headers)) == (400, -32602)
        body, headers = rpc("tools/call", {"name": 5}, name="5")
        assert error_of(await lab.post(client, body, headers)) == (400, -32602)

        body, headers = rpc("tools/list")
        notification = {key: value for key, value in body.items() if key != "id"}
        for invalid in (notification, [body], {**body, "id": None}, {**body, "id": True},
                        {**body, "id": 1.5}, {**body, "jsonrpc": "1.0"}, {**body, "extra": 1}):
            refused = await lab.post(client, invalid, headers)
            assert refused.status_code == 400 and refused.content == b""
        duplicate = b'{"jsonrpc":"2.0","id":7,"id":8,"method":"tools/list","params":{}}'
        assert (await lab.post(client, None, headers, content=duplicate)).status_code == 400
        large = json.dumps({**body, "pad": "x" * mcp_gateway.BODY_LIMIT}).encode()
        assert (await lab.post(client, None, headers, content=large)).status_code == 413
        assert (await lab.post(client, body, {**headers, "content-type": "text/plain"})).status_code == 415
        assert (await lab.post(client, body, {**headers, "content-encoding": "gzip"})).status_code == 415
        token = lab.token()
        assert (await client.post("/mcp?x=1", json=body, headers={
            **headers, "authorization": f"DPoP {token}", "dpop": lab.signer.sign(MCP_RESOURCE, token)})).status_code == 400
        # Values Python can read but cannot write back out: refused as malformed, never a crash.
        for unsendable in (b'{"jsonrpc":"2.0","id":"\\ud800","method":"tools/list","params":{}}',
                           b'{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"lab_echo",'
                           b'"arguments":{"text":1e400},"_meta":{}}}',
                           b'{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"lab_echo",'
                           b'"arguments":{"text":"\\udc00"},"_meta":{}}}'):
            refused = await lab.post(client, None, headers, content=unsendable)
            assert refused.status_code == 400 and refused.content == b""
        assert (await lab.post(client, body, {**headers, "origin": "https://127.0.0.1:8083"})).status_code == 403
        for method in ("GET", "DELETE", "PUT"):
            assert (await client.request(method, "/mcp")).status_code == 405
        assert not lab.sent

    lab.run(check)


def in_small_chunks(request):
    # Too large only in total: no single piece is over the limit.
    padded = json.dumps({**GOOD, "result": {**GOOD["result"], "content": [
        {"type": "text", "text": "x" * mcp_gateway.REPLY_LIMIT}]}}).encode()
    pieces = [padded[start:start + 65536] for start in range(0, len(padded), 65536)]
    return httpx.Response(200, stream=Bytes(*pieces), headers={"content-type": "application/json"})


def fake(result=None, **overrides):
    def respond(request):
        data = {"jsonrpc": "2.0", "id": 1,
                "result": {"resultType": "complete", "content": [], "isError": False, **(result or {})}}
        data.update(overrides)
        return reply({key: value for key, value in data.items() if value is not None})
    return respond


GOOD = {"jsonrpc": "2.0", "id": 1, "result": {"resultType": "complete", "content": [], "isError": False}}


def stream(request):
    # A reply that would be acceptable as JSON, sent as a stream.
    return httpx.Response(200, stream=Bytes(json.dumps(GOOD).encode()),
                          headers={"content-type": "text/event-stream"})


def oversized(request):
    # A well-formed reply that is only too large.
    padded = {**GOOD, "result": {**GOOD["result"], "content": [{"type": "text", "text": "x" * mcp_gateway.REPLY_LIMIT}]}}
    return httpx.Response(200, stream=Bytes(json.dumps(padded).encode()), headers={"content-type": "application/json"})


@pytest.mark.parametrize(("respond", "status"), [
    (stream, 502),
    (fake({"resultType": "input_required", "inputRequests": {"a": {"method": "elicitation/create"}}}), 502),
    (fake({"resultType": "task", "task": {"taskId": "1"}}), 502),
    (fake({"resultType": None}), 502),
    (fake({"content": "text"}), 502),
    (fake({"isError": "no"}), 502),
    (fake({"structuredContent": []}), 502),
    (fake(id=2), 502),
    (fake(id=True), 502),
    (fake(result=None, error={"code": -32603, "message": "Internal error"}), 502),
    (fake(extra="field"), 502),
    (lambda request: httpx.Response(500, json={}), 502),
    (lambda request: httpx.Response(200, stream=Bytes(b"{not json"), headers={"content-type": "application/json"}), 502),
    (lambda request: httpx.Response(200, stream=Bytes(b"[]"), headers={"content-type": "application/json"}), 502),
    (oversized, 502),
    (in_small_chunks, 502),
    (fake(jsonrpc="1.0"), 502),
    (fake({"content": [1, "x", None]}), 502),
    (lambda request: httpx.Response(200, stream=Bytes(
        b'{"jsonrpc":"2.0","id":1,"result":{"resultType":"complete","content":[{"type":"text","text":1e400}]}}'),
        headers={"content-type": "application/json"}), 502),
    (lambda request: httpx.Response(200, stream=Bytes(
        b'{"jsonrpc":"2.0","id":1,"result":{"resultType":"complete","content":[{"type":"text","text":"\\udc00"}]}}'),
        headers={"content-type": "application/json"}), 502),
    (lambda request: httpx.Response(200, stream=Bytes(json.dumps(GOOD).encode()),
                                    headers={"content-type": "application/json", "content-encoding": "gzip"}), 502),
    (lambda request: (_ for _ in ()).throw(httpx.ConnectError("refused")), 502),
    (lambda request: (_ for _ in ()).throw(httpx.ReadTimeout("slow")), 504),
])
def test_refuses_tool_server_replies_it_cannot_vouch_for(lab, respond, status):
    lab.fake = respond

    async def check(client):
        refused = await lab.post(client, *call("lab_echo", {"text": "x"}))
        assert refused.status_code == status and refused.content == b""
        assert len(lab.sent) == 1

    lab.run(check)


def test_a_tool_list_keeps_only_allowed_tools_and_the_page_marker(lab):
    lab.fake = fake({"tools": [{"name": "lab_add"}, {"name": "lab_echo", "description": "kept"},
                               {"name": "another"}], "nextCursor": "page-2", "cacheScope": "public",
                     "ttlMs": 60000, "_meta": {"upstream": "detail"}})

    async def check(client):
        listed = await lab.post(client, *rpc("tools/list", {"cursor": "page-1", "unexpected": "dropped"}))
        assert listed.json()["result"] == {
            "resultType": "complete", "tools": [{"name": "lab_echo", "description": "kept"}],
            "nextCursor": "page-2", "ttlMs": 0, "cacheScope": "private"}
        assert json.loads(lab.sent[0].content)["params"] == {
            "cursor": "page-1", "_meta": {mcp_gateway.PROTOCOL_VERSION: VERSION, mcp_gateway.CAPABILITIES: {}}}
        lab.fake = fake({"tools": [{"name": 5}]})
        assert (await lab.post(client, *rpc("tools/list"))).status_code == 502
        lab.fake = fake({"tools": [{"name": "lab_echo"}, {"name": "lab_echo"}]})
        assert (await lab.post(client, *rpc("tools/list"))).status_code == 502
        # A call forwards its name and arguments and nothing else the caller added.
        lab.fake, before = fake(), len(lab.sent)
        body, headers = call("lab_echo", {"text": "x", "name": "lab_add"})
        body["params"].update({"cursor": "c", "task": {"ttl": 1}, "unexpected": "dropped"})
        assert (await lab.post(client, body, headers)).status_code == 200
        assert json.loads(lab.sent[before].content)["params"] == {
            "name": "lab_echo", "arguments": {"text": "x", "name": "lab_add"},
            "_meta": {mcp_gateway.PROTOCOL_VERSION: VERSION, mcp_gateway.CAPABILITIES: {}}}
        lab.fake = fake({"tools": [], "nextCursor": 5})
        assert (await lab.post(client, *rpc("tools/list"))).status_code == 502

    lab.run(check)


def test_the_deadline_applies_to_the_tool_server(lab, monkeypatch):
    monkeypatch.setattr(mcp_gateway, "DEADLINE", 0.05)
    closed = []

    class Slow(httpx.AsyncByteStream):
        async def __aiter__(self):
            await asyncio.sleep(5)
            yield b"{}"

        async def aclose(self):
            closed.append(True)

    lab.fake = lambda request: httpx.Response(200, stream=Slow(), headers={"content-type": "application/json"})

    async def check(client):
        assert (await lab.post(client, *call("lab_echo", {"text": "x"}))).status_code == 504

    lab.run(check)
    assert closed == [True]


def test_a_caller_that_disconnects_closes_the_tool_server_request(lab, caplog):
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    started, closed = asyncio.Event(), []

    class Waiting(httpx.AsyncByteStream):
        async def __aiter__(self):
            started.set()
            await asyncio.sleep(30)
            yield b"{}"

        async def aclose(self):
            closed.append(True)

    lab.fake = lambda request: httpx.Response(200, stream=Waiting(), headers={"content-type": "application/json"})

    async def check(client):
        assert (await lab.post(client, *rpc("server/discover"))).status_code == 200
        token = lab.token()
        body, headers = call("lab_echo", {"text": "x"})
        raw = json.dumps(body).encode()
        headers = {**headers, "host": "127.0.0.1:8083", "content-type": "application/json",
                   "authorization": f"DPoP {token}", "dpop": lab.signer.sign(MCP_RESOURCE, token)}
        scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST",
                 "scheme": "https", "path": "/mcp", "raw_path": b"/mcp", "query_string": b"", "root_path": "",
                 "client": ("127.0.0.1", 50000), "server": ("127.0.0.1", 8083),
                 "headers": [(key.lower().encode(), value.encode()) for key, value in headers.items()]}
        events = asyncio.Queue()
        events.put_nowait({"type": "http.request", "body": raw, "more_body": False})
        replies = []

        async def send(event):
            replies.append(event)

        handler = asyncio.create_task(lab.app(scope, events.get, send))
        async with asyncio.timeout(5):
            await started.wait()
            events.put_nowait({"type": "http.disconnect"})
            await handler

    lab.run(check)
    assert closed == [True]
    assert "event=client_disconnected" in caplog.text


def test_metadata_is_public_and_says_dpop_is_required(lab):
    async def check(client):
        response = await client.get("/.well-known/oauth-protected-resource/mcp")
        assert response.status_code == 200
        assert response.json() == {
            "resource": "https://127.0.0.1:8083/mcp", "authorization_servers": ["https://127.0.0.1:8081"],
            "scopes_supported": ["mcp:invoke"], "bearer_methods_supported": [],
            "dpop_bound_access_tokens_required": True, "dpop_signing_alg_values_supported": ["ES256"]}
        assert mcp_gateway.METADATA == "https://127.0.0.1:8083/.well-known/oauth-protected-resource/mcp"

    lab.run(check)


def test_an_unprintable_subject_is_not_written_to_the_log(lab, caplog):
    caplog.set_level(logging.INFO, logger="uvicorn.error")

    async def check(client):
        assert (await lab.post(client, *rpc("server/discover"))).status_code == 200
        token = lab.token(sub="line one\nmcp_gateway event=forged")
        assert (await lab.post(client, *rpc("server/discover"), token=token)).status_code == 200

    lab.run(check)
    assert "subject=unprintable" in caplog.text and "forged" not in caplog.text


def test_tool_policy_file(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps({"tools": {SUBJECT: ["lab_echo"], "another.user_2": []}}))
    assert mcp_gateway.load_tool_policy(path) == {SUBJECT: frozenset({"lab_echo"}), "another.user_2": frozenset()}
    for invalid in ('[]', '{}', '{"tools": []}', '{"tools": {}, "extra": 1}',
                    '{"tools": {"user": "lab_echo"}}', '{"tools": {"user": ["lab echo"]}}',
                    '{"tools": {"user": ["lab_echo", "lab_echo"]}}', '{"tools": {"user": [5]}}',
                    '{"tools": {"bad user": []}}', '{"tools": {"user": ["a\\nb"]}}',
                    '{"tools": {"user": []}, "tools": {}}', '{"tools": {"user": ["' + "x" * 129 + '"]}}', 'not json'):
        path.write_text(invalid)
        with pytest.raises(Exception) as refused:
            mcp_gateway.load_tool_policy(path)
        assert isinstance(refused.value, (ValueError, gateway.FoundationError)), invalid


def test_will_not_start_without_dpop_a_policy_or_a_credential(tmp_path, monkeypatch, capsys):
    nonce = tmp_path / "nonce.key"
    for options in ({"dpop_nonce_key": None, "dpop_replay_dir": tmp_path},
                    {"dpop_nonce_key": nonce, "dpop_replay_dir": None}):
        with pytest.raises(ValueError):
            mcp_gateway.create_app(certifi.where(), UPSTREAM_SECRET, {}, **options)
    for credential in ("", "x" * 21, "has spaces in it and is long enough"):
        with pytest.raises(ValueError):
            mcp_gateway.create_app(certifi.where(), credential, {}, dpop_nonce_key=nonce, dpop_replay_dir=tmp_path)
    policy = tmp_path / "policy.json"
    policy.write_text('{"tools": {"user": "everything"}}')
    monkeypatch.setenv("MCP_GATEWAY_UPSTREAM_TOKEN", UPSTREAM_SECRET)
    monkeypatch.setattr("sys.argv", [
        "mcp_gateway.py", "--as-ca", certifi.where(), "--tls-cert", "unused", "--tls-key", "unused",
        "--dpop-nonce-key", str(nonce), "--dpop-replay-dir", str(tmp_path), "--tool-policy", str(policy)])
    with pytest.raises(SystemExit) as stopped:
        mcp_gateway.main()
    assert stopped.value.code == 1 and UPSTREAM_SECRET not in capsys.readouterr().err


def tool_server(request):
    sent = json.loads(request.content)
    if sent["method"] == "tools/list":
        return fake({"tools": [{"name": "lab_echo"}, {"name": "lab_add"}]})(request)
    return fake({"content": [{"type": "text", "text": sent["params"]["arguments"]["text"]}]})(request)


def test_the_lab_probe_passes_only_when_the_gateway_hides_the_right_tool(tmp_path):
    for number, (tools, passes) in enumerate(((["lab_echo"], True), (["lab_echo", "lab_add"], False), ([], False))):
        directory = tmp_path / str(number)
        directory.mkdir()
        lab = Lab(directory, {SUBJECT: frozenset(tools)})
        lab.fake = tool_server
        with TestClient(lab.app, base_url="https://127.0.0.1:8083") as client:
            if passes:
                mcp_probe(client, lab.token(), lab.signer)
                assert [json.loads(request.content)["method"] for request in lab.sent] == ["tools/list", "tools/call"]
            else:
                with pytest.raises(ValueError):
                    mcp_probe(client, lab.token(), lab.signer)


def test_refuses_a_request_that_did_not_arrive_over_https(lab):
    async def check(client):
        assert (await lab.post(client, *rpc("server/discover"))).status_code == 200
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=lab.app),
                                     base_url="http://127.0.0.1:8083") as plain:
            refused = await lab.post(plain, *rpc("server/discover"))
        assert refused.status_code == 401 and "invalid_dpop_proof" in refused.headers["www-authenticate"]

    lab.run(check)


class Canned:
    """Stands in for the MCP gateway, to show each of the probe's own checks can fail."""

    def __init__(self, **changes):
        self.replies = {
            "server/discover": {"result": {"capabilities": {"tools": {}}}},
            "tools/list": {"result": {"tools": [{"name": "lab_echo"}], "cacheScope": "private"}},
            "lab_echo": {"result": {"content": [{"type": "text", "text": "MCP_OK"}]}},
            "lab_add": {"error": {"code": -32602, "message": "Unknown tool"}},
            **changes}

    def post(self, url, json, headers):
        assert url == MCP_RESOURCE and headers["Mcp-Method"] == json["method"]
        return httpx.Response(200, json=self.replies[json["params"].get("name", json["method"])],
                              request=httpx.Request("POST", url))


@pytest.mark.parametrize("changes", [
    {"server/discover": {"result": {"capabilities": {"tools": {}, "prompts": {}}}}},
    {"tools/list": {"result": {"tools": [{"name": "lab_echo"}, {"name": "lab_add"}], "cacheScope": "private"}}},
    {"tools/list": {"result": {"tools": [{"name": "lab_echo"}], "cacheScope": "public"}}},
    {"lab_echo": {"result": {"content": [{"type": "text", "text": "something else"}]}}},
    {"lab_add": {"result": {"content": [{"type": "text", "text": "3"}]}}},
    {"lab_add": {"error": {"code": -32602, "message": "Unknown tool: lab_add"}}},
])
def test_each_of_the_probes_checks_can_fail(changes):
    mcp_probe(Canned(), "token", ProofClient())
    with pytest.raises(ValueError):
        mcp_probe(Canned(**changes), "token", ProofClient())
