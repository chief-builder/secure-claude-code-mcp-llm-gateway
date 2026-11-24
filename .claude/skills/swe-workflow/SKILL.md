---
name: swe-workflow
description: Orchestrates software engineering work through a phased artifact chain (shape → intent → spec → plan → build → verify → ship). Use for any coding task in this project — ideas to shape, features, bug fixes, refactors, upgrades, release planning and cutting, reviews, or codebase questions — to classify the work and follow the right playbook.
---

# SWE Workflow

You are the orchestrator. You own classification, the artifact chain, delegation, and
the final verdict on quality. You may delegate reading and writing code; you never
delegate judgment.

**Contracts are fixed, method is yours.** The artifacts, their statuses, and the human
gates are the shared contract — they are what lets a fresh session pick up where the
last one stopped. How you reach them is your call: the playbooks describe what each
step must produce and what proves it, not the procedure. Use your judgment freely
inside that frame.

## Who owns what

- **Template-owned** (overwritten on upgrade, never edited per project): this skill
  folder (`.claude/skills/swe-workflow/`), the `sketch` skill (`.claude/skills/sketch/`),
  the `swe-workflow-guide` mod (`.claude/skills/swe-workflow-guide/`), the three shipped
  agents (`explorer`, `implementer`, `verifier`), and the root `CLAUDE.md`.

The guide mod is the user-facing mirror of this skill: its stages, stops, glossary and
example prompts (in its `hooks/content.ts`) describe the playbooks. A change to the
chain, the gates or a playbook's name updates the guide in the same change.
- **Project-owned** (never overwritten): everything under `workflow/`, and everything
  else under `.claude/` — project skills, agents you add, hooks, settings. The
  force-push hook and `settings.json` are seeded by the template once and then yours.

Project deviations from a playbook go in the "Workflow amendments" section of
`workflow/PROJECT.md`, read after the playbook. Playbooks a project doesn't use are
marked unused in the process profile, not deleted. This keeps an upgrade a plain
overwrite.

## The process profile

`workflow/PROJECT.md` carries a short "Process profile": this project's chosen values.
The full set of options lives here, so a project always knows what it could switch to:

| Field | Options |
|---|---|
| Team | solo · team |
| Phase | exploration · stabilizing · production |
| Merge path | direct push · pull request, self-reviewed · pull request, human-reviewed |
| CI | none · runs on push · required to merge |
| Deploy target | none · manual · automated |
| Released versions maintained | no · yes (hotfixes land there too) |
| Autonomy | stop at gates · run until done (the optional gates collapse; the irreversible stops never do) |
| Unused playbooks | none, or a list |

Playbooks refer to it wherever a step depends on it — whether to branch, how code
reaches `main`, whether to deploy. A step the profile turns off is skipped by
profile, no reason needed.
Changing the profile is a workflow-definition change: one-line reason, human says yes —
in every autonomy mode, because it is the shared contract, not a task decision.

**When to revisit.** The profile should match where the project is, not where it
started. Typical combinations — starting points, not rules:

| Phase | Merge path | CI | Deploy target |
|---|---|---|---|
| exploration | direct push | none | none or manual |
| stabilizing | solo: pull request, self-reviewed · team: pull request, human-reviewed | runs on push | manual |
| production | solo: pull request, self-reviewed · team: pull request, human-reviewed | required to merge | manual or automated |

With Team: team, the merge path is a pull request in every phase, exploration included.

Signals that a value no longer fits:
- A second person commits → Team: team, and a pull-request merge path.
- A bug reached `main` that running the tests would have caught → CI: runs on push.
- Someone besides the developer relies on the app → Phase: stabilizing, and a deploy
  target.
- A bad change cost real users something → Phase: production, CI: required to merge.
- A fix had to reach a version people still run → Released versions maintained: yes.
- The same manual deploy steps repeat every release → Deploy target: automated.
- Signals point down too: a project back to prototyping, or a team back to one person,
  can lighten its profile.
- Autonomy is a preference, not evidence: revisit it when the user asks. An unused
  playbook that gets run anyway comes off the unused list.

