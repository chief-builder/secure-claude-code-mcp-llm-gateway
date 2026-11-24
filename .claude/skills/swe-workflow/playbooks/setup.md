# Setup

Adopting this workflow in a project, run once after the template files are copied in
("set up the workflow", "adopt swe-workflow", or a first task in a project whose
`workflow/PROJECT.md` is still placeholders). The deliverable is a working setup the
user shaped, not a form the user filled in alone.

1. **Check the ground.** Confirm the template files landed (CLAUDE.md, `.claude/`,
   `workflow/`) and the project is a git repository — offer `git init` if not. If a
   pre-template CLAUDE.md existed, its content belongs in `workflow/PROJECT.md`;
   merge it there, don't lose it.
2. **Draft PROJECT.md.** Two starting points:
   - **Existing codebase:** draft from evidence. Read the code (delegate breadth to
     `explorer`): build/test/lint/run commands from the manifests and CI config,
     architecture and boundaries from the structure, conventions from the code
     itself, where the version number lives, and the Design section — whether there
     is a UI and what it targets, and any design system or component library in use.
     Fill every section you can from observation and verify the commands actually run. Draft first, ask second — the
     user corrects a concrete draft faster than they answer a blank questionnaire.
   - **Greenfield (nothing to read):** the facts don't exist yet, so they get
     decided, not inferred. Elicit what's being built and for whom, then propose a
     technology stack and starting architecture as a recommendation with
     alternatives — that choice is the project's first ADR. The first roadmap task
     is then the skeleton: scaffold, test harness, a walking end-to-end sliver —
     run through the feature chain like any task. PROJECT.md's commands and
     architecture sections get filled and verified as the skeleton lands, not
     guessed up front.
3. **Set the process profile.** Propose every profile value from what you observed
   (options, per-phase starting points, and signals: the skill's "The process
   profile" section) with a recommended answer each, batched per Thought
   partnership. Recommend the lightest setting the evidence supports — a solo project
   in exploration gets direct push, no CI, no deploy, and that is a correct setup, not
   a shortcut. Also propose which playbooks this project won't need, listed as unused
   in the profile (never deleted — upgrades overwrite the skill folder).
4. **Draft PRODUCT.md.** Who the users are and what they need, the capability map,
   and what the product won't be. Existing codebase: infer the capabilities from what
   the code does today and mark them done; the user corrects. Greenfield: this is the
   shape conversation, run [shape.md](shape.md) for the core idea. Keep it short;
   it grows with every shape.
5. **Ask the remaining judgment calls.** What observation can't settle, elicit per
   Thought partnership — batched, each with a recommended answer: what "working"
   means for this software, boundaries that matter but aren't visible in the code yet,
   anything the user wants done differently from a playbook (lands in Workflow
   amendments), and — for a project with a UI — the Design system link if it has one
   in Claude Design (the code can't show that).
6. **Seed the roadmap together.** Elicit the direction paragraph and the first
   release's theme and candidate tasks; capture what the user says, in their words,
   into `workflow/ROADMAP.md`. If they don't know yet, leave honest placeholders and
   a backlog of what they mentioned — don't invent a roadmap.
7. **Wire what the profile turned on.** If CI is on, draft a starter CI file for the
   project's host that runs the test and lint commands from PROJECT.md; the user
   approves it. If the merge path is a pull request, draft a short pull-request
   template that asks for the spec link. Nothing is drafted for a profile value that
   is off.
8. **Point out what the template can't do.** Host-side setup only the user can
   perform: branch protection on `main` if the merge path needs it, CI secrets,
   deploy credentials. Name it, don't attempt it.
9. **Verify.** A fresh look at PROJECT.md, PRODUCT.md, and ROADMAP.md passes the
   zero-context test: accurate, plain, and the commands run.

**Report:** what was inferred vs. asked, the profile chosen, what was marked unused,
and the host-side steps left for the user.
