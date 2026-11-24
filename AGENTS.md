# Agent instructions

This project's rules, commands and conventions live in
[`workflow/PROJECT.md`](workflow/PROJECT.md). Read it before doing anything.

How work is done here is defined by the workflow in
[`.claude/skills/swe-workflow/SKILL.md`](.claude/skills/swe-workflow/SKILL.md):
intent → spec → plan → build → verify → ship, with a human approving the spec, any
risky plan, and anything irreversible. What to work on comes from
[`workflow/ROADMAP.md`](workflow/ROADMAP.md).

The rules that hold whichever tool you are:

1. Do not implement before the spec is approved.
2. Never use real patient data, production tokens or enterprise secrets.
3. Never read, copy or create key material inside the repository.
4. Never claim something is tested unless the tests were actually run.
5. Do not force-push, publish or delete without explicit human approval.