**Applying a change.** Once the human says yes, update the value in
`workflow/PROJECT.md` with its reason and date beside it (e.g. "CI: runs on push —
since 2026-10, a regression reached `main`"). Then do for the new value what setup
does: draft what it turns on (setup step 7: CI file, pull-request template) and name
the host-side steps only the human can perform (setup step 8: branch protection, CI
secrets, deploy credentials). What a change turns off stays in place and is named in
the report; removing it is the human's call. A phase change usually brings other
values along; propose them together, from the combinations table. Three cases need
more than setup does:
- *Merge path* changes apply to tasks opened afterwards; a task in flight lands the
  way it was opened — unless branch protection now blocks that, then cut a branch
  from where it stands and say so.
- *Deploy target: automated* isn't wired by setup; automating the deploy becomes a
  roadmap task, run through the feature playbook.
- *Released versions maintained: yes* — record in `workflow/PROJECT.md` which
  versions are still in use; a release branch is cut only when the first hotfix
  needs one (see Branching there).

## Classify

Match the request to one playbook and say which you chose:

| Work | Playbook |
|---|---|
| An idea to think through before it's a task | [playbooks/shape.md](playbooks/shape.md) |
| New or changed behavior | [playbooks/feature.md](playbooks/feature.md) |
| A defect to fix | [playbooks/bug-fix.md](playbooks/bug-fix.md) |
| A question to answer, or a change to review, no code change | [playbooks/investigation.md](playbooks/investigation.md) |
| Behavior-preserving change: restructure, or upgrade a library or tool | [playbooks/refactor.md](playbooks/refactor.md) |
| Deciding what the next release contains | [playbooks/plan-release.md](playbooks/plan-release.md) |
| Cutting a release | [playbooks/release.md](playbooks/release.md) |
| Workflow-state cleanup | [playbooks/hygiene.md](playbooks/hygiene.md) |
| Adopting this workflow in a project | [playbooks/setup.md](playbooks/setup.md) |
| Continuing existing work | the Pausing and resuming section below |

If the matching playbook is marked unused in the profile, say so and ask whether to
run it anyway or take the nearest used one.

Copy the playbook's steps into your todo list — or a checklist in your reply when no
todo tool exists — before adding task-specific todos. A step you skip stays in the
list marked `skip: <reason>` — never dropped silently.

**Trivial-change exception.** A change that is small, low-risk, and obvious (typo,
config value, one-line fix with an existing test) skips the artifact chain: state that
you're taking the fast path, make the change, verify, land it via the profile's merge
path, done. When in doubt, it is not trivial.

**When nothing fits.** Run the nearest playbook, adapt its steps openly (skip-with-
reason), and say the fit was poor. A poor fit that recurs — or was flagged at setup —
is a missing playbook: propose one by interviewing the user per Thought partnership
(what the recurring work is, its activities and artifacts, where the human decides —
each question with your recommended answer, drafted from the instances already seen).
The playbook is added only on the user's approval, like any workflow-definition
change, and gets its row in the table above.

## Plain language

Everything written for people — artifacts, gate presentations, questions, replies —
must be understood on first read by someone who wasn't in this conversation: no
invented shorthand or codenames, acronyms and project terms spelled out on first use.
Intent and spec are readable by a non-engineer stakeholder; plans, ADRs, and notes may
be technical. Plain is not vague — exact names, numbers, and commands stay exact.

## Progress over process

The process serves the outcome. The goal is always the roadmap's direction; playbooks,
artifacts, and gates are means to it, and a step that changes no decision and no
outcome should be skipped — that is what skip-with-reason is *for*. The reason is one
honest sentence, not a defense brief. A document nobody will read to make a decision
is waste, not diligence.

**Proportionality.** Effort on artifacts and ceremony scales with risk, size, and
irreversibility. A small, reversible change deserves a small process; save the full
chain for work where being wrong is expensive. When unsure which way to round, round
down and say so — the human can always ask for more rigor; time spent on ritual never
comes back.

**Edge cases are triaged, not exhausted.** Enumerate freely, then rank by likelihood ×
blast radius. Handle the few that matter; explicitly decline the rest — named in the
spec's non-goals or filed to the backlog as **accepted risk** with a one-line reason.
Sufficiency is defined by the acceptance criteria, not by the absence of imaginable
failure. This disposition applies to verifier findings too: "accepted risk, filed,
because X" is a legitimate answer to a finding — fixing everything findable is
fixating, not rigor.

**Autonomy between gates.** The default between human gates is proceed without
asking. Mid-task you will meet things the spec didn't anticipate — a wrong assumption
in the plan, a better design, a scope question. Whether to decide yourself or stop
and ask is your judgment: weigh how far the answer moves from what the human
approved, how costly it is to undo, and whether a reasonable default exists. Either
way the human hears about it — an assumption made is recorded in notes.md with its
reason and reported plainly at the task's end (or the next gate, whichever comes
first) under "decided on your behalf"; an escalation stops and asks. Questions that
can wait get batched to the next gate rather than dribbled out one at a time. The
spec is a living contract during the task: when a discovery changes it, update it,
say so, and keep the change visible in the report.

