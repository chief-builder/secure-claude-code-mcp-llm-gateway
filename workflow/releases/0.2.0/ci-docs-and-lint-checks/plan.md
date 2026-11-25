# Plan: ci-docs-and-lint-checks

Consumes: [spec.md](spec.md)

**Design summary.** One standard-library script, `tools/check_docs.py`, with a pure
function that takes a list of Markdown files and returns problems as
`path:line: message` strings; `main` only gathers the files from git and prints. That
split is what makes it testable without a repository. Ruff is configured in
`pyproject.toml`. Plan approval is not required: tooling only, fully reversible, and
no component code changes.

**Units.**

| # | Unit | Check | Status |
|---|------|-------|--------|
| 1 | `tools/check_docs.py` and its tests | Tests pass; the script reports the 24 source-line links and nothing else | todo |
| 2 | Replace the 24 source-line links in the two walkthroughs | The script exits 0; the grep in the spec finds nothing | todo |
| 3 | Ruff as a development dependency, with rules and documented exceptions | `uv run ruff check` exits 0 | todo |
| 4 | `docs` and `lint` jobs in CI; checker tests in the `test` job | All jobs pass on the task branch | todo |
| 5 | Commands and pitfalls in `workflow/PROJECT.md` | Commands run as written | todo |
| 6 | Prove each failure in real CI on a scratch branch, then delete it | Five failures seen, each naming file and line | todo |
| 7 | Verifier agent, then land | Acceptance criteria met | todo |

**Risks.** GitHub's heading-to-anchor rule is not formally specified; the checker
implements the common cases, and a false alarm would show up as a failing `docs` job
on a correct link. The template-owned files under `.claude/` are checked too; if one
of them fails the shell-comment rule it cannot be edited here and needs an exclusion.
