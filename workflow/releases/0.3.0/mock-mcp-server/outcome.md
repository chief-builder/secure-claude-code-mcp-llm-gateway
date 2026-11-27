# Outcome: mock-mcp-server

Consumes: [spec.md](spec.md), [plan.md](plan.md)
Date: 2026-11-27

## What was built

`components/mock-mcp`: a mock MCP tool server for revision 2026-07-28, built with
the official MCP Python SDK (`mcp` 2.3.0), with two tools, `lab_echo` and
`lab_add`, on `127.0.0.1:8767`. The one piece of our own security code is a check
that refuses a request without the shared credential before the SDK sees it.

## What was run

All offline unless marked.

| Check | Result |
|---|---|
| `mock-mcp` suite | 28 passed |
| `mock-llm`, `oauth-as`, `gateway` suites | 8, 88 and 96 passed |
| `oauth-lab` suite | 34 passed, 11 skipped (need Keycloak) |
| `broker` suite | 13 passed, 6 skipped (need the hardware signer) |
| `tools` suite, lint, documentation check | 28 passed; no problems |
| README start and `curl` commands pasted into a default interactive shell (live, local) | The reply's text was `42` |
| Installed Claude Code 2.1.331 pointed straight at the running mock, with the mock LLM as its model (live, local) | Server reported `connected`; tools `lab_add` and `lab_echo` listed |

The Claude Code run was made before subscriptions were switched off and the tests
were extended; it was repeated afterwards, and the result is recorded below under
"After verification".

## Checks shown to be tested

Each line was broken on its own, the suite run, and the file restored.

| Change made | Caught |
|---|---|
| Credential check removed | yes, 15 tests failed |
| Credential compared by prefix only | yes, 2 |
| Several `Authorization` headers allowed | yes, 1 |
| Credential checked on `POST` only | yes, 5 (not caught before verification; tests added) |
| Any credential accepted at startup | yes, 4 |
| Credential as short as 6 characters accepted | yes, 1 (not caught before verification; test added) |
| Subscriptions left on | yes, 2 |

## What verification found

An independent verifier agent tried to refute the work. It could not get a request
past the credential check. It did find the following, all acted on:

1. With subscriptions on, the SDK's default, the mock served `subscriptions/listen`
   as a long-lived stream, contradicting "replies with a single JSON object". Now
   switched off with the SDK's own option, and pinned.
2. Under older revisions the SDK does not compare headers with body, so headers
   naming one tool over a body calling another ran the other tool. Nothing said so
   and nothing pinned it. Now pinned, documented, and a rule for the gateway: send
   the 2026-07-28 header upstream.
3. The documents said the SDK was "looser than the specification in four ways".
   Only the unknown-tool answer departs from the specification; accepting older
   revisions, the `GET` stream and advertising prompts and resources are permitted
   by it. `GET` is in fact refused with 405 when the header names the current
   revision. The spec's tables, the README, the concept page, decision 0004 and
   the roadmap were corrected.
4. Two ways of breaking the credential check passed every test. Tests added.
5. Three table cases were not pinned (`Mcp-Method` missing, two resource lists),
   and the `GET` test would have passed on any hang. Now pinned; the `GET` test
   asserts the 200 and the stream's content type.
6. The mock LLM's tests now run on `httpx2`. The debt-register line that had been
   removed was restored and reworded: the warning is hidden, not fixed.
7. The README's `claude` example did not say which model it would use. Now says.
8. The concept page's diagram put the duty to compare headers and body on the
   gateway; the specification puts it on the server. Corrected.

Not verified by anyone: that the two Mermaid diagrams render on GitHub.

## After verification

With the fixes in place: all suites and lint passed again with the counts in the
table above; the seven mutations were run against the final code; and the installed
Claude Code 2.1.331 was pointed at the final server once more (live, local). It
reported the server `connected` and listed `lab_add` and `lab_echo`. A request
without the credential got 401 on both `POST` and `GET`.
