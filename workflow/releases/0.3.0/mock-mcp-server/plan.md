# Plan: mock-mcp-server

Consumes: [spec.md](spec.md)

**Design summary.** One module, `mock_mcp.py`. A function builds the SDK server and
registers the two tools; another wraps the SDK's web application with a small
credential check and returns it, so tests can run the same application in-process.
Plan approval is not required: it is a new component, touches no accepted security
module, and is easy to remove.

**Units.**

| # | Unit | Check | Status |
|---|------|-------|--------|
| 1 | Add `mcp==2.3.0`, relock | All existing suites, lint and docs check pass with it installed | **done** |
| 2 | The server: two tools, no sessions, JSON replies, public tool list, credential check | In-process tests for the tools and the credential | **done** |
| 3 | Tests that pin each row of the spec's two tables | Tests pass and state the status and code observed | **done** |
| 4 | README, CI, root README, glossary, decision record, diagram page | Documentation check passes | **done** |
| 5 | Real artifact: start the server and connect the installed Claude Code to it | Claude Code reports both tools | **done** |
| 6 | Verifier agent, then land | Acceptance criteria met | **done** (merge awaits the owner) |

**Risks.** The SDK's API for version 2 is new to this project; the trial run covered
the calls needed. The test for `GET` has to observe a reply that never arrives,
which may be awkward to pin without making the suite slow.
