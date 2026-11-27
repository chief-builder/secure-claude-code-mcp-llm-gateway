# Intent: mcp-tokens

Release: 0.3.0 · Roadmap line: mcp-tokens · Capability: MCP gateway

**Problem.** The authorization server issues exactly one kind of access token: for
the LLM gateway, with the scope `llm:invoke`. The MCP gateway planned in
[decision 0003](../../../decisions/0003-mcp-through-the-broker-with-its-own-tokens.md)
needs its own kind, so that a token for model calls cannot be used for tools and a
token for tools cannot be used for model calls. Without that separation a single
stolen or misrouted token would open both.

**Why now.** It is the first building block of the MCP gateway: the mock server,
the gateway and the broker's MCP endpoint all need a token to check or present.

**Success looks like.** From one sign-in, the broker can obtain a model token and an
MCP token, each bound to its DPoP key, each naming only its own gateway. The LLM
gateway refuses the MCP token. Everything that works today works unchanged.

**Constraints.** This changes the authorization server's token exchange, an
accepted security module: the plan needs the owner's approval and the task closes
with a live lab run. Existing exchange policies must keep working without edits, and
must not start issuing MCP tokens just because the code was updated.
