# Mock MCP tool server

## What it is

A stand-in for a real tool server. It speaks the Model Context Protocol (MCP),
revision 2026-07-28, and offers two harmless tools: `lab_echo` returns the text it is
given, and `lab_add` adds two whole numbers. It is what the MCP gateway will sit in
front of, so the gateway can be built and tested without real tools or real
credentials. It is built with the official MCP Python SDK, so the gateway is tested
against an independent implementation of the protocol and not against the lab's own
reading of it.

## Run it

Run `uv sync` once at the repository root. The server refuses to start without a
credential of at least 22 letters, digits, hyphens or underscores:

```sh
export MOCK_MCP_TOKEN="$(uv run python -c 'import secrets; print(secrets.token_urlsafe(32))')"
uv run python mock_mcp.py
```

It listens on `http://127.0.0.1:8767/mcp`. In another terminal, with the same
`MOCK_MCP_TOKEN` exported, call a tool:

```sh
curl --silent http://127.0.0.1:8767/mcp \
  -H "Authorization: Bearer $MOCK_MCP_TOKEN" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'MCP-Protocol-Version: 2026-07-28' \
  -H 'Mcp-Method: tools/call' -H 'Mcp-Name: lab_add' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"lab_add","arguments":{"a":2,"b":40},"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{}}}}' && echo
```

The reply's text is `42`. The request names its protocol revision, its method and
its tool both in headers and in the body, as the protocol requires;
[the shape of an MCP request](../../docs/concepts/mcp-request.md) explains why.

To see Claude Code connect to it directly, with no gateway in between, give it the
address and the credential as a header. Claude Code then lists `lab_echo` and
`lab_add` among its tools. This starts Claude Code with whatever model access you
normally use; the check recorded for this component used the
[mock model](../mock-llm/README.md) instead:

```sh
claude --mcp-config "{\"mcpServers\":{\"lab\":{\"type\":\"http\",\"url\":\"http://127.0.0.1:8767/mcp\",\"headers\":{\"Authorization\":\"Bearer $MOCK_MCP_TOKEN\"}}}}"
```

The [MCP gateway](../gateway/README-mcp.md) sits in front of this server; its README
shows how to run the two together.

## Test it

```sh
uv run python -m pytest -q
```

Expect 28 passed. All tests run offline.

## How it works

- [`mock_mcp.py`](mock_mcp.py) builds the SDK server, registers the two tools, and
  puts one check in front of it: a request without the shared credential is refused
  with 401 before the SDK sees it.
- [`tests/test_mock_mcp.py`](tests/test_mock_mcp.py) pins how the SDK answers
  correct and malformed requests, so an SDK upgrade that changes its behavior is
  noticed.
- [The shape of an MCP request](../../docs/concepts/mcp-request.md), with a diagram.
- [Why the mock uses the SDK](../../workflow/decisions/0004-mock-mcp-server-uses-the-official-sdk.md)
  and the gateway does not.

## Limits

- Tools only, and only these two. It keeps no sessions and replies with a single
  JSON object.
- Its credential is a secret shared with whoever calls it, on loopback, like the
  mock LLM's. It is not MCP's own OAuth-based authorization.
- An unknown tool is answered with a result flagged as an error, where the MCP
  specification describes an "unknown tool" error. This is the SDK's behavior.
- The SDK also serves clients built for older revisions of MCP, and picks the rules
  from the `MCP-Protocol-Version` header alone. Without the value `2026-07-28` in
  that header it does not compare the headers with the body, and `GET` opens a
  long-lived stream. It also says it offers prompts and resources. The specification
  permits all of this; the gateway has to be strict about each itself, and has to
  send the header on what it forwards. Each behavior is pinned by a test.
- The SDK's subscriptions are switched off, so nothing here streams under the
  current revision.
- It listens on plain HTTP and is meant for loopback only.
