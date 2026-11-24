# Notes: improve-documentation

## Decisions made in flight

- Glossary entries are headings, not bold paragraphs, so the root README can link
  each term. Decided on the owner's behalf; it follows from the approved spec line
  that the README links each term's first use.
- Component READMEs take their paths from the quickstart's `lab.env` instead of
  repeating setup. This is what removes the variable hand-offs between READMEs.
- Three links and four anchors in frozen records were repaired because their targets
  moved. No other content in those records changed.
- One stale sentence in the signer README ("needs manual physical lock/unlock
  verification before Gate 7 acceptance") was corrected; the check was done at
  acceptance.

## Discoveries

- A clone in a folder Docker cannot share makes Keycloak fail with the realm file
  "Is a directory". Found when the first proof run used a scratch folder. Added to
  the quickstart's troubleshooting table and to Known pitfalls.
- `lab_exchange.py init-client` prints `component_03_succeeded`, which reads like a
  test result during setup. The quickstart now says what the line means; changing
  the message is a code change and is filed to the backlog.
- The walkthroughs link to source lines (`#L125`) that have drifted since they were
  written. Filed to the backlog.

## Proof run — 2026-11-24

Fresh clone of commit 20d732b under the home folder; `~/secure-claude-lab` was not
empty but held only earlier, unrelated lab directories. The owner did the browser
sign-ins.

- Quickstart steps 1 to 7, each command block run as extracted from the page: lab
  created, `Keycloak is ready`, three services healthy, broker exit 0 with
  `MOCK_OK — Local inference working`, shutdown clean.
- Gateway README: DPoP probe `component_05_succeeded`; Bearer profile
  `component_04_succeeded`; offline CLI check passed.
- Authorization server README: metadata-only curls as described (empty grant list,
  one key, HTTP 404 on the token route); Bearer probe `component_03_succeeded`.
- Sign-in README: `component_02a_login_succeeded`; 45 passed with Keycloak up.
- Mock README: health, JSON and streaming calls, and Claude Code pointed straight at
  the mock, which printed the `MOCK_OK` line.
- Test counts with `LAB_TLS_DIR` unset: 8; 34 and 11 skipped; 55; 93; 13 and 6
  skipped.
- After the run the quickstart's prose was corrected in four places; no command
  changed.

## Next action

Waiting for the verifier agent's findings; then disposition them, update PRODUCT.md
and the roadmap, and open the pull request.
