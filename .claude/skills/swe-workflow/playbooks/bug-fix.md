# Bug fix

A reported defect. The deliverable is a proven fix of the root cause, not a patch that
hides the symptom.

0. **Open the task** per [_open-close.md](_open-close.md).
1. **Reproduce.** Make the bug happen yourself, on the surface it was reported on.
   No reproduction, no fix — if you truly cannot reproduce, report what you tried and
   what evidence would unblock you.
2. **Root-cause.** Trace the symptom to its cause; keep asking why until the answer is
   a decision or assumption in the code, not another symptom. State the root cause in
   one sentence before writing the fix.
3. **Pin it with a test.** Write a failing test that captures the bug. This is the
   artifact that keeps it fixed.
4. **Fix.** The smallest change that corrects the root cause. If the real fix is a
   redesign, say so and let the human choose between the tactical patch and the
   redesign — don't silently pick either.
5. **Prove.** Failing test now passes, the original reproduction no longer occurs on
   the same surface, and the full suite still passes.
6. **Widen once.** Ask where else this same mistake lives (the sibling call sites, the
   copy-pasted variant). Fix what's in scope; file the rest as backlog lines in
   `workflow/ROADMAP.md`.
7. **Encode the lesson.** Capture what this bug taught per the skill's Capturing
   lessons ladder — a type, lint, or guard where mechanically preventable; a skill or
   pitfall line where not — or record the structural gap in the debt register. If
   the existing tests would have caught this bug had they run before it reached
   `main`, that is a process-profile signal (CI): propose it in the report.
8. **Ship.** Land the fix per [_open-close.md](_open-close.md): the failing-then-passing
   test, the fix, and the root cause in the description. If a released version that
   users still run needs this fix too (a hotfix), land it there as well — the
   profile says whether released versions are maintained.
9. **Close the task** per [_open-close.md](_open-close.md).

A bug hunt that spans sessions gets a task dir with `notes.md`, same as a feature.

**Report:** root cause in plain language, the fix, how it was proven, anything
decided on the human's behalf, and any sibling risks found.
