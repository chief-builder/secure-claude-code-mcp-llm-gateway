# Hygiene

A cleanup pass over the workflow's state. Runs as the closing step of every release,
and standalone whenever asked ("run workflow hygiene") or when staleness is visibly
accumulating mid-cycle. The deliverable is state that tells the truth.

1. **Reconcile the roadmap.** Every task row's status matches reality. A task marked
   in-progress that nobody intends to finish is marked `abandoned` with a one-line
   reason (**confirm with the human** — abandoning is their call); its salvageable
   ideas go back to the backlog as lines.
2. **Walk the ADRs.** List the accepted ones by file name (a search for their
   `Status:` line) — no need to open each. Open only those whose area this release's
   changes touched — or, after a pivot, all of them — and check they still describe
   the code, or the new direction. An ADR that no longer matches reality either gets
   superseded by a new one or flagged to the human — never silently edited.
3. **Prune the knowledge surfaces.** `workflow/PROJECT.md`: drop pitfalls,
   conventions, and Workflow amendments that no longer apply (an amendment a later
   playbook change made redundant included), add lessons missed since the last pass;
   it loads every session, so it stays short — when pitfalls about one area pile up,
   move them together into a project skill (rung 2 of Capturing lessons).
   `workflow/PRODUCT.md`: capability statuses match what shipped, and capabilities
   whose features are all done are collapsed to one line. Project skills born from the lessons ladder: delete ones describing
   techniques or tools the project no longer uses.
4. **Sweep the backlog and debt register.** Keep them relevant to the direction.
   Merge duplicates on your own; propose dropping lines that no longer earn their
   place, and the human confirms. The filed-in tag says how long a line has waited —
   that is evidence, not by itself a reason. Promote what recent experience made
   urgent.
5. **Close out shipped task folders.** For this release's shipped tasks, delete
   lingering `notes.md` files after distilling anything durable into the spec or an
   ADR. The release record stays: it is history, and the rollback plan's home. A
   record of an earlier release still not marked shipped is flagged to the human —
   it was either shipped without closing the record, or abandoned. Among older specs, mark `superseded` only those whose area this release's
   changes touched and that no longer match the code. In `workflow/sketches/`: a
   `DECISION.md` whose direction this release built is marked `Status: built`; an
   older one whose area this release touched and that the code no longer matches is
   marked `superseded`; a parked one lives and dies with its backlog line — when
   step 4 drops the line, delete the folder.
6. **Check the branches.** Task branches for shipped or abandoned work get deleted
   (**human confirms** the abandoned ones — deletion is irreversible even if git
   reflog softens it).
7. **Hand off.** If the current-release table is now empty or fully shipped, say so
   and point at [plan-release.md](plan-release.md) as the next move.

**Report:** what was pruned, superseded, or abandoned, and anything flagged for a
human decision.
