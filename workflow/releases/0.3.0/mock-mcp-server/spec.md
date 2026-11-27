# Spec: mock-mcp-server

Consumes: [intent.md](intent.md)
Status: draft (revised 2026-11-27 after the owner chose the official SDK)

**How it is built.** With the official MCP Python SDK, pinned at version 2.3.0, and
not by hand. The owner chose this, and the assistant agreed after testing it. The
reasons: the mock is not the security boundary, the gateway is; a server written by
the same hand as the gateway would share its misreadings of the specification,
while the SDK is an independent implementation to test the gateway against; and it
is what a real tool server looks like. The cost is twelve more pinned packages,
used only by the mock.

**Behavior.** A new component, `components/mock-mcp`, with one file,
`mock_mcp.py`, run on `127.0.0.1:8767` over plain HTTP like the mock LLM, with a
single endpoint, `POST /mcp`. It is configured to keep no sessions and to reply
with a single JSON object.

*Tools.* Two, both pure calculations on their arguments:

- `lab_echo` returns the text it is given.
- `lab_add` returns the sum of two whole numbers.

The tool list is the same for every caller, so it is marked as cacheable by anyone.

*Its credential.* The one piece of the mock that is our own code. The server
refuses to start without `MOCK_MCP_TOKEN`, and a small check in front of the SDK
refuses any request that does not present that value as a bearer credential, with
401, before the SDK sees it. This is the credential the MCP gateway will hold: a
shared secret between two lab services on loopback, the same arrangement as the
mock LLM, and not MCP's own OAuth-based authorization.

*What the SDK does, found by a trial run before this spec was revised.* The tests
will pin each of these, so that a later SDK upgrade which changes one is noticed.

Where it does what the specification says:

| Request | Answer |
|---|---|
| `server/discover`, `tools/list`, `tools/call` | Results with the fields revision 2026-07-28 requires |
| A tool call with bad arguments | A normal result flagged as an error, which a model can read and correct |
| `Mcp-Method` or `Mcp-Name` header missing or disagreeing with the body | 400, header-mismatch error `-32020` |
| A revision it does not support | 400, error `-32022`, naming the supported one |
| No protocol fields in the request | 400, error `-32602` |
| A method that does not exist | 404, error `-32601` |
| `DELETE` | 405 |
| A request with an `Origin` header from elsewhere | 403 |

Where it differs from the specification's text, or does more than this lab wants.
None of these is changed in the mock; each becomes a rule the gateway must enforce
itself, and is carried into the gateway task:

| What the SDK does | What it means for the gateway |
|---|---|
| A call to a tool that does not exist gets a normal result flagged as an error, not the JSON-RPC "unknown tool" error the specification describes | The gateway cannot rely on an upstream's error code to mean "no such tool" |
| It also accepts the older, handshake-based revisions. A request with an older or missing `MCP-Protocol-Version` header is served under the older rules instead of being refused, even when its body says 2026-07-28 | The gateway must itself require the 2026-07-28 header and check it against the body |
| `GET` opens a long-lived stream, an older-revision feature, instead of answering 405 | The gateway must forward `POST` only |
| It says it offers prompts and resources, and answers their list requests with empty lists, although only tools are registered | The gateway must allow only the three tool methods and advertise only tools |

**Scope.** `components/mock-mcp/` (the server, its tests and a README in the
standard five sections), `pyproject.toml` and `uv.lock` (the SDK), the CI test
loop, the root README's component table, a decision record for the SDK choice, a
diagram page under `docs/concepts/` showing the shape of an MCP request, and the
glossary.

**Non-goals.**

- No resources, prompts, subscriptions, tasks, or requests for user input of our
  own. The first gateway version blocks all of them.
- No attempt to make the SDK stricter than it is. The gateway is where strictness
  belongs.
- No OAuth and no published authorization metadata on the mock.
- No tool that reads files, calls the network, or tells the time.
- Not added to the quickstart yet; nothing uses it until the gateway exists.
- The standalone `fastmcp` package is not used. It is a separate, larger project;
  the official SDK already contains the same style of server.

**Other requirements.** Dependencies: `mcp==2.3.0` and the packages it brings are
pinned in the lock file like every other dependency. The existing suites must be
unaffected by their presence.

**Acceptance criteria.**

- [ ] The installed Claude Code, pointed straight at the running mock with its
      credential and with the mock LLM standing in for a model, connects and reports
      both tools as available.
- [ ] `lab_echo` and `lab_add` return the expected text through `tools/call`.
- [ ] Every row of the two tables above is pinned by a test that states the status
      and error code observed.
- [ ] The server will not start without `MOCK_MCP_TOKEN`. A request with a wrong or
      missing credential gets 401, and the SDK does not see it: no tool runs.
- [ ] Removing the credential check makes a test fail; this is recorded in the
      outcome. (It is the only check in this component that is our own code.)
- [ ] Its tests run in CI, and the other five suites, the tools tests, lint and the
      documentation check still pass with the SDK installed.
- [ ] A decision record states why the mock uses the SDK and the gateway does not.
- [ ] A diagram page explains the shape of an MCP request and is linked from the
      documentation index.

**Open questions.** None on how to build it. Awaiting approval of the spec as a
whole.