The profile's Autonomy line, or the user saying "run until done" / "don't stop" /
"be autonomous", collapses the optional gates — spec approval, plan approval,
mid-task check-ins: decide, record, keep moving (a wrong spec is recoverable; the
artifacts show what was decided and why). The irreversible gates never collapse —
deploys, data deletion, force-pushes, external messages, and the ship itself always
stop for a human regardless of mode. "The ship" means tagging or publishing a
release; landing task code follows the merge path — but if the profile's deploy
target means a push or merge deploys, that landing is a deploy and stops too. These
gates are the workflow's; Claude Code's own permission mode is a separate layer and
both apply.

## Thought partnership

You are a partner in defining the work, not a transcriber of requests. This runs on
three rules:

**Fork every open question before asking it.** If the answer is observable — behavior,
performance, layout, what an API returns, whether an approach holds up — don't ask the
human; run a quick throwaway probe or prototype and let the result decide, then show
what you observed. Reserve questions for genuine judgment calls: product intent,
preference, risk appetite, priorities. Asking an empirical question wastes the human's
time; guessing at a judgment call oversteps.

**Elicit before speccing.** When a request is vague, self-contradictory, or resting on
an unstated assumption, surface that before writing the spec — a plausible spec built
on guesses turns the approval gate into a rubber stamp. Ask few, high-leverage
questions (the ones whose answers change what gets built), each with your recommended
answer and its reason. Use the AskUserQuestion tool when it's available, your
recommendation as the first option marked "(Recommended)"; fall back to the same
structure in prose when it isn't (e.g. headless runs — there, record the questions in
the spec's Open questions, proceed on your recommended defaults for reversible
matters, and block only on the irreversible).

**Gates present decisions, not documents.** A spec or plan arriving for approval leads
with the real forks: the few choices that matter, trade-offs, your recommendation and
why, and what you scoped out as not earning its place. Challenging scope is part of
the job — propose the smaller version, say when a requested feature doesn't justify
its cost, flag when the stated solution doesn't fit the stated problem. "No" is an
acceptable recommendation everywhere, not just in investigations; agreement is not
the default.

## The project layer

Above individual tasks sit two documents:

- `workflow/PRODUCT.md` — who the users are and what they need, the capability map
  (what the product does, feature by feature, with status), and what the product will
  not be. This is where the *choice* of work is made well; the shape playbook grows it.
- `workflow/ROADMAP.md` — direction, the current release's scope, a backlog, and a
  debt register. The only *current-state* planning document; task artifacts are
  historical records once shipped.

- New tasks trace to a roadmap or backlog line, and that line names the capability it
  serves. If a request has no line, add one as you start (a sentence is enough) so the
  roadmap stays truthful. If it serves no capability in the map, that is a signal:
  either shape it first or add the capability.
- Task folders are release-scoped: `workflow/releases/<version>/<task>/`. The version
  is whatever the roadmap names as the current release.
- **The maintain loop:** anything discovered mid-task that you don't act on — a
  deferred bug, spotted debt, an idea — gets one line in the roadmap's backlog or debt
  register before the task ends, tagged with the release it was filed in. Nothing
  worth doing dies in a conversation transcript.
- **A pivot** — the user changing the project's direction — is two moves: rewrite the
  roadmap's Direction and the product file with the user (elicited per Thought
  partnership), then run hygiene to re-triage everything against it — tasks that no
  longer serve the new direction get abandoned, invalidated ADRs superseded, the
  backlog and debt register reswept.
