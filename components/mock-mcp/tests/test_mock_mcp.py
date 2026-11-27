"""Pins how the SDK-built mock behaves, so an SDK upgrade that changes it is noticed.

Where the SDK is looser than the MCP specification's text, the test says so. The
gateway, not this mock, is responsible for being strict.
"""

import asyncio
import base64

import httpx
import pytest

import mock_mcp

CREDENTIAL = "synthetic_mock_mcp_credential"
VERSION = "2026-07-28"
META = {"io.modelcontextprotocol/protocolVersion": VERSION,
        "io.modelcontextprotocol/clientCapabilities": {}}


def message(method, params=None, *, name=None, headers=None, meta=META):
    """A request shaped as revision 2026-07-28 requires, with optional deviations."""
    body = {"jsonrpc": "2.0", "id": 1, "method": method,
            "params": {**(params or {}), **({"_meta": meta} if meta is not None else {})}}
    sent = {"Authorization": f"Bearer {CREDENTIAL}", "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": VERSION, "Mcp-Method": method}
    if name is not None:
        sent["Mcp-Name"] = name
    sent.update(headers or {})
    return {"json": body, "headers": {key: value for key, value in sent.items() if value is not None}}


def call(tool, arguments, **options):
    return message("tools/call", {"name": tool, "arguments": arguments}, name=tool, **options)


def run(check):
    async def session():
        app = mock_mcp.create_app(CREDENTIAL)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                         base_url="http://127.0.0.1:8767") as client:
                await check(client)
    asyncio.run(session())


def error_of(response):
    return response.status_code, response.json()["error"]["code"]


