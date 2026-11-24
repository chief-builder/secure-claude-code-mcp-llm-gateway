# Release record: <version>

What was decided, what proved this release, and how to undo it. Started at step 1 of
the release playbook once the scope is approved and filled in as each step happens —
not retroactively. Kept after the ship: it is history like a spec, and the place the
rollback plan lives.

Status: verifying | waiting for ship approval | shipped <YYYY-MM-DD>

**Scope.** <Approved on <date>: what ships and what slipped, one line each slip with
its reason. The roadmap's current-release table carries the detail.>

**Verification.** <What was run against the built release and what it showed: the
commands, the acceptance criteria checked, the results.>

**Upgrade path.** <From <previous version>: what was exercised and what it showed.
Any compatibility break, and the spec or ADR that says it is intended.>

**Rollback plan.** <The signal that triggers a rollback, and how to roll back — or
why that is impossible and why that is acceptable.>

**Ship.** <Which commit was approved for shipping, by whom, when. The tag, and the
deploy confirmation if there was a deploy.>

## Next action

<One line, kept current: exactly where the release stands and what happens next.>