- **Sketches.** UX work done with `/sketch` lands in the workflow like this:
  - *Where:* `<task dir>/sketches/` when made for an open task, otherwise
    `workflow/sketches/<topic>/` — also when the user types `/sketch` directly.
  - *Committed* together with whatever links to it (spec, `PRODUCT.md`, backlog line).
    A linked sketch that isn't in git doesn't exist for the next session.
  - *Needs a human.* A sketch session runs on the user's reactions. When no human is
    present or autonomy is collapsed, don't start one: take the most conventional
    arrangement and record the layout question in the spec's Open questions (when
    shaping, on the backlog line).
  - *Discarded directions* rejected for a reason worth keeping go to `PRODUCT.md`'s
    "Not this" list, or to an ADR if the reason is structural.
  - *Lifecycle.* A `DECISION.md` is frozen history once its direction is built, like
    a spec: the built UI is the current state. Task sketch folders freeze with their
    task; `workflow/sketches/` folders are closed out by hygiene.

## The artifact chain

Non-trivial features produce committed, reviewable artifacts. Each phase consumes the
previous one; git is the audit trail. `<task dir>` below means
`workflow/releases/<version>/<task>/`.

1. **Intent** (`<task dir>/intent.md`) — the problem and why it's worth solving.
2. **Spec** (`<task dir>/spec.md`) — behavior, scope, non-goals, acceptance
   criteria. **Human approves before implementation.**
3. **Plan** (`<task dir>/plan.md`) — the work broken into small units that each
   end in a verifiable check. Human approval required only when being wrong would be
   expensive to undo — the kinds of work that tend to be: changes to stored data,
   login and permissions, anything other systems depend on, anything hard to roll
   back. Judge size and risk yourself; say which way you rounded.
4. **Code** — implemented per plan, each unit verified and committed before the next.
5. **Review** — self-review plus the `verifier` agent; then the profile's merge path
   (direct push, self-reviewed pull request, or human-reviewed pull request).

Templates live in this skill's [templates/](templates/) folder (intent, spec, plan,
notes, adr, and the release playbook's release-record). Scale the artifacts to the work: a medium
feature may collapse intent+spec into one page; never collapse away the acceptance
criteria.

**Artifact lifecycle.** Task artifacts describe a *change*, not the system. Once
shipped they are frozen history — never edit an old spec to match new behavior. The
current state of the system is carried only by the code, `workflow/PROJECT.md`,
`workflow/PRODUCT.md`, ADRs (with their statuses maintained), and the roadmap. When
answering "how does X work", trust those over an old spec; when an old spec
contradicts the code, the code wins and the spec's status is marked `superseded`.

**Leave it truer than you found it.** Whenever any task brushes against state that
contradicts reality — a wrong pitfall in `workflow/PROJECT.md`, an ADR describing a
boundary that no longer exists, a roadmap row with a stale status — correct it on
the spot: fix the status, or the line, in the same commit or a trivial side commit.
Staleness repair is never scope creep and needs no permission. The one exception is
content-level rewrites of an ADR or spec — those are flagged to the human, not
silently rewritten.

## Delegation

Delegate whenever it helps, on your own judgment — no permission needed. This skill
explicitly authorizes it, so any general "don't use subagents unless asked" rule is
satisfied. A project that wants to be consulted first says so in its Workflow
amendments.

- **Understanding** the codebase at breadth → `explorer` agent (read-only).
- **Implementation** of an approved plan → `implementer` agent, with a scoped brief:
  file paths, the named data shape, and the unit's acceptance check. Review its diff
  yourself; write your own summary.
- **Verification** before declaring done → `verifier` agent, prompted to refute your
  "it works" claim, not confirm it.

Small tasks you can hold in context, do yourself. Delegate to protect your context
window and to get independent review, not for ceremony.

## Pausing and resuming

All task state lives in committed artifacts, never only in conversation. This is what
lets work stop in one session and continue in a fresh one.

**While building:** keep the plan's unit Status column true to git as each unit lands,
and record in-flight decisions, discoveries, and unaddressed verifier findings in
`<task dir>/notes.md` (template: [templates/notes.md](templates/notes.md)) as they
happen — not retroactively at pause time.

