# Spec: improve-documentation

Consumes: [intent.md](intent.md)
Status: **approved** (2026-11-24)

**Behavior.** After this change the documentation has four clearly separate parts.

- **One quickstart** (`docs/quickstart.md`): the whole lab from a fresh clone to the
  broker running Claude Code against the mock, in one page, with every variable
  defined where it is first used. It covers the DPoP profile with the software
  signer, and ends with how to shut down and clean up. The Secure Enclave signer and
  the Bedrock backend are linked as optional next steps, not included.
- **Component READMEs organised by task.** Each of the five has the same sections in
  the same order: what it is, how to run it on its own, how to test it, how it
  works (links), and its limits. Component and gate numbers remain as a one-line
  reference, not as headings. The mock LLM gets a README for the first time.
- **Explanation separated from evidence.** A `docs/README.md` index sorts every
  document into "how it works" or "how it was verified". The two Component 5 code
  walkthroughs move to `docs/concepts/`, joined by one new page that walks a single
  request from sign-in to the model's reply.
- **A glossary** (`docs/glossary.md`) defining each protocol and project term in two
  or three plain sentences, with a link to its standard. The root README links each
  term's first use to it.

The root README links to the quickstart, the docs index and the glossary, and its
"Running the lab" section shrinks to a pointer.

**Scope.** `README.md`, the five component READMEs and the signer README,
`docs/README.md`, `docs/quickstart.md`, `docs/glossary.md`, `docs/concepts/`, and
link repairs in existing documents whose targets move.

**Non-goals.**

- No setup script. A script would hide the steps a learner is here to see; the
  quickstart stays copy-and-paste.
- No rewrite of design specs or verification records. Only links in them that would
  otherwise break are repaired.
- No automated link checker in CI. Links are checked once by command; a standing
  check is filed to the backlog.
- No documentation for MCP, which is not built.
- No diagrams beyond the one already in the root README, except where the new
  request walkthrough needs one.

**Acceptance criteria.**

- [x] Following `docs/quickstart.md` literally, from a fresh clone and an empty
      `~/secure-claude-lab`, ends with the broker exiting 0 and printing `MOCK_OK`.
      Proven by one live run in which every command is taken from the page as
      written.
- [x] Every command block in the five component READMEs that does not need a browser
      has been run as written, and the test command in each reports the counts the
      README states.
- [x] All five component READMEs have the same section headings in the same order.
- [x] `components/mock-llm/README.md` exists and its run and test commands work.
- [x] Every relative link and every `#anchor` in every Markdown file outside `.venv`
      resolves, checked by a command whose output is recorded.
- [x] Every term in the root README's standards table and architecture section has a
      glossary entry, and the glossary has no entry for a term the project does not
      use.
- [x] `docs/README.md` lists every file under `docs/` exactly once, under either
      "how it works" or "how it was verified".
- [x] `git diff main -- components '*.py' '*.swift' pyproject.toml uv.lock` is empty
      apart from README files, and all five offline suites still pass.
- [x] The verifier agent, given only the repository, reports no step in the
      quickstart that it could not follow or that was ambiguous.

**Open questions.** None. Decided at approval on 2026-11-24: the quickstart is a
page only; the two Component 5 walkthroughs move to `docs/concepts/`; component and
gate numbers leave the README headings.

## Outcome — 2026-11-24

All acceptance criteria met, with one stated deviation.

**Proof run.** A fresh clone under the home folder; the owner did the browser
sign-ins. Every quickstart command block was run as extracted from the page: lab
created, `Keycloak is ready`, three services healthy, broker exit 0 with
`MOCK_OK — Local inference working`, clean shutdown. Every command block in the
five component READMEs was also run as written, including the Bearer and DPoP
probes (`component_03_succeeded`, `component_04_succeeded`,
`component_05_succeeded`), the sign-in client, the offline CLI check, and Claude
Code pointed straight at the mock. Test counts matched the READMEs: 8; 34 with 11
skipped (45 with Keycloak up); 55; 93; 13 with 6 skipped.

**Deviation.** `~/secure-claude-lab` was not empty during the run; it held earlier,
unrelated lab directories. Accepted: the quickstart creates uniquely named
directories and cannot collide with them.

**Link check.** A one-off script resolved every relative link and heading anchor in
all Markdown files. Final output: `62 files, 245 relative links checked, 0 broken`.
The script is not kept; a standing check in CI is on the backlog.

**Verifier findings and what was done.**

| Finding | Disposition |
|---|---|
| The lab-creation block had `#` comment lines, which the default macOS shell rejects when pasted, so step 2 failed for a real reader. The proof run missed it because it ran the block non-interactively | Fixed: comments moved into prose. Reproduced the failure, then pasted the corrected create, load and cleanup blocks into an interactive default shell successfully |
| The sign-in README's test count was wrong when the lab paths were loaded but Keycloak was stopped, and the instruction to unset `LAB_TLS_DIR` had been dropped | Fixed: the README lists all three cases |
| The link check's output and the non-empty lab folder were not recorded against the criteria | Recorded above |
| Several glossary terms were not linked from the root README | Fixed: linked in prose, and the diagram's terms in one sentence below it |
| Six small imprecisions: which service records what for replay protection; signature and issuer check order; what the child process receives; the cleanup instruction; a troubleshooting row; no glossary entry for Keycloak | All fixed |

**Decided on the owner's behalf.** Glossary entries are headings so they can be
linked. Component READMEs take their paths from the quickstart's `lab.env`. Three
links and six anchors in frozen records were repaired because their targets moved,
and one stale sentence in the signer README was corrected; nothing else in those
records changed.
