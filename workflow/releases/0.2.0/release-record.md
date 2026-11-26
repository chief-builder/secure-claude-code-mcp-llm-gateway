# Release record: 0.2.0

What was decided, what proved this release, and how to undo it.

Status: waiting for ship approval

**Scope.** Approved on 2026-11-26. Shipped: `ci-docs-and-lint-checks`,
`package-shared-code`, `shape-aws-hosted-identity`, `shape-mcp-gateway`, and the
billing check from `close-pending-checks`. Slipped to the next release, by the
owner's choice to do them later: the other three checks in `close-pending-checks`
(reachability from a second device, a gateway call with a debugger-recovered token,
and signing during screen lock).

**Verification.**

- Offline suites, lint and documentation check pass in continuous integration on
  `main` at `7bbdedc`, on Python 3.12 and 3.14, and locally: mock 8 passed; sign-in
  34 passed and 11 skipped; authorization server 55 passed; gateway 93 passed;
  broker 13 passed and 6 skipped; tools 28 passed.
- The offline check with the installed Claude Code CLI passed.
- Live lab, 2026-11-25, from a fresh clone of the refactored code with the owner
  signing in: the broker with the software key, the DPoP probe, and the broker with
  the Secure Enclave signer all succeeded. Everything merged since then is
  documentation, apart from pinning the build tool, one redundant line removed from
  a test, and new guard tests; none of it was followed by another live run.
- Not verified for this release: the Bedrock backend, and a deployment to another
  host. The two remedies for a copied-folder deployment were checked on the
  owner's Mac only.

**Upgrade path.** From 0.1.0, exercised on 2026-11-26 in a throwaway clone: checked
out `v0.1.0`, installed, ran all five suites; switched in place to `main`, ran
`uv sync --locked`, and ran all five suites, the tools tests, lint, the
documentation check and the offline Claude Code check. Everything passed with the
same counts. The one required action for a user is to run `uv sync` again. There is
no stored data to migrate: lab keys, policies and replay databases are unchanged in
format. A lab created under 0.1.0 was not started under 0.2.0 as part of this
exercise. The one compatibility break, a copied-folder deployment needing
`PYTHONPATH` or `uv sync`, is intended and recorded in the `package-shared-code`
plan and the changelog.

**Rollback plan.** Nothing is deployed, so a rollback is removing the tag and the
GitHub release. A user who hits a problem can return to `v0.1.0` with
`git checkout v0.1.0` and `uv sync --locked`. The signal would be a documented
command that fails after the update, or a secret found in the tagged history. For a
defect, the normal course is a fix and a new release.

**Ship.** Not yet shipped. Waiting for the owner to approve tagging.

## Next action

Owner approves the ship. Then: merge this record to `main`, tag that commit
`v0.2.0` once continuous integration passes on it, publish the GitHub release with
the 0.2.0 changelog section, set Status to shipped, run hygiene, and plan 0.3.0.
