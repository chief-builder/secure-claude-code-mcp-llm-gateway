# Spec: ci-docs-and-lint-checks

Consumes: [intent.md](intent.md)
Status: **approved** (2026-11-25)

**Behavior.** Continuous integration gains two jobs that run on every push and pull
request, next to the existing `test` and `secrets` jobs.

- **`docs`** runs a small checker, kept in the repository at `tools/check_docs.py`,
  over every tracked Markdown file. It fails, naming file and line, when:
  - a relative link points at a file that does not exist;
  - a link's `#anchor` does not match a heading in the target Markdown file;
  - a shell code block (```` ```sh ````, `bash`, `zsh` or `shell`) contains a line
    whose first non-blank character is `#`;
  - a link points at a line number in a source file (`file.py#L125`).
  It does not fetch web links. The same command runs locally:
  `uv run python tools/check_docs.py`.
- **`lint`** runs `ruff check` with a deliberately small rule set: syntax errors,
  undefined names, unused imports and variables, and import placement (ruff's
  `E4`, `E7`, `E9` and `F`). The same command runs locally: `uv run ruff check`.

The two code walkthroughs lose their 24 source-line links. Each becomes a link to
the file, with the function or class named in the sentence, which survives code
moving.

**Scope.** `tools/check_docs.py` and its tests; `.github/workflows/ci.yml`;
`pyproject.toml` (ruff as a development dependency, and its configuration);
`uv.lock`; the two walkthroughs; `workflow/PROJECT.md` (commands and pitfalls).

**Non-goals.**

- No code formatter and no import sorting. Ruff's formatter would rewrite 27 of 37
  files, including the accepted security code, for no change in behavior.
- No broader lint rules. The wider rule families report 60 findings, mostly style.
- No fixes to the 24 findings the small rule set reports today. A probe showed that
  none is a defect: 7 are imports placed after the `sys.path` lines, and 17 are test
  fixtures imported from another test module. Both patterns disappear in the
  `package-shared-code` task, so here they are listed as per-file exceptions, each
  with that reason, and removed there.
- No type checker. Filed to the backlog.
- No checking of web links, which fail for reasons unrelated to the repository.

**Other requirements.** The checker uses only the Python standard library, so the
`docs` job needs no installation beyond Python.

**Acceptance criteria.**

- [x] `uv run python tools/check_docs.py` exits 0 on the repository and prints how
      many files and links it checked.
- [x] The checker's own tests cover each of the four failure kinds and a passing
      case, and they run in the `test` job.
- [x] On a scratch branch, each of these makes the named job fail in real CI, and is
      then reverted: a broken relative link (`docs`), a broken anchor (`docs`), a
      comment line in a shell block (`docs`), a source-line link (`docs`), an unused
      import in a component (`lint`).
- [x] No Markdown file contains a link to a source line. (Reworded at close: the
      original said a grep for the pattern finds nothing, which this spec's own
      prose examples make impossible.)
- [x] `uv run ruff check` exits 0, and every per-file exception in `pyproject.toml`
      carries a comment saying why it exists and which task removes it.
- [x] `git diff main -- components` shows changes to Markdown files only, and all
      five offline suites report the same counts as before.

**Open questions.** None. Decided at approval on 2026-11-25: the small rule set
with existing findings listed as exceptions; a small script kept in the repository;
source-line links replaced and banned.

## Outcome — 2026-11-25

All acceptance criteria met.

**What was built.** `tools/check_docs.py` with 25 tests; ruff 0.17.6 with rules
`E4`, `E7`, `E9` and `F` and four documented per-file exceptions; `docs` and `lint`
jobs in CI, with the checker's tests added to the `test` job; 24 source-line links
replaced. No file under `components/` changed, and the five suites report the same
counts as before (8; 34 with 11 skipped; 55; 93; 13 with 6 skipped).

**Proof in real CI.** All five jobs passed on the task branch. On a throwaway
branch, a link to a missing file, a link to a missing heading, a source-line link
and a comment line in a shell block each failed `docs`, and an unused import in
`gateway.py` failed `lint`, every message naming the file and line. The checker
changed after that run; the later changes are covered by its unit tests and by the
passing run on the final commit.

**Verifier findings and what was done.**

| Finding | Disposition |
|---|---|
| The grep criterion could not be met as worded | Reworded above; no source-line links remain |
| Missed: links with a title or angle brackets; shell fences written with attributes or `~~~`; a code block never closed; file names git would quote; other spellings of a source-line fragment; running from a subdirectory | Fixed, each with a test |
| False alarm: a link written as inline code | Fixed, with a test |
| Two replaced links named a function that did only part of what the sentence says | Corrected to `Invocation.open_upstream` and `error_response` |
| Not checked: reference-style and HTML links, links in indented code blocks, repo-root absolute links, targets with parentheses or a query, setext headings and named anchors, targets outside the repository | Accepted risk. None occurs in the repository's 66 Markdown files; the limits are stated at the top of the script |
| A `#` line inside a here-document in a shell block is reported though it would paste correctly | Accepted risk, stated at the top of the script. The fix is to keep such lines out of shell blocks |
| The lint exceptions are whole-file, so a new unused import in those four files goes unreported | Accepted until `package-shared-code` removes them. The narrower form would edit component code, which this task excludes |
| `README.md` and `workflow/ROADMAP.md` changed though the Scope list names neither | Noted: one sentence in the README's Tests section, and this task's roadmap row |

**Decided on the owner's behalf.** The setup-python action is used for the `docs`
job so it needs no project installation. The checker always checks the whole
repository, whatever directory it is run from.

**Left for the owner.** Add `docs` and `lint` to the required status checks in the
branch protection rule for `main`; new jobs are not required automatically.
