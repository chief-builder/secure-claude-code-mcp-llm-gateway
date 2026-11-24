# Investigation

A read-only question: how does X work, why is Y like this, should we do A or B. Also
a review of someone else's change ("review this pull request"). The deliverable is a
cited answer, not a code change.

1. **Sharpen the question.** Restate what is being asked and what decision the answer
   feeds. If it decomposes into sub-questions, list them. For a review, the question
   is "does this change do what it claims, safely, and does it belong?"
2. **Gather evidence.** Read the code, the git history, the ADRs and specs in
   `workflow/`. Delegate breadth to `explorer`; verify the load-bearing claims
   yourself. When the question is empirical (behavior, timing, output), run the code
   and observe rather than reasoning from source alone — a quick throwaway probe beats
   speculation.
3. **Answer from evidence.** Every claim cites its source (`file:line`, commit,
   observed output). Distinguish clearly between what you verified, what you infer,
   and what remains unknown. A review's answer is its findings, ranked by how much
   they matter, each with a concrete failure scenario — no style nitpicks.
4. **Recommend if asked.** For "should we" questions, give a real recommendation with
   trade-offs — not a survey of options. "No" and "this doesn't earn its place" are
   acceptable answers.
5. **Stop.** Do not fix what you find along the way. Surface findings worth acting on
   as proposed follow-ups and let the human choose.

An answer worth keeping beyond the conversation gets written down: a "we looked into
this" ADR if it settles a decision, or a backlog line if it points at future work.

**Report:** the answer first, then the evidence, then unknowns and suggested follow-ups.
