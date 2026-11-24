# Shape

An idea that isn't a task yet: "I want users to be able to…", "help me think through
X", "what should this product do about Y". The deliverable is a clear picture of the
capability — who it's for, what it does, what the smallest useful version is — landed
in `workflow/PRODUCT.md` and the backlog. No spec, no code; specs come later, per task.

This is a conversation, not a form. It is also where your broad knowledge earns the
most: you know what products like this one usually need. Propose; don't just ask.

1. **Find the user and the job.** Who has this need, and what are they trying to get
   done? Read `workflow/PRODUCT.md` first — the user may already be described, and
   the idea may already be a capability with a gap. Ask only what you can't infer.
2. **Propose the capability.** Name it, and list the features that would make it
   real, one line each. Mark which ones make the smallest version that is actually
   useful and which can wait. Say what's already there in the code that this builds on.
   If the project has a UI (the Design section of `workflow/PROJECT.md`) and the idea
   turns on how users find, see, or move through things — navigation, layout, a
   whole-app UX reset — offer to work it out visually with `/sketch` instead of in
   lists; run it on a yes. The sketch's closing next-step question maps onto this
   playbook: *build it* or *visual design first* puts the first slice in the current
   release (its line noting a visual design step when chosen); *stop here* leaves it
   in the backlog. Either way the direction lands in step 5 — shape never builds.
3. **Challenge it.** Say whether it earns its place against the direction and the
   "not this" list. If a smaller idea gets most of the value, propose that. If it
   doesn't fit, say so — "no" is a valid recommendation.
4. **Decide together.** Present the forks with your recommendation (per Thought
   partnership). The human chooses the shape.
5. **Land it.** Add or update the capability in the product file's map with its
   features and statuses. Add the chosen first slice to the roadmap's backlog (or the
   current release, if the human says so), one line per task, each naming the
   capability. If a sketch session kept a direction, the capability and each of those
   backlog lines link its `DECISION.md`, so the feature that picks one up starts from
   the agreed structure. A parked sketch gets one backlog line linking its
   `DECISION.md`, so it isn't lost. If the conversation settled a real decision,
   record it as an ADR.

**Report:** the capability in one paragraph, the smallest useful version, what was
deferred, and what the human decided.
