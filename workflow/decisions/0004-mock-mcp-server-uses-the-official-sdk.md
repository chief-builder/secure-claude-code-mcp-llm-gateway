# ADR-0004: The mock MCP server is built with the official SDK; the gateway is written by hand

Date: 2026-11-27
Status: **accepted**

**Context.** The MCP gateway needs a tool server behind it to forward to and to be
tested against. It could be written by hand on the web framework the lab already
uses, or built with the official MCP Python SDK. The lab pins every dependency and,
as a security reference, prefers checks it can point to in its own code.

**Decision.** Build the mock server with the official MCP Python SDK, pinned at
2.3.0. Keep the gateway hand-written.

**Alternatives considered.**

- A hand-written mock: no new dependency and every refusal ours to state. It lost
  because the same author would then write both sides of the conversation, and a
  misreading of the protocol would appear on both and pass every test.
- The standalone `fastmcp` package: a separate, larger project that brings
  integrations for several AI providers. The official SDK already contains the same
  style of server, which is where the original FastMCP went.
- The SDK for the gateway too: the gateway must do things the SDK is not built for,
  namely check DPoP-bound tokens, apply per-user rules and relay to another server,
  and it is the security boundary, where the lab wants its own strict checks.

**Consequences.**

- The gateway is tested against an independent implementation of the protocol. A
  trial run and the verification after it already showed one place where the SDK
  departs from the protocol's text (an unknown tool) and several things the
  protocol permits but the lab does not want, the most serious being that the SDK
  compares headers with body only when the request's header names the current
  revision. Each is pinned by a test and becomes a rule the gateway must enforce
  itself.
- Twelve more pinned packages are installed. Only the mock uses them, and none is on
  the path that issues or checks tokens.
- The mock LLM's tests now run on `httpx2`, which the SDK brings, instead of the
  pinned `httpx`, because the test client prefers it when installed.
- The mock's behavior is partly the SDK's. An SDK upgrade can change it; the tests
  exist to make such a change visible.
- The gateway's tests will still need small hand-made stand-ins for the malformed
  upstream replies a well-behaved SDK server never produces.
