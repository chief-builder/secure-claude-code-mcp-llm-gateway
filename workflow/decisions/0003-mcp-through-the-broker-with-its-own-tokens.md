# ADR-0003: MCP traffic goes through the broker, with its own DPoP-bound tokens and per-tool rules

Date: 2026-11-26 (revised the same day after reading the MCP specification, revision 2026-07-28)
Status: **accepted**

**Context.** The project's name promises an MCP gateway and nothing implements one.
MCP lets Claude Code call tools on remote servers. Those servers need to know who is
calling, and whatever credentials they need for the systems behind them should not
sit on a laptop, for the same reasons AWS credentials should not.

The MCP specification's own authorization model is OAuth with bearer tokens. It
never mentions DPoP or any other way of tying a token to a key: its rule for clients
is literally `Authorization: Bearer <access-token>`. Claude Code can sign in to an
MCP server that way, or attach fixed headers when it connects. Either way the token
is a bearer token: whoever copies it can use it. The base protocol does allow
clients and servers to "negotiate their own custom authentication and authorization
strategies".

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
- The gateway holds whatever credential the tool server needs and never forwards the
  user's token. In the lab the tool server is a mock with harmless tools.
- It is built for the local lab first, on loopback like every other component.
- It targets revision 2026-07-28 of the specification.

**Alternatives considered.**

- Claude Code's built-in MCP sign-in straight to the gateway: standard and needs no
  broker, but yields bearer tokens, which is the weakness this project exists to
  remove.
- Both paths: more to build, and two security levels to explain in one reference.
- One scope for all tools first, per-tool rules later: smaller, but the owner wants
  the control a company would actually need from the start.
- Waiting for the AWS host: would put MCP behind the AWS work for no technical
  reason.
- The specification's Enterprise-Managed Authorization extension: it has the same
  aim, a company controlling which MCP servers an employee may use, but a different
  flow. The client exchanges its ID token at the identity provider for an
  intermediate grant, then presents that grant to the MCP server's authorization
  server. Ours is one exchange at our own authorization server. It also uses bearer
  tokens. Not adopted now; filed as an idea to compare against later.

## How the design sits against the specification

**Where it follows the specification.**

- *No token passthrough.* The specification says a server "MUST NOT pass through
  the token it received from the MCP client". The gateway uses its own credential
  upstream.
- *Audience checking.* Servers must accept only tokens issued for them. MCP tokens
  will name the MCP gateway, and only it, as their audience. The specification
  identifies a server by its URL, so the audience should be the gateway's MCP
  endpoint address, and the broker should name it when it asks for the token.
- *Per-user tool lists are allowed.* A tool list must not vary per connection but
  "MAY vary by the authorization presented on the request".
- *Rules enforced at the server, not only in the token.* The security guidance
  lists "treating claimed scopes in token as sufficient without server-side
  authorization logic" as a common mistake.
- *Stateless requests.* This revision removed the opening handshake and sessions:
  every request stands alone. That suits a gateway that checks a fresh proof on
  every request, and it removes session hijacking as a concern.
- *The local listener.* The guidance for local HTTP servers is to bind to loopback,
  require a token and check the `Origin` header. The broker already does all three
  for model calls.

**Where it deliberately departs.**

- *DPoP instead of Bearer between the broker and the gateway.* A standard MCP client
  cannot use the gateway directly, because it will send `Bearer` and has no DPoP
  key. This is the point of the design, and it is confined to the one hop the lab
  controls. Between Claude Code and the broker the exchange is ordinary MCP with a
  bearer secret that is valid for one session on loopback.
- *Refusals use the DPoP challenge form* defined by RFC 9449, where the
  specification's examples use the Bearer form.
- *The authorization server offers token exchange only.* It has no sign-in page of
  its own, so the specification's discovery flow cannot be completed by a standard
  client even though the gateway will publish the metadata the specification
  requires.

**What the specification requires the gateway and mock to implement.**

- To a client the gateway is the server, so it must answer `server/discover` itself
  and advertise only what it offers. The first version offers tools only:
  `server/discover`, `tools/list` and `tools/call`. Every other method is refused as
  not found.
- Every request carries `MCP-Protocol-Version` and `Mcp-Method` headers, and tool
  calls carry `Mcp-Name`. The specification mirrors these into headers so gateways
  can inspect requests. Anything that reads the body must check the headers match
  it and refuse with the `HeaderMismatch` error if they do not. The gateway decides
  on the tool name only after that check.
- A filtered tool list must be marked `cacheScope: "private"` on every page, with a
  `ttlMs`, even if the upstream list was `"public"`. Otherwise a shared cache may
  serve one user's list to another.
- A call to a tool the user may not use is refused as "Unknown tool" (JSON-RPC
  `-32602`). The specification defines no "forbidden" error; this one matches the
  filtered list and does not reveal that the tool exists. Filtering the list is not
  enforcement: the check runs on every call.
- A missing or invalid token gets 401, and insufficient permission gets 403 with a
  challenge. The gateway must publish OAuth Protected Resource Metadata naming the
  authorization server.
- When the client disconnects, the gateway closes the upstream request; that is how
  cancellation works over HTTP in this revision. Responses are a JSON object or a
  stream scoped to the one request, with no resuming.
- The gateway forwards no client capabilities upstream in the first version, so an
  upstream cannot ask the user for input mid-call. If an upstream answers with an
  input request or a task handle anyway, the gateway refuses the response.
- Upstream servers see one credential, the gateway's, so the gateway's audit log is
  the only record of which user called which tool. It records the user and the tool
  name, never the arguments.

**Consequences.**

- The broker stops being model-only and gains a second local listener. It also has
  to launch Claude Code with tools enabled and an MCP configuration, where today it
  disables both.
- The authorization server must issue tokens for a second audience and scope. That
  is a change to an accepted security module.
- The MCP gateway reuses the token and DPoP checks the LLM gateway uses, which makes
  the shared code more important.
- An ordinary MCP client that does not go through the broker cannot use this
  gateway.
- Three stages are wanted, each a step further end to end: a test client calling a
  tool and Claude Code listing it; a scripted mock model that makes Claude Code
  really call the tool; and a real model on Bedrock choosing to call it. The third
  needs tool-use support in the Bedrock adapter, which is text-only today, and paid
  AWS time.

**Still to verify, when the first build task is specified.**

- *Which protocol revision the installed Claude Code speaks.* The specification
  says a client built for the earlier, handshake-based revisions cannot talk to a
  server that supports only this one. If Claude Code is such a client, the broker's
  listener must accept the older form as well. This is the largest open risk and
  should be settled first, by observing what Claude Code actually sends.
- Whether to use the official MCP Python SDK or a small hand-written
  implementation. With three methods and no sessions, hand-written is plausible.
- The exact field for stating "DPoP required" in the published metadata.
- The normative text of the two authorization extensions. Only their overview pages
  were read; the binding text lives in a separate repository.

**What was read.** Every page of revision 2026-07-28 except the schema reference,
which was searched for exact field names but not read through: the base protocol,
versioning, transports, authorization (four pages), message patterns, server
features, client features, utilities, the changelog and the deprecation list. Also
the extensions overview, the Tasks extension, the two authorization extension
overviews and the security best practices guide.
