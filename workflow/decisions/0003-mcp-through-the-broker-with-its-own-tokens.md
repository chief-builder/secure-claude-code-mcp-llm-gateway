# ADR-0003: MCP traffic goes through the broker, with its own DPoP-bound tokens and per-tool rules

Date: 2026-11-26
Status: **accepted**

**Context.** The project's name promises an MCP gateway and nothing implements one.
MCP lets Claude Code call tools on remote servers. Those servers need to know who is
calling, and whatever credentials they need for the systems behind them should not
sit on a laptop, for the same reasons AWS credentials should not.

Claude Code can sign in to a remote MCP server itself with standard OAuth, and can
attach fixed or helper-generated headers when it connects. Its documentation does
not mention DPoP, and a helper runs once per connection, not once per request. So a
token Claude Code obtains or attaches on its own is a bearer token: whoever copies
it can use it.

**Decision.**

- Claude Code speaks MCP to the local broker. The broker adds a DPoP-bound access
  token and a fresh proof to every request and forwards it to an MCP gateway, the
  same pattern as model calls.
- MCP tokens are separate from model tokens: their own audience and scope, issued by
  the same authorization server through the same token exchange. A model token is
  refused by the MCP gateway and the reverse.
- The MCP gateway enforces rules per tool from the first version: a policy says
  which tools each user may call; tools a user may not call are left out of the list
  the user sees and refused if called anyway.
- The gateway holds whatever credential the tool server needs. In the lab the tool
  server is a mock with harmless tools.
- It is built for the local lab first, on loopback like every other component.

**Alternatives considered.**

- Claude Code's built-in MCP sign-in straight to the gateway: standard and needs no
  broker, but yields bearer tokens, which is the weakness this project exists to
  remove.
- Both paths: more to build, and two security levels to explain in one reference.
- One scope for all tools first, per-tool rules later: smaller, but the owner wants
  the control a company would actually need from the start.
- Waiting for the AWS host: would put MCP behind the AWS work for no technical
  reason.

**Consequences.**

- The broker stops being model-only and gains a second local listener. It also has
  to launch Claude Code with tools enabled and an MCP configuration, where today it
  disables both.
- The authorization server must issue tokens for a second audience and scope. That
  is a change to an accepted security module.
- The MCP gateway reuses the token and DPoP checks the LLM gateway uses, which makes
  the shared code more important and the packaging work on the backlog more useful.
- An ordinary MCP client that does not go through the broker cannot use this
  gateway. Publishing standard MCP discovery metadata for such clients is not
  planned.
- Three stages are wanted, each a step further end to end: a test client calling a
  tool and Claude Code listing it; a scripted mock model that makes Claude Code
  really call the tool; and a real model on Bedrock choosing to call it. The third
  needs tool-use support in the Bedrock adapter, which is text-only today, and paid
  AWS time.

**Not yet verified, to settle when the first build task is specified.** Which
revision of the MCP specification to target, and what it says about sessions and
streaming; whether to use the official MCP Python SDK or a small hand-written
implementation; exactly how Claude Code is pointed at a local MCP endpoint with a
session secret; and whether per-tool rules live in the gateway's policy file or in
the token's scopes.
