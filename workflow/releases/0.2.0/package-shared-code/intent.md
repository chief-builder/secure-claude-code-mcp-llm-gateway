# Intent: package-shared-code

Release: 0.2.0 · Roadmap line: package-shared-code ·
Capability: Gateway and inference

**Problem.** Components reach each other's code by editing the import path at run
time. Four files carry a `sys.path.insert` line, and two test files and one script
import fixtures from other test modules. The costs today:

- The dependency between components is written in four places in code instead of
  one place in configuration, and each place computes a relative directory.
- Deploying the gateway to another host means copying two directories and keeping
  their relative layout, because `gateway.py` looks for `../oauth-as`.
- The linter added in this release needs four whole-file exceptions to tolerate the
  pattern, which also hides any new unused import in those files.
- A runnable script, `manual_claude_check.py`, depends on test internals.

**Why now.** The two design tasks in this release, MCP and AWS-hosted identity, both
add code that will want the shared DPoP verifier and token checks. The linter
exceptions were accepted on the condition that this task removes them.

**Success looks like.** No `sys.path` manipulation anywhere in `components/`, no
lint exceptions, one place that says which directories are importable, and every
documented command still works exactly as written.

**Constraints.** Behavior does not change. This touches the import lines of the
accepted security modules, so the plan needs the owner's approval. No file moves and
no renamed modules unless the owner chooses the larger option.
