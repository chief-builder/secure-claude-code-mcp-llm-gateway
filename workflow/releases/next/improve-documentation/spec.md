# Spec: improve-documentation

Consumes: [intent.md](intent.md)
Status: draft

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

- [ ] Following `docs/quickstart.md` literally, from a fresh clone and an empty
      `~/secure-claude-lab`, ends with the broker exiting 0 and printing `MOCK_OK`.
      Proven by one live run in which every command is taken from the page as
      written.
- [ ] Every command block in the five component READMEs that does not need a browser
      has been run as written, and the test command in each reports the counts the
      README states.
- [ ] All five component READMEs have the same section headings in the same order.
- [ ] `components/mock-llm/README.md` exists and its run and test commands work.
- [ ] Every relative link and every `#anchor` in every Markdown file outside `.venv`
      resolves, checked by a command whose output is recorded.
- [ ] Every term in the root README's standards table and architecture section has a
      glossary entry, and the glossary has no entry for a term the project does not
      use.
- [ ] `docs/README.md` lists every file under `docs/` exactly once, under either
      "how it works" or "how it was verified".
- [ ] `git diff main -- components '*.py' '*.swift' pyproject.toml uv.lock` is empty
      apart from README files, and all five offline suites still pass.
- [ ] The verifier agent, given only the repository, reports no step in the
      quickstart that it could not follow or that was ambiguous.

**Open questions.**

1. Should the quickstart be a page only, or a page plus a helper script?
   Recommended: page only.
2. Should the two Component 5 walkthroughs move to `docs/concepts/`, or stay where
   they are and only be linked from the index? Recommended: move, and repair the
   three links that point at them.
3. Should component and gate numbers disappear from README headings? Recommended:
   yes, kept as a one-line reference, with links from frozen records repaired.
