# Intent: ci-docs-and-lint-checks

Release: 0.2.0 · Roadmap line: ci-docs-and-lint-checks ·
Capability: Documentation

**Problem.** Three mistakes reached review in the last release cycle that a machine
could have caught, and nothing stops them recurring:

1. Renaming README headings broke six anchors in older documents. A one-off script
   found them; that script was never kept.
2. A quickstart block contained `#` comment lines. The default macOS shell rejects
   those when pasted, so the step failed for a real reader. An independent review
   caught it; the author's own proof run did not.
3. The two code walkthroughs link to source lines such as `gateway.py#L125`. The
   code has moved since, so those 24 links now point at the wrong lines.

Separately, no linter runs on the Python code, so an unused import or an undefined
name is only found by a test that happens to execute it.

**Why now.** It is small, and every later task in this release edits documents or
moves code. The shared-package refactor in particular will move many imports; a
linter should be watching when it does.

**Success looks like.** A pull request that breaks a link or anchor, adds a comment
line to a shell block, adds a source-line link, or introduces an unused import or
undefined name fails continuous integration with a message that names the file and
line.

**Constraints.** No change to the behavior of any component. The accepted security
code is not reformatted.
