# Spec: ci-docs-and-lint-checks

Consumes: [intent.md](intent.md)
Status: draft

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

- [ ] `uv run python tools/check_docs.py` exits 0 on the repository and prints how
      many files and links it checked.
- [ ] The checker's own tests cover each of the four failure kinds and a passing
      case, and they run in the `test` job.
- [ ] On a scratch branch, each of these makes the named job fail in real CI, and is
      then reverted: a broken relative link (`docs`), a broken anchor (`docs`), a
      comment line in a shell block (`docs`), a source-line link (`docs`), an unused
      import in a component (`lint`).
- [ ] `grep -rE '\.(py|swift)#L[0-9]+'` over the Markdown files finds nothing.
- [ ] `uv run ruff check` exits 0, and every per-file exception in `pyproject.toml`
      carries a comment saying why it exists and which task removes it.
- [ ] `git diff main -- components` shows changes to Markdown files only, and all
      five offline suites report the same counts as before.

**Open questions.**

1. Lint depth: small rule set with the existing findings listed as exceptions
   (recommended), or also fix the test-fixture imports now, or broader rules and the
   formatter?
2. Docs checker: a small script kept in the repository (recommended), or a
   third-party tool?
3. Source-line links: replace with file links and ban them (recommended), or keep
   them and correct the numbers?
