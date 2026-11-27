# Spec: mock-mcp-server

Consumes: [intent.md](intent.md)
Status: draft

**Behavior.** A new component, `components/mock-mcp`, with one file,
`mock_mcp.py`, run on `127.0.0.1:8767` over plain HTTP like the mock LLM. It has a
single endpoint, `POST /mcp`, and speaks MCP revision 2026-07-28, which has no
sessions and no opening handshake: every request stands alone.

*Tools.* Two, both pure calculations on their arguments:

- `lab_echo` returns the text it is given.
- `lab_add` returns the sum of two whole numbers.

*Methods.*

- `server/discover` says which revision the server speaks and that it offers tools.
- `tools/list` returns the two tools, always in the same order, marked as cacheable
  by anyone, because every caller sees the same list.
- `tools/call` runs a tool and returns its result as text. A call with bad
  arguments is answered with a normal result flagged as an error, so a model can
  read it and try again. A call to a tool that does not exist is answered with the
  JSON-RPC "unknown tool" error. Both are what the specification asks for.
- Any other method is refused as not found.

*Refusals the specification defines*, each tested:

- A request whose `MCP-Protocol-Version`, `Mcp-Method` or `Mcp-Name` header is
  missing or disagrees with the body: 400 with the header-mismatch error.
- A revision other than 2026-07-28: 400 with the unsupported-version error, naming
  the supported one.
- A request without the required protocol fields: 400, invalid parameters.
- `GET` or `DELETE`: 405.
- A request carrying an `Origin` header: 403. Only another server calls this one,
  never a web page.

*Its credential.* The server refuses to start without `MOCK_MCP_TOKEN`, and
refuses any request that does not present that value as a bearer credential, with
401. This is the credential the MCP gateway will hold. It is a shared secret
between two lab services on loopback, the same arrangement as the mock LLM, and
not MCP's own OAuth-based authorization.

*Replies.* Always a single JSON object. The specification lets a server choose
between that and a stream; the mock never needs a stream.

**Scope.** `components/mock-mcp/` (the server, its tests and a README in the
standard five sections), the CI test loop, the root README's component table, a
diagram page under `docs/concepts/` showing the shape of an MCP request, and the
glossary.

**Non-goals.**

- No resources, prompts, subscriptions, tasks, or requests for user input. The
  first gateway version blocks all of them.
- No streaming replies.
- No OAuth and no published authorization metadata on the mock. The gateway, not
  the mock, is what users authenticate to.
- No tool that reads files, calls the network, or tells the time.
- Not added to the quickstart yet; nothing uses it until the gateway exists.

**Other requirements.** No new dependency: it uses the web framework already in the
lock file.

**Acceptance criteria.**

- [ ] The installed Claude Code, pointed straight at the running mock with its
      credential and with the mock LLM standing in for a model, connects and reports
      both tools as available.
- [ ] `server/discover`, `tools/list` and `tools/call` return results that carry the
      fields the 2026-07-28 schema requires, checked field by field in tests.
- [ ] `lab_echo` and `lab_add` return the expected text; bad arguments give a result
      flagged as an error; an unknown tool gives error `-32602`.
- [ ] Each refusal listed above is tested, with the status and error code stated.
- [ ] The tool name in `Mcp-Name` is accepted in plain form and in the
      specification's Base64 form, and refused when it disagrees with the body.
- [ ] The server will not start without `MOCK_MCP_TOKEN`, and a request with a wrong
      or missing credential gets 401 and runs nothing.
- [ ] For the credential check, the header checks and the `Origin` check, removing
      the check makes a test fail; the checks tried are listed in the outcome.
- [ ] Its tests run in CI, and the other five suites, lint and the documentation
      check still pass.
- [ ] A diagram page explains the shape of an MCP request and is linked from the
      documentation index.

**Open questions.**

1. Write the server by hand, or use the official MCP Python SDK? The SDK (version
   2.3.0) would add about nineteen packages to a lab that pins every dependency,
   and would decide for us how strictly requests are checked. By hand it is about
   150 lines on the framework already in use, and every refusal is ours to state
   and test. Recommended: by hand.
2. The specification does not say which HTTP status accompanies the "unknown tool"
   error. Proposed: 200 with the JSON-RPC error in the body, the usual JSON-RPC
   convention. To be confirmed against what Claude Code accepts.
