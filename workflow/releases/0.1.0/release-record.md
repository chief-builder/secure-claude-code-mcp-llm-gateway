# Release record: 0.1.0

What was decided, what proved this release, and how to undo it.

Status: waiting for ship approval

**Scope.** Approved on 2026-11-25: everything on `main` — Components 1 to 8, the
publication fixes, the single `uv` environment, continuous integration, the adopted
workflow, and the documentation task. Nothing slipped; the unfinished items were
never in this release and are on the roadmap's backlog.

**Verification.**

- Offline suites on the merge commit `28af6e2`, in continuous integration on Python
  3.12 and 3.14: mock 8 passed; sign-in 34 passed and 11 skipped; authorization
  server 55 passed; gateway 93 passed; broker 13 passed and 6 skipped. The secret
  scan found nothing.
- Live lab, 2026-11-24, from a fresh clone with the owner signing in: every
  quickstart command block run as written, ending in broker exit 0 and
  `MOCK_OK`; the Bearer and DPoP probes; the sign-in client; 45 of 45 sign-in tests
  with Keycloak up.
- Live lab, 2026-11-23: the broker with the Secure Enclave signer and the installed
  Claude Code CLI.
- Not re-verified for this release: the Bedrock backend, last run live on
  2026-11-23 before the publication fixes; and the full quickstart after its final
  wording changes, of which only the changed command blocks were re-run.

**Upgrade path.** None. This is the first release; there is no earlier version and
no stored data to migrate.

**Rollback plan.** Nothing is deployed, so a rollback is removing the tag and the
GitHub release. The signal would be a secret found in the tagged history, or a
defect that breaks a property the README claims. For a defect, the normal course is
a fix and a new release, not removing 0.1.0.

**Ship.** Not yet shipped. Waiting for the owner to approve tagging.

## Next action

Owner approves the ship. Then: merge this record to `main`, tag that commit
`v0.1.0`, publish the GitHub release with the 0.1.0 changelog section, and set
Status to shipped with the commit and date.