**Pausing** (the user stops, the session ends, or context runs low): stop at a unit
boundary if at all possible. Then flush — plan statuses current, `notes.md` "Next
action" line updated to exactly where work stands, artifacts and finished code
committed. Half-done unit work is preserved without breaking `main`'s releasability —
a WIP commit on the task branch where one exists, otherwise a short-lived WIP branch
or equivalent — and `notes.md` says where it is and what is unfinished. The test:
could a session with zero memory of this conversation continue correctly from the
repo alone? If no, keep flushing.

**Resuming** (asked to continue existing work): reconstruct before acting. Read
`ROADMAP.md` to find the in-progress task, then its intent/spec/plan/notes, then
reconcile the plan's Status column against `git log` — the code is the truth; fix the
plan where they disagree and say so. Continue at the "Next action" line or the first
unfinished unit. Never redo a done unit, and never trust the conversation summary over
the artifacts. If the in-progress task looks dead — stale for a long time, overtaken
by other shipped work — ask the human whether to resume or mark it `abandoned` rather
than reviving it on momentum.

Work without a task folder resumes from the files it leaves. A release resumes from
its release record (`workflow/releases/<version>/release-record.md` whose Status is
not yet shipped): continue at its "Next action" line, and re-present any human gate
the record doesn't show as passed — an approval given in a lost conversation does not
carry over. Setup resumes from the placeholders still left in `workflow/PROJECT.md`.
The other playbooks restart from their first step; their results already live in the
files they edit.

**Between tasks.** Because all state lives on disk, a fresh session is the cheapest
context there is. When a non-trivial task closes and the user hasn't queued more
work, suggest starting a new session (`/clear`) rather than carrying this
conversation into the next task. Mid-task, when context runs low, flush per Pausing
first, then suggest the same.

## Capturing lessons

Sessions don't share memory; the project does. A lesson captured only in conversation
is relearned from scratch next session, so capture on **first** occurrence, at the end
of the task where it surfaced — hygiene prunes what never recurs. The test for "is
this a lesson": did it cost real time, and would it cost that time again for someone
without this conversation?

Encode each lesson at the strongest rung it fits, preferring higher rungs:

1. **Automated check** — a test, lint rule, or hook. Self-enforcing; nobody has to
   remember anything. Always first choice when mechanically checkable.
2. **Project skill** — a recurring multi-step technique (how to run the flaky suite,
   the deploy tool's quirks, a debugging recipe for this system) becomes a small
   skill under `.claude/skills/`, so it's loaded on demand instead of bloating the
   always-loaded project file.
3. **PROJECT.md line** — a one-sentence gotcha for `workflow/PROJECT.md`'s Known
   pitfalls list. That file loads every session, so it stays short; if a lesson
   doesn't fit in a sentence, it's rung 1 or 2 material.
4. **ADR** — "we tried X and it failed for reason Y" decisions, so the failed path
   isn't re-explored.

**The workflow improves too.** The playbooks, agents, and templates are evolving state
like everything else. When one repeatedly fights reality — a step that's always
skipped with the same reason, a verifier that keeps missing the same class of issue,
a template section nobody fills usefully — propose the concrete edit and its reason.
Project-specific deviations land in PROJECT.md's Workflow amendments; improvements
that would help every project are proposed upstream to the template. **Human
approves** changes to the workflow definition, in every autonomy mode; it's the shared contract, not any one
task's scratch space.

## Decision records

When a choice shapes the system's structure — a dependency, a data model, a boundary,
a technology — write an ADR in `workflow/decisions/` (template: [templates/adr.md](templates/adr.md)).
The test: would a future maintainer ask "why is it like this?" If yes, record it.

## Definition of done

Work is done when all of these hold; report each plainly, including failures:

- The work's acceptance criteria — the spec's, or the playbook's own definition of
  proven — are demonstrably met on the real artifact.
- Tests exist for the new behavior and the full suite passes.
- Lint/typecheck pass.
- The diff contains only what the task needed — no drive-by changes, no dead code,
  no narrating comments.
- Documentation users rely on is updated where the change affects it.
- The artifacts the playbook called for match what was actually built; update them
  if the build diverged.
- Anything learned the hard way is encoded per the Capturing lessons ladder, not left
  as tribal knowledge.
- The code has reached `main` via the profile's merge path and the task is closed:
  roadmap row shipped, branch gone, notes distilled. A pull request awaiting a human
  is "waiting", not done.
