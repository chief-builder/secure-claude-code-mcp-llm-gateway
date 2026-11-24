# Refactor

A behavior-preserving change: rename, extract, dedupe, move, simplify — or upgrade a
library, runtime, or tool the project depends on. The invariant is that observable
behavior does not change — the structure of the work must prove that.

0. **Open the task** per [_open-close.md](_open-close.md).
1. **Name the goal.** What gets easier after this change, for whom? For an upgrade:
   what it fixes, unlocks, or keeps supported. If you can't answer, don't do it.
2. **Check the net.** Confirm the affected code has test coverage that would catch a
   behavior change. If not, add characterization tests first — that's the first unit.
3. **Subtract first.** Delete dead code, unused parameters, and one-caller wrappers
   before restructuring what remains. Often the deletion is the whole refactor.
4. **Move in small equivalence steps.** Each step is a complete, behavior-preserving
   transformation with the full suite green, committed before the next. Never mix a
   behavior change into a refactor commit — if you discover a bug mid-refactor, stop
   and surface it separately. For an upgrade, read the changelog between versions
   before touching code; a behavior change it forces on you is surfaced, not absorbed.
5. **Migrate fully.** A new internal API replaces the old one in the same effort:
   migrate every caller and delete the legacy path. No parallel old/new states left
   behind.
6. **Prove equivalence.** Full suite green, and a spot-check on the real artifact for
   the paths you touched.
7. **Ship.** Land it per [_open-close.md](_open-close.md); the description states what got
   simpler (or what was upgraded) and how equivalence was proven.
8. **Close the task** per [_open-close.md](_open-close.md).

A refactor large enough to span sessions gets a task dir with a plan (the equivalence
steps as units) and `notes.md`, same as a feature.

**Report:** what got simpler (ideally with a line-count or layer-count delta), what
was deleted or upgraded, anything decided on the human's behalf, and confirmation
that behavior is unchanged.
