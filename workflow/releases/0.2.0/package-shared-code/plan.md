# Plan: package-shared-code

Status: draft — waiting for the owner's choice of approach

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
| 1 | Declare the four directories in `pyproject.toml`; relock | Suites pass with the `sys.path` lines still present | todo |
| 2 | Delete the `sys.path` blocks in `gateway.py`, `lab_exchange.py` and `broker.py` | Suites pass; each module imports from an unrelated directory | todo |
| 3 | Move shared fixtures to `conftest.py` in `oauth-as/tests` and `gateway/tests` | Same test counts; the two test-file lint exceptions removed | todo |
| 4 | Move the three helpers `manual_claude_check.py` borrows from tests into a small module; delete its `sys.path` lines | The offline check passes; the last two lint exceptions removed | todo |
| 5 | Update `workflow/PROJECT.md` and the debt register | Docs check passes | todo |
| 6 | Prove equivalence: a fresh clone runs the quickstart end to end | Broker exits 0 with `MOCK_OK` | todo |
| 7 | Verifier agent, then land | No behavior difference found | todo |

**Proving behavior is unchanged.** Test counts identical before and after (8; 34
with 11 skipped; 55; 93; 13 with 6 skipped). `git diff` on the component modules
shows only import lines and moved fixtures. A fresh clone, where no stale path can
help, runs the whole quickstart.

**Risks.** A fresh clone or another host needs `uv sync` before anything imports;
running a component with a bare `python` outside the project environment stops
working. That is already what every README says to do. A name clash with the mock's
`app` package was checked and does not occur for the documented commands.
