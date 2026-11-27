# Spec: mock-mcp-server

Consumes: [intent.md](intent.md)
Status: **approved** (2026-11-27)

**How it is built.** With the official MCP Python SDK, pinned at version 2.3.0, and
not by hand. The owner chose this, and the assistant agreed after testing it. The
reasons: the mock is not the security boundary, the gateway is; a server written by
the same hand as the gateway would share its misreadings of the specification,
while the SDK is an independent implementation to test the gateway against; and it
is what a real tool server looks like. The cost is twelve more pinned packages,
used only by the mock.

**Behavior.** A new component, `components/mock-mcp`, with one file,
`mock_mcp.py`, run on `127.0.0.1:8767` over plain HTTP like the mock LLM, with a
single endpoint, `POST /mcp`. It is configured to keep no sessions, to reply
with a single JSON object, and with the SDK's subscriptions switched off.

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
pin each of these, so that a later SDK upgrade which changes one is noticed. The
two tables were corrected on 2026-11-27 after verification; what changed is in
[outcome.md](outcome.md).

What it does when the request's `MCP-Protocol-Version` header says 2026-07-28:

| Request | Answer |
|---|---|
| `server/discover`, `tools/list`, `tools/call` | Results with the fields revision 2026-07-28 requires |
| A tool call with bad arguments | A normal result flagged as an error, which a model can read and correct |
| `Mcp-Method` or `Mcp-Name` header missing or disagreeing with the body | 400, header-mismatch error `-32020` |
| A revision it does not support | 400, error `-32022`, naming the supported one |
| No protocol fields in the request | 400, error `-32602` |
| A method that does not exist, including `subscriptions/listen` | 404, error `-32601` |
| `GET` or `DELETE` | 405 |
| A request with an `Origin` header from elsewhere | 403 |

What the gateway must not rely on the mock for. The first row departs from the
specification's text. The rest are things the specification permits, because the
SDK also serves clients built for older revisions, but that this lab does not want.
None is changed in the mock; each becomes a rule for the gateway and is carried
into the gateway task:

| What the SDK does | What it means for the gateway |
|---|---|
| A call to a tool that does not exist gets a normal result flagged as an error, not the JSON-RPC "unknown tool" error the specification describes | The gateway cannot rely on an upstream's error code to mean "no such tool"; it decides itself which tools exist |
| It chooses which revision's rules to apply from the `MCP-Protocol-Version` header alone. With an older value, or none, the request is served under the older rules even when its body says 2026-07-28 | The gateway must require the 2026-07-28 header from its caller |
| Under the older rules it does not compare the headers with the body at all: headers naming `lab_echo` over a body calling `lab_add` run `lab_add` | The gateway must also send the 2026-07-28 header on every request it forwards, or the mock checks nothing |
| Under the older rules `GET` opens a long-lived stream | The gateway must forward `POST` only |
| It says it offers prompts and resources, and answers their list requests with empty lists, although only tools are registered | The gateway must allow only the three tool methods and advertise only tools |

**Scope.** `components/mock-mcp/` (the server, its tests and a README in the
standard five sections), `pyproject.toml` and `uv.lock` (the SDK), the CI test
loop, the root README's component table, a decision record for the SDK choice, a
diagram page under `docs/concepts/` showing the shape of an MCP request, and the
glossary.

**Non-goals.**

- No resources, prompts, subscriptions, tasks, or requests for user input of our
  own. The first gateway version blocks all of them.
- No attempt to make the SDK stricter than it is, with one exception: its
  subscriptions are switched off, a constructor option, because left on it serves
  `subscriptions/listen` as a long-lived stream. The gateway is where strictness
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

**Open questions.** None. Approved as described on 2026-11-27.
