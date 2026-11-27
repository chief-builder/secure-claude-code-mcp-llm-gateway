# Intent: mcp-gateway

Date: 2026-11-27
Playbook: feature
Roadmap line: mcp-gateway (capability: MCP gateway)

**What is wanted.** The MCP gateway itself: a service that stands between a caller
holding a DPoP-bound MCP token and a tool server, decides per user which tools may
be seen and called, and forwards allowed calls with its own credential.

**Why.** It is the piece the project's name promises and nothing yet provides. The
authorization server can already issue MCP tokens and the mock tool server exists;
nothing checks one before reaching the other.

**Who it is for.** Readers who want to see how sender-constrained tokens and
per-tool rules can be put in front of MCP tool servers.

**Done looks like.** A test client signs in as the synthetic user, obtains an MCP
token, and through the gateway lists only the tools that user is allowed, calls an
allowed tool and gets its result, and is refused a tool that exists but is not
allowed, in a way that does not reveal it exists. A model token, a replayed proof
and a request whose headers disagree with its body are each refused.

**Constraints.** The design is fixed by
[decision 0003](../../../decisions/0003-mcp-through-the-broker-with-its-own-tokens.md)
and the rules learned from the mock server, listed in the roadmap. This task reuses
token validation and DPoP checking, so both the spec and the plan need the owner's
approval, each security check must be shown to be tested, and a live lab run closes
the task. Claude Code is not connected in this task; that is `broker-mcp-endpoint`.
