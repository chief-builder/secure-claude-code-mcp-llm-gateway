# Release

Cutting a release. The deliverable is a shippable, tagged version with a proven upgrade
path, plus a workflow left clean for the next iteration. Formality follows the
profile's phase: in exploration a release may be just a tag and a changelog line;
stabilizing and production run every step.

The release keeps a record, `workflow/releases/<version>/release-record.md` (template:
[templates/release-record.md](../templates/release-record.md)), filled in as each step
happens, its "Next action" line kept current whenever work stops. It is what lets a
fresh session resume a release halfway, and where the rollback plan lives after the
ship. In exploration it is skipped with a reason unless
the release spans sessions.

1. **Freeze scope.** Reconcile the roadmap's current-release table with reality: what
   actually shipped, what slips to next release. Update `workflow/ROADMAP.md`; slipped
   items move to the next-release section with a one-line reason. **Human approves the
   final scope.** Then start the release record with the approved scope, `Status:
   verifying`.
2. **Verify the release, not the branch.** Full suite green is the floor, not the
   proof. Run the acceptance criteria of the release's headline changes against the
   built artifact — the thing users will actually get, built the way they'll get it.
   Record what was run and what it showed.
3. **Verify the upgrade path.** Exercise the path from the *previous released version*
   to this one: data migrations, config changes, API compatibility for whatever
   consumers exist. A fresh install passing is not evidence that an upgrade works.
   If this release breaks compatibility, confirm the break is documented and intended
   (spec or ADR), not accidental. Record what was exercised and what it showed.
4. **Write the changelog.** Add this release's section to the root `CHANGELOG.md`,
   assembled from the shipped specs and fixed bugs — user-facing language, organized
   by what changed for whom. The specs are the source; don't re-derive from commit
   messages.
5. **State rollback before shipping.** Write into the release record what signal would
   trigger a rollback and how rollback works (or that it's impossible and why that's
   acceptable), and set `Status: waiting for ship approval`. **Human approves the
   ship** — tagging/deploying is an irreversible act. The approval holds for the commit
   it was given for and the session that gave it: a fresh session resuming at this
   step re-presents the gate, it never acts on an approval it can't see.
6. **Tag and ship.** Version bump where PROJECT.md says the version lives, tag,
   release notes attached. What you tag and distribute is exactly what you verified
   in steps 2 and 3 — if anything landed in between, verify again first. Record the
   approved commit and the tag, and set `Status: shipped <date>`. If the release
   folder under `workflow/releases/` was named with a placeholder like `next`, rename
   it to the version now; the record moves with it.
7. **Deploy and confirm.** Only if the profile names a deploy target. Deploy the way
   the profile says (manual steps are handed to the human; automated ones run under
   the approval given in step 5), then confirm the release works where users actually
   get it — not just where it was built; record the confirmation. The rollback plan
   in the release record is what you reach for if it doesn't.
8. **Hygiene pass.** Run [hygiene.md](hygiene.md) in full, so the next iteration
   starts from state that tells the truth.

**Report:** what shipped and what slipped, upgrade-path evidence, the rollback plan,
deploy confirmation if any, and what the hygiene pass changed.
