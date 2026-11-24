# Feature

New or changed behavior. You own the design; delegate implementation, keep judgment.

0. **Open the task** per [_open-close.md](_open-close.md).
1. **Understand.** Map the affected subsystem — how it works today, its data shapes,
   its boundaries. Delegate breadth to `explorer`; read the load-bearing files yourself.
2. **Intent.** Write the task's `intent.md`: the problem, who it's for, why now, what
   success looks like, which capability in `workflow/PRODUCT.md` it serves. If the
   user stated this crisply, capture it, don't re-invent it. If it's vague or rests on
   unstated assumptions, elicit first per the skill's Thought partnership rules —
   probe what's observable, ask the judgment calls with recommended answers — before
   committing words to the artifact.
3. **Spec.** If the project has a UI and the feature adds or changes a screen whose
   layout no linked `DECISION.md` settles, and more than one arrangement is plausible,
   offer `/sketch` first; run it on a yes. Its closing next-step question maps onto
   this playbook: *build it* and *visual design first* both continue with this step
   (the visual design happens in step 4); *stop here* pauses the task per Pausing and
   resuming. Write the task's `spec.md`: behavior, scope, explicit non-goals,
   acceptance criteria a machine or a human can check. When a sketch direction exists,
   the spec links its `DECISION.md` and turns the Handoff's "Must keep" items into
   acceptance criteria. **Stop for human approval** — presented as a decision, not a
   document: lead with the forks that shaped it, your recommendation on each, and what
   you deliberately scoped out. If autonomy is collapsed (profile or the user's word),
   decide on your recommendation, record it, and carry the forks into the report
   instead.
4. **Design.** Name the core data shapes and their organizing structure before writing
   logic. If more than one design is genuinely viable, lay out the real alternatives
   with trade-offs and pick one; record a structural choice as an ADR. If the user
   chose a visual design step for a screen, it happens now, before the plan, bound by
   the Handoff's "Must keep" and linked from the spec: in Claude Design if the project
   has it, otherwise in the user's own tool, or skipped on their word. It follows the
   design system named in `workflow/PROJECT.md`; if there is none and this step
   creates one, record where it lives on that line.
5. **Plan.** Write the task's `plan.md`: small units, each ending in a check
   (a test, a command, an observable behavior). Order them so the sequence proves
   itself. Human approval only when being wrong would be expensive to undo.
6. **Build.** One unit at a time: implement (yourself or via `implementer` with a
   scoped brief), verify the unit's check, commit. Tests accompany the behavior they
   test, written before or with the code — not batched at the end.
7. **Verify whole.** Run the acceptance criteria against the real artifact — launch
   the app, hit the endpoint, click the UI. Then send the `verifier` agent to refute
   your claim of done.
8. **Capture lessons.** Anything this task taught the hard way — a gotcha, a
   technique, a failed approach — gets encoded now per the skill's Capturing lessons
   ladder, on first occurrence, before the context that holds it is gone.
9. **Ship.** Self-review the full diff for scope creep and leftovers, sync artifacts
   with what was actually built, update the product file's capability map, then land
   the code per [_open-close.md](_open-close.md) with a description that links the spec.
10. **Close the task** per [_open-close.md](_open-close.md).

**Report:** what you built, the key design choice and why, how it was verified,
anything decided on the human's behalf (with the reason), and any open decisions.
