# Spec: mcp-gateway

Consumes: [intent.md](intent.md)
Status: draft

**Behavior.** A new service in `components/gateway`, `mcp_gateway.py`, run as its
own process on `https://127.0.0.1:8083`, with one MCP endpoint, `POST /mcp`. It
speaks MCP revision 2026-07-28 only. It is separate from the LLM gateway so that
the credential for tool servers and the credentials for models never share a
process. It runs only with DPoP: it will not start without a nonce key and a replay
folder.

*Order of checks.* Every request passes these in order, and stops at the first
that fails. Nothing is forwarded, and no tool name is acted on, before all of them
pass.

1. An `Origin` header is refused (403). Browsers send one; the broker does not.
2. The credential: exactly one `Authorization: DPoP` token, no other credential.
3. The token: signed by the lab's authorization server, type `at+jwt`, audience
   `https://127.0.0.1:8083/mcp`, at most five minutes long, not expired, bound to a
   key. A model token fails here, on its audience.
4. The DPoP proof: for this address and method, signed by the key the token is
   bound to, with a current nonce from this gateway.
5. The client is the lab's exchange client and the scope is `mcp:invoke`.
6. The request: JSON, at most 1 MB, one JSON-RPC request with an `id`. The
   `MCP-Protocol-Version` header must be `2026-07-28` and equal the version in the
   body; `Mcp-Method` must equal the body's method; for a tool call, `Mcp-Name`
   must equal the body's tool name.
7. The proof is recorded so it cannot be used twice.
8. The method and, for a call, the per-tool rule.

*The three methods.*

- `server/discover` is answered by the gateway itself, under its own name, saying
  it supports revision 2026-07-28 and offers tools only. Nothing is forwarded.
- `tools/list` is forwarded to the tool server. The gateway removes every tool the
  user is not allowed and marks the list private with no caching, so one user's
  list is never served to another.
- `tools/call` for an allowed tool is forwarded and the result returned. For any
  other tool the answer is the "unknown tool" error (JSON-RPC `-32602`, sent with
  HTTP 200 as an ordinary JSON-RPC reply), word for word the same whether the tool
  exists upstream or not.

Every other method is refused as not found (404, `-32601`). `GET` and `DELETE` are
refused (405).

*The per-tool rules.* A policy file, required at startup, lists for each user the
tools they may use. Users are named by the mapped identity in their token, the same
opaque identity the LLM gateway sees:

```json
{"tools": {"synthetic-gateway-subject-01": ["lab_echo"]}}
```

A user who is not in the file is still a valid caller but has no tools: an empty
list, and every call refused as unknown. A file that is malformed, or names a tool
with characters outside letters, digits, `_`, `-` and `.`, stops the gateway from
starting. The file is read once at startup.

*What goes to the tool server.* The gateway never forwards the caller's request as
received. It builds a new one containing only the method, the tool name and
arguments (or the list cursor), the protocol version, and an empty set of client
capabilities. It sends its own credential, `MCP_GATEWAY_UPSTREAM_TOKEN`, and the
2026-07-28 headers, by `POST` only. The user's token, proof and any other field of
the caller's request are not sent. The empty capabilities mean a tool server cannot
ask the user for input.

*What it accepts back.* A single JSON reply of at most 1 MB with status 200, that
is a complete result. A reply that is a stream, asks for user input, hands back a
task, or is malformed is refused (502). When the caller disconnects, the gateway
closes the upstream request. A tool list keeps only its tools and next-page marker;
a call result is passed on with the tool server's own name removed.

*Refusals a client can act on.* A missing or invalid token gets 401 with a DPoP
challenge; a wrong scope gets 403. Both name the metadata address. The gateway
publishes OAuth Protected Resource Metadata (RFC 9728) at
`/.well-known/oauth-protected-resource/mcp`, without requiring a credential: its
own address, the authorization server, the scope `mcp:invoke`, and
`dpop_bound_access_tokens_required: true` with `ES256`. RFC 9728 defines that field,
which settles a question decision 0003 left open.

