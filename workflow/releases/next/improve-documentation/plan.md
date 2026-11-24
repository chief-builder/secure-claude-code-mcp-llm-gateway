# Plan: improve-documentation

Consumes: [spec.md](spec.md)

**Design summary.** Four document kinds, each with one home: the quickstart
(`docs/quickstart.md`), task-based component READMEs with one shared heading set,
explanations (`docs/concepts/`), and frozen verification history
(`docs/component-NN/`). `docs/README.md` is the index that tells them apart. Plan
approval is not required: the change is documentation only and fully reversible.

**Units.**

| # | Unit | Check | Status |
|---|------|-------|--------|
| 1 | Glossary | Every term in the root README's standards table has an entry | **done** |
| 2 | Move the two walkthroughs to `docs/concepts/`, add the request walkthrough, repair links | Link check passes | **done** |
| 3 | `docs/README.md` index | Lists every file under `docs/` exactly once | **done** |
| 4 | Quickstart | Live run following it literally ends in `MOCK_OK` | **done** |
| 5 | Five component READMEs with one heading set, including a new mock README | Headings identical; non-browser commands run as written | **done** |
| 6 | Root README points to the quickstart, index and glossary | Link check passes | **done** |
| 7 | Whole-task verification: link check, code diff empty, suites pass, verifier agent | All acceptance criteria met | in-progress |

**Risks.** Renamed README headings break anchors that frozen records link to; the
link check in unit 7 covers anchors as well as files. The quickstart can only be
proven by a live run, which needs the owner present for one browser sign-in.
