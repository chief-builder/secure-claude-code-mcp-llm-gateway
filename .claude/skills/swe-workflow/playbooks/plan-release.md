# Plan release

Deciding what the next release contains. Runs after a release ships (hygiene ends by
pointing here) or whenever the current-release table is empty or stale. The
deliverable is a roadmap that tells the truth about what comes next.

Formality follows the profile's phase. In exploration, "release" just means "the next
few things to do" — no version numbers required, keep it to a few minutes. In
stabilizing or production, it has a version and a theme and precedes every cycle.

1. **Look back.** For what shipped last release, ask whether it did what its intent
   said success would look like — where there is evidence (usage, feedback, the
   metric named). Say what was learned; a feature that didn't land its outcome is a
   candidate for follow-up or removal, not silence. Skip when nothing has shipped yet.
   Either way, check the process profile: compare `workflow/PROJECT.md`'s profile
   against the signals in the skill's "The process profile" section, using the
   evidence at hand — git authors, bugs that reached `main`, who relies on the app,
   how deploys and fixes went. If a value no longer fits, up or down, propose the
   change with its one-line reason; the human decides. Usually nothing fits — say so
   in one line.
2. **Propose the theme.** One line: what this release is for. Draw it from the
   roadmap's Direction, from what the look-back taught, and from which capabilities
   in `workflow/PRODUCT.md` are thinnest relative to what users need. The human sets
   it.
3. **Propose the tasks.** Walk the backlog and the debt register; propose the set that
   serves the theme, each with a one-line reason and the capability it advances.
   Include debt where it is now costing more than it would cost to fix. The human
   says yes, no, or swap.
4. **Reset the roadmap.** Name the new version, clear the previous release's shipped
   and abandoned rows (the changelog and the release folders hold them), move the
   chosen tasks into the current-release table as `backlog`, leave everything else
   where it is.
5. **Prune while you're here.** Propose dropping backlog and debt lines that no
   longer earn their place against the direction; the human confirms. The filed-in
   tag is evidence of how long a line has waited, not by itself a reason. Merge
   duplicates.

**Report:** what the look-back taught, the theme, the chosen tasks and why, what was
deliberately left out, and what was pruned.
