# Intent: close-pending-checks

Release: 0.2.0 · Roadmap line: close-pending-checks ·
Capability: Sender-constrained access

**Problem.** Four checks were left open when the original gates were accepted, and
the README lists them as planned but not completed. Each needs the owner's hardware
or accounts:

1. Reconciling the billed cost of the live Bedrock run of 2026-11-22/23 (UTC) and
   confirming that the budget alert can deliver an email.
2. Reachability of the lab listeners from a second device.
3. Calling the gateway with a debugger-recovered token and software key.
4. Observing the operating system refuse to sign during screen lock, independently
   of the helper's own lock check.

**Why now.** They are the last open task in 0.2.0, and the first one gets harder to
do the longer it waits: cost data is clearest while the run is recent.

**Success looks like.** Each check has a dated record of what was run, by whom, and
what it showed, or a stated reason it was dropped. The README's list of unfinished
checks shrinks to match.

**Constraints.** The assistant does not hold or use AWS credentials: the project
keeps them off the developer's Claude Code session. The owner runs every AWS command
and reports the output. Account numbers and email addresses are not recorded in the
repository.