def test_discover_and_tool_list_carry_the_required_fields():
    async def check(client):
        discovered = (await client.post("/mcp", **message("server/discover"))).json()["result"]
        assert discovered["resultType"] == "complete"
        assert discovered["supportedVersions"] == [VERSION]
        assert "tools" in discovered["capabilities"]
        assert discovered["cacheScope"] in ("public", "private") and discovered["ttlMs"] >= 0
        assert discovered["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "lab-mock-mcp"

        response = await client.post("/mcp", **message("tools/list"))
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        listed = response.json()["result"]
        assert listed["resultType"] == "complete"
        # The same for every caller, so anyone may cache it.
        assert (listed["cacheScope"], listed["ttlMs"]) == ("public", 60_000)
        assert [tool["name"] for tool in listed["tools"]] == ["lab_echo", "lab_add"]
        echo, add = listed["tools"]
        assert echo["inputSchema"]["required"] == ["text"]
        assert add["inputSchema"]["properties"]["a"]["type"] == "integer"
        assert sorted(add["inputSchema"]["required"]) == ["a", "b"]

    run(check)


def test_tools_return_their_results():
    async def check(client):
        echoed = (await client.post("/mcp", **call("lab_echo", {"text": "hello lab"}))).json()["result"]
        assert (echoed["resultType"], echoed["isError"]) == ("complete", False)
        assert echoed["content"] == [{"type": "text", "text": "hello lab"}]
        added = (await client.post("/mcp", **call("lab_add", {"a": 2, "b": 40}))).json()["result"]
        assert added["content"] == [{"type": "text", "text": "42"}] and added["isError"] is False

    run(check)


def test_bad_arguments_are_a_result_flagged_as_an_error():
    async def check(client):
        response = await client.post("/mcp", **call("lab_add", {"a": "not a number"}))
        assert response.status_code == 200
        result = response.json()["result"]
        assert result["isError"] is True and result["resultType"] == "complete"

    run(check)


def test_tool_name_header_must_match_the_body():
    async def check(client):
        named = call("lab_echo", {"text": "x"})
        encoded = "=?base64?" + base64.b64encode(b"lab_echo").decode() + "?="
        assert (await client.post("/mcp", **call("lab_echo", {"text": "x"}, headers={"Mcp-Name": encoded}))).status_code == 200
        assert (await client.post("/mcp", **named)).status_code == 200
        for wrong in ("lab_add", None, "LAB_ECHO"):
            refused = await client.post("/mcp", **call("lab_echo", {"text": "x"}, headers={"Mcp-Name": wrong}))
            assert error_of(refused) == (400, -32020)

    run(check)


def test_refusals_the_specification_defines():
    async def check(client):
        for wrong in ("tools/call", None):
            mismatch = await client.post("/mcp", **message("tools/list", headers={"Mcp-Method": wrong}))
            assert error_of(mismatch) == (400, -32020)
        # Subscriptions are switched off, so the one streaming method does not exist.
        async with asyncio.timeout(5):
            listen = await client.post("/mcp", **message(
                "subscriptions/listen", {"notifications": {"toolsListChanged": True}}))
        assert error_of(listen) == (404, -32601)
        old = {**META, "io.modelcontextprotocol/protocolVersion": "1900-01-01"}
        unsupported = await client.post("/mcp", **message(
            "tools/list", meta=old, headers={"MCP-Protocol-Version": "1900-01-01"}))
        assert error_of(unsupported) == (400, -32022)
        assert unsupported.json()["error"]["data"] == {"supported": [VERSION], "requested": "1900-01-01"}
        assert error_of(await client.post("/mcp", **message("tools/list", meta=None))) == (400, -32602)
        assert error_of(await client.post("/mcp", **message("no/such-method"))) == (404, -32601)
        credential = {"Authorization": f"Bearer {CREDENTIAL}"}
        assert (await client.request("DELETE", "/mcp", headers=credential)).status_code == 405
        # GET is refused only when the request names the current revision.
        refused = await client.get("/mcp", headers={**credential, "MCP-Protocol-Version": VERSION})
        assert (refused.status_code, refused.headers["allow"]) == (405, "POST")
        foreign = await client.post("/mcp", **message("tools/list", headers={"Origin": "https://elsewhere.example"}))
        assert foreign.status_code == 403

    run(check)


def test_what_the_gateway_must_not_rely_on_the_mock_for():
    """One departure from the specification, then behavior it permits but the lab does not want."""
    async def check(client):
        # The departure: the specification describes a JSON-RPC "unknown tool" error (-32602).
        unknown = await client.post("/mcp", **call("no_such_tool", {}))
        assert unknown.status_code == 200
        assert unknown.json()["result"]["isError"] is True
        assert "Unknown tool" in unknown.json()["result"]["content"][0]["text"]

        # It also speaks the older revisions: a request whose header names one, or
        # omits it, is served under the older rules even though its body says 2026-07-28.
        for header in ("2025-11-25", None):
            served = await client.post("/mcp", **message("tools/list", headers={"MCP-Protocol-Version": header}))
            assert served.status_code == 200
            assert "resultType" not in served.json()["result"]
        handshake = await client.post("/mcp", headers={
            "Authorization": f"Bearer {CREDENTIAL}", "Accept": "application/json, text/event-stream"}, json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}})
        assert handshake.status_code == 200 and handshake.json()["result"]["protocolVersion"] == "2025-11-25"

        # It says it offers prompts and resources, and answers for them, with only tools registered.
        capabilities = (await client.post("/mcp", **message("server/discover"))).json()["result"]["capabilities"]
        assert capabilities == {"prompts": {"listChanged": False}, "tools": {"listChanged": False},
                                "resources": {"listChanged": False, "subscribe": False}}
        for method, key in (("prompts/list", "prompts"), ("resources/list", "resources"),
                            ("resources/templates/list", "resourceTemplates")):
            assert (await client.post("/mcp", **message(method))).json()["result"][key] == []

    run(check)


def test_headers_and_body_are_compared_only_under_the_current_revision():
    """The attack the headers invite: they name one tool, the body runs another.

    The mock refuses it only when the request's revision header says 2026-07-28, so
    the gateway must send that header upstream as well as require it from its caller.
    """
    async def check(client):
        disguise = {"Mcp-Method": "tools/list", "Mcp-Name": "lab_echo"}
        refused = await client.post("/mcp", **call("lab_add", {"a": 1, "b": 2}, headers=disguise))
        assert error_of(refused) == (400, -32020)
        for header in ("2025-11-25", None):
            ran = await client.post("/mcp", **call(
                "lab_add", {"a": 1, "b": 2}, headers={**disguise, "MCP-Protocol-Version": header}))
            assert ran.status_code == 200
            assert ran.json()["result"]["content"] == [{"type": "text", "text": "3"}]

    run(check)


