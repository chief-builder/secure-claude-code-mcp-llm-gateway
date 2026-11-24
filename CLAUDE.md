# Workflow contract

This file is owned by the workflow template — don't edit it per project; template
upgrades overwrite it. Everything project-specific lives in the imported file below.

@workflow/PROJECT.md

## Workflow

This project is orchestrated through the `swe-workflow` skill. For any coding task,
invoke it first — it owns the process: playbooks, the artifact chain under
`workflow/`, the product file, the roadmap, gates, pausing/resuming, and how lessons
get captured. How much process runs is set by the process profile in
`workflow/PROJECT.md`.

The rules that hold even when the skill isn't loaded:

1. **Understand before changing.** Read the affected code before proposing a design
   or a fix.
2. **Small verifiable units, proven on the real artifact.** Commit in steps that each
   end in a passing check; "done" means the app runs, the tests pass, the bug is
   demonstrably gone. Compiles ≠ works.
3. **The current system is described by the code, `workflow/PROJECT.md`,
   `workflow/PRODUCT.md`, the ADRs, and the roadmap** — never by old task artifacts,
   which are frozen history. To learn how something works, start from those; old
   task folders under `workflow/releases/` answer *why* it came to be that way.
4. **Plain language.** Everything written for people is understandable on first read
   without this conversation's context; names, numbers, and commands stay exact.
5. **Sketches live under `workflow/`.** `/sketch` saves to the task folder's
   `sketches/` for an open task, otherwise `workflow/sketches/<topic>/`, and is
   committed with whatever links to it.

Human gates: spec approval, plan approval (when being wrong would be expensive to
undo), code review as the profile's merge path defines it, and anything irreversible
(deploys, data deletion, force-pushes, external messages, and the ship itself).
Everything else proceeds autonomously.

People new to this workflow have a guide: the `swe-workflow-guide` mod shows where
the work stands above the prompt, `/wf` opens the full guide, and `/wf-explain
<topic>` explains one part. When someone seems unsure how to engage — what to say,
why Claude stopped, what a term means — point them to it.

Project knowledge — commands, architecture, conventions, branching, the process
profile, known pitfalls — is read from and maintained in `workflow/PROJECT.md`,
never here.
