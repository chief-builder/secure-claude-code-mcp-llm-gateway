# Intent: mock-mcp-server

Release: 0.3.0 · Roadmap line: mock-mcp-server · Capability: MCP gateway

**Problem.** The MCP gateway needs something behind it: a tool server that speaks
MCP. Real tool servers need real credentials and real data, which the lab forbids.
The lab solved the same problem for the model with a mock LLM; there is no
equivalent for tools.

**Why now.** It is the next building block after MCP tokens. The gateway cannot be
built or tested without a server to forward to, and its per-tool rules can only be
shown if there are at least two tools to tell apart.

**Success looks like.** A small server that the installed Claude Code can connect
to directly and list two harmless tools from, that answers correctly formed requests
and refuses malformed ones the way the MCP specification says, and that the gateway
task can run in-process in its tests.

**Constraints.** MCP revision 2026-07-28 only. Harmless, deterministic tools with no
access to files, the network or the system. Loopback only. It must not weaken or
depend on any accepted security module.