*The audit log.* One line per request with the event, the request ID, the user's
mapped identity once the token is verified, and the tool name when the call was
allowed. Never the arguments, the result, a token, or a tool name the policy does
not know, since that is text chosen by the caller. This needs a change to the
project convention that logs carry "event names and request IDs only"; see the
decisions below.

*The test client.* `lab_invoke.py`'s probe, which can already obtain an MCP token
with `--mcp`, goes on to use it: it discovers the gateway, lists tools, calls an
allowed tool, and confirms a tool that is not allowed is refused as unknown.

**Scope.** `components/gateway/mcp_gateway.py` and its tests; `gateway.py`, where
the token check gains the audience and scope it is checking for as parameters with
the LLM gateway's behavior unchanged; `lab_invoke.py`; the gateway README; the
root README; `workflow/PROJECT.md`; the glossary; a diagram page under
`docs/concepts/`; and `pyproject.toml` only to make `mock-mcp` importable by tests.

**Non-goals.**

- Claude Code is not connected, and the broker and quickstart do not change. That
  is the next task.
- No streaming replies, no requests for user input, no tasks, no subscriptions, no
  prompts or resources.
- No reloading of the policy while running, and no rules on a tool's arguments.
- No more than one tool server.
- No Bearer mode.
- A standard MCP client still cannot use the gateway directly: it has no DPoP key,
  and the authorization server has no sign-in page for it. The metadata is
  published because the specification requires it.

**Other requirements.** Security: every refusal before step 5 looks the same as
the LLM gateway's refusal of the same kind. The LLM gateway's own suite must pass
unchanged. Dependencies: none new.

**Acceptance criteria.**

- [ ] With a valid MCP token and proof, `server/discover` reports tools only and
      the gateway's own name; `tools/list` shows only the user's allowed tools and
      is marked private; an allowed `tools/call` returns the tool's result, tested
      against the real SDK-built mock server in-process.
- [ ] A tool that exists upstream but is not allowed, and a tool that does not
      exist, get byte-identical "unknown tool" replies, and the tool server
      receives no request for either.
- [ ] Refused: a model token; a token with the wrong scope; an expired token; a
      token bound to a different key; a missing, replayed or stale-nonce proof; a
      proof made for the LLM gateway's address; a Bearer credential; two
      credentials.
- [ ] Refused with the header-mismatch error: a missing or older
      `MCP-Protocol-Version` header, a version that differs from the body, an
      `Mcp-Method` or `Mcp-Name` that is missing or differs from the body. In
      particular, headers naming an allowed tool over a body calling another tool
      are refused and nothing is forwarded.
- [ ] Refused: any other method, `GET`, `DELETE`, a notification, a batch, an
      `Origin` header, an oversized body.
- [ ] The request the tool server receives carries the gateway's credential and
      the 2026-07-28 headers, and contains neither the user's token, the proof,
      nor the caller's capabilities.
- [ ] Upstream replies that are a stream, ask for input, hand back a task, are
      oversized or malformed are refused with 502.
- [ ] The LLM gateway refuses an MCP token (already tested) and its suite passes
      unchanged.
- [ ] The metadata document is served without a credential and matches RFC 9728.
- [ ] The audit log names the user and an allowed tool, and never contains
      arguments or a tool name the policy does not know.
- [ ] Each security check is shown to be tested by breaking it and seeing a test
      fail; the list is in the outcome.
- [ ] A live lab run: Keycloak sign-in, MCP token, the probe through the running
      gateway to the running mock server, with the allowed call succeeding and the
      disallowed one refused. Recorded in the task folder.
- [ ] A diagram page shows the path of a tool call and where each check sits.

**Open questions.** Three decisions for the owner:

1. What a signed-in user with no entry in the policy gets: an empty tool list
   (proposed), or a 403.
2. Which tool the synthetic user is allowed in the lab's example policy: `lab_echo`
   only (proposed), so the demonstration shows one tool allowed and one hidden.
3. Changing the logging convention so the MCP gateway's audit log may carry the
   mapped user identity and an allowed tool's name. Decision 0003 already calls
   for it; the convention in `workflow/PROJECT.md` forbids it as written.
