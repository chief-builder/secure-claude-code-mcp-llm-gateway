# Notes: <task name>

Working state that must survive a session boundary. Append-only during the task,
except the Next action line, which is kept current; deleted or distilled into the
spec/ADRs when the task ships. Not a diary — record only
what a fresh session (or another person) would need to continue correctly.

## Decisions made in flight

<Choices resolved during build that the spec/plan didn't settle, each with its reason
and whether the human was asked or it was decided on their behalf. If one changes the
spec's meaning, update the spec too and note it here. Everything decided on the
human's behalf is repeated in the task's final report.>

## Discoveries

<Things the code taught us mid-task: wrong assumptions in the plan, surprising
behavior, verifier findings not yet addressed.>

## Next action

<One line, kept current when pausing: exactly where work stops and what happens next.>