def test_get_without_the_current_revision_header_opens_a_stream():
    """An older-revision feature: the gateway must forward POST only."""
    async def session():
        app = mock_mcp.create_app(CREDENTIAL)
        scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET",
                 "scheme": "http", "path": "/mcp", "raw_path": b"/mcp", "query_string": b"", "root_path": "",
                 "client": ("127.0.0.1", 50000), "server": ("127.0.0.1", 8767), "headers": [
                     (b"host", b"127.0.0.1:8767"), (b"accept", b"text/event-stream"),
                     (b"authorization", f"Bearer {CREDENTIAL}".encode())]}
        started = asyncio.get_running_loop().create_future()
        requests = asyncio.Queue()
        requests.put_nowait({"type": "http.request", "body": b"", "more_body": False})

        async def send(event):
            if event["type"] == "http.response.start":
                started.set_result(event)

        async with app.router.lifespan_context(app):
            stream = asyncio.create_task(app(scope, requests.get, send))
            async with asyncio.timeout(5):
                start = await started
            assert start["status"] == 200
            assert dict(start["headers"])[b"content-type"].startswith(b"text/event-stream")
            await asyncio.sleep(0.2)
            assert not stream.done()
            stream.cancel()
            await asyncio.gather(stream, return_exceptions=True)

    asyncio.run(session())


@pytest.mark.parametrize("authorization", [
    None, "", "Bearer", "Bearer wrong_credential_wrong_credential", f"bearer {CREDENTIAL}",
    f"Basic {CREDENTIAL}", f"Bearer {CREDENTIAL} ", f"Bearer {CREDENTIAL}x", CREDENTIAL,
])
def test_requests_without_the_credential_never_reach_the_sdk(authorization, monkeypatch):
    reached = []
    original = mock_mcp.build_server

    def watched():
        server = original()

        @server.tool()
        def lab_canary() -> str:
            """Records that the SDK ran a tool."""
            reached.append(True)
            return "ran"

        return server

    monkeypatch.setattr(mock_mcp, "build_server", watched)

    async def check(client):
        for request in (call("lab_canary", {}), message("tools/list"), message("server/discover")):
            response = await client.post("/mcp", **{**request, "headers": {
                **request["headers"], "Authorization": authorization}} if authorization is not None else {
                **request, "headers": {k: v for k, v in request["headers"].items() if k != "Authorization"}})
            assert response.status_code == 401
            assert response.headers["www-authenticate"] == "Bearer" and response.content == b""
        assert not reached
        assert (await client.post("/mcp", **call("lab_canary", {}))).status_code == 200
        assert reached == [True]

    run(check)


@pytest.mark.parametrize("method", ["GET", "DELETE", "OPTIONS", "HEAD", "PUT"])
def test_every_http_method_needs_the_credential(method):
    async def check(client):
        async with asyncio.timeout(5):
            assert (await client.request(method, "/mcp")).status_code == 401

    run(check)


def test_two_authorization_headers_are_refused():
    async def check(client):
        request = message("tools/list")
        headers = [(key, value) for key, value in request["headers"].items()] + [
            ("Authorization", f"Bearer {CREDENTIAL}")]
        response = await client.post("/mcp", json=request["json"], headers=headers)
        assert response.status_code == 401

    run(check)


def test_starts_with_the_shortest_and_longest_credential_allowed():
    mock_mcp.create_app("x" * 22)
    mock_mcp.create_app("x" * 128)


@pytest.mark.parametrize("credential", ["", "x" * 21, "has spaces in it and is long enough", "x" * 129])
def test_refuses_to_start_without_a_usable_credential(credential, monkeypatch):
    with pytest.raises(ValueError):
        mock_mcp.create_app(credential)
    monkeypatch.setenv("MOCK_MCP_TOKEN", credential)
    with pytest.raises(SystemExit):
        mock_mcp.main()
