# Opening, landing, and closing a task

Shared by the feature, bug-fix, and refactor playbooks. All three parts read the
process profile in `workflow/PROJECT.md`.

**Open the task.**
- Make sure the roadmap has a line for this work, naming the capability it serves.
  Add one if not.
- Create the task folder `workflow/releases/<version>/<task>/`, where `<version>` is
  whatever the roadmap calls the current release (in exploration that may just be
  `next`). Task folder and branch share one name: lowercase words joined by dashes.
- If the merge path uses branches, cut the task branch from `main`. On direct push,
  work on `main`.

**Land the code.** How the finished work reaches `main`, per the merge path:
- Direct push: push.
- Pull request, self-reviewed: open it, review it as if someone else wrote it, merge.
- Pull request, human-reviewed: open it and stop. Mark the roadmap row *waiting*.
  The task closes when the human says merged, or when a later session finds it merged.

Honor the profile's CI line: "required to merge" means the checks pass before the
merge; "runs on push" means report the outcome, or say it is still pending; "none"
means nothing. If the profile's deploy target means this push or merge deploys, it is
a deploy — the human approves it first, in every autonomy mode.

**Close the task.** Once the code is on `main`: roadmap row marked shipped, task
branch deleted if one existed, anything durable in `notes.md` distilled into the spec
or an ADR and the notes file deleted. Those workflow-state edits land through the
same merge path; the task is closed when they are on `main` too.
