# Plan: package-shared-code

Status: **approved** (2026-11-25) — approach A, proven at the end by a live run from a fresh clone

**What a probe showed.** Declaring the four component directories in
`pyproject.toml` through an editable install makes every cross-component import
work from any directory, with the `sys.path` lines still in place and all suites
passing. The mock, whose package is also called `app`, still resolves correctly in
its tests and under `uvicorn --app-dir`.

**The honest limit.** The roadmap line says a change in one component should not be
able to "silently break another". No packaging choice delivers that; the test
suites in CI do, and already do. What packaging changes is where the dependency is
declared and how the code is deployed.

**Three approaches.**

| | A. Declare the path | B. Real packages | C. Fixtures only |
|---|---|---|---|
| What changes | `pyproject.toml` lists the four directories; the four `sys.path` blocks are deleted; shared test fixtures move to `conftest.py`; the three helpers the offline check borrows from tests move to a small module | Each directory becomes a named package (`oauth_as`, `gateway`, …); every import is rewritten; services start with `python -m` | Only the shared test fixtures move to `conftest.py` |
| Files touched | About 10 | About 35, plus every README, the quickstart and the walkthroughs | About 5 |
| Documented commands | Unchanged | All change | Unchanged |
| Lint exceptions left | 0 | 0 | 2 |
| Main risk | Module names such as `app`, `gateway` and `login` become importable from anywhere in the environment, so a future name clash is possible | Large diff across accepted security code and all documentation | The `sys.path` lines stay |

Recommended: **A**. It meets every success point in the intent at a tenth of the
change. B is the better end state for code that is deployed as separate units, and
the AWS-hosting design task will say what those units are; doing B before that risks
packaging along the wrong lines.

**Units for approach A.** Each ends with all five suites and both checks green,
and is committed before the next.

| # | Unit | Check | Status |
|---|------|-------|--------|
| 1 | Declare the four directories in `pyproject.toml`; relock | Suites pass with the `sys.path` lines still present | **done** |
| 2 | Delete the `sys.path` blocks in `gateway.py`, `lab_exchange.py` and `broker.py` | Suites pass; each module imports from an unrelated directory | **done** |
| 3 | Move shared fixtures to `conftest.py` in `oauth-as/tests` and `gateway/tests` | Same test counts; the two test-file lint exceptions removed | **done** |
| 4 | Move the three helpers `manual_claude_check.py` borrows from tests into a small module; delete its `sys.path` lines | The offline check passes; the last two lint exceptions removed | **done** |
| 5 | Update `workflow/PROJECT.md` and the debt register | Docs check passes | **done** |
| 6 | Prove equivalence: a fresh clone runs the quickstart end to end | Broker exits 0 with `MOCK_OK` | **done** |
| 7 | Verifier agent, then land | No behavior difference found | **done** |

**Proving behavior is unchanged.** Test counts identical before and after (8; 34
with 11 skipped; 55; 93; 13 with 6 skipped). `git diff` on the component modules
shows only import lines and moved fixtures. A fresh clone, where no stale path can
help, runs the whole quickstart.

**Risks.** A fresh clone or another host needs `uv sync` before anything imports;
running a component with a bare `python` outside the project environment stops
working. That is already what every README says to do. A name clash with the mock's
`app` package was checked and does not occur for the documented commands.

## Outcome — 2026-11-25

Behavior is unchanged for every documented command. One thing outside the
documented commands did change, and one claim in the intent was wrong.

**What was built.** `pyproject.toml` lists the four component directories through a
hatchling editable install. Every `sys.path` change in `components/` is gone,
including a redundant one in a test. Shared fixtures moved to `conftest.py` in the
`oauth-as` and `gateway` tests; the synthetic responses the offline check borrowed
from tests moved to `gateway/lab_fixtures.py`. All four lint exceptions are removed.

**Proof.**

- Collected test IDs and results are identical to `main` in all five suites (8; 34
  with 11 skipped; 55; 93; 13 with 6 skipped), confirmed independently by the
  verifier, which also found the moved code to be a line-for-line move.
- All five CI jobs pass on a clean Linux checkout.
- A fresh clone under the home folder ran the whole quickstart live, with the owner
  signing in: the broker with the software key exited 0 with `MOCK_OK`; the DPoP
  probe printed `component_05_succeeded`; the broker with the Secure Enclave signer
  returned `MOCK_OK`. No tracebacks in the service logs.
- The offline Claude Code check passed.

**Verifier findings and what was done.**

| Finding | Disposition |
|---|---|
| Copying only the `gateway` and `oauth-as` directories into a plain virtual environment, as the live Bedrock run did, worked on `main` and now fails with `No module named 'dpop'` | Real change in behavior. Documented in the gateway README with both remedies, each checked: `uv sync --locked --no-dev` in a clone, or `PYTHONPATH=../oauth-as`. The Component 8 records are history and were not edited |
| The intent claimed this task makes deployment simpler. It does not: a host still needs both directories, and now the project files and `uv` as well | The intent was wrong on this point. Simpler deployment needs real packages (approach B), which is filed against the AWS-hosting design |
| Hatchling was a new build-time dependency with no version pin, in a project that pins everything else | Fixed: hatchling and the four packages it pulls in are pinned, and the lockfile records them. Residual: build dependencies are pinned by version, not by hash |
| Component directories now come after installed packages on the import path, so a dependency shipping a module named `gateway` or `exchange` would silently replace the lab's own | Fixed as a guard, not a prevention: `tools/tests/test_import_path.py` fails when any component module resolves elsewhere. Shown to fail with a same-named module placed ahead on the path |
| A mistyped directory in `dev-mode-dirs` is accepted silently | Fixed: the same test file checks every listed directory exists and that module names are unique |
| One `sys.path` change remained in a test, hidden from a text search | Removed |

**Decided on the owner's behalf.** Pinning the build tool's own dependencies through
`build-constraint-dependencies`. Adding the import-path guard tests to `tools/tests`,
which already runs in CI.

**Not covered.** The Bedrock backend and a real deployment to another host were not
run; the two remedies in the gateway README were checked on this Mac only.
