# Secure Claude Code – MCP & LLM Gateway

A reference implementation that connects Claude Code on macOS to AWS Bedrock through
an LLM gateway, using OAuth 2.0 token exchange and DPoP sender-constrained tokens.
Its readers are engineers and security architects who want a worked example. It is a
synthetic lab, not a product: "working" means the offline test suites pass and the
documented lab flow runs end to end on one Mac with disposable keys.

## Process profile

How much process this project runs. Options, typical combinations per phase, and
when to change a value: the swe-workflow skill's "The process profile" section. Changing a value is a workflow change: one
line of reason, and the human says yes.

- Team: solo
- Phase: stabilizing — since 2026-11, the repository is public and others may rely on it
- Merge path: pull request, self-reviewed
- CI: required to merge — enforced since 2026-11-25 by branch protection on `main`
- Deploy target: none
- Released versions maintained: no
- Autonomy: stop at gates
- Unused playbooks: none

## Commands

- Build: none (the components run from source)
- Test: `uv sync`, then `for c in mock-llm mock-mcp oauth-lab oauth-as gateway broker; do (cd components/$c && uv run python -m pytest -q); done` and `(cd tools && uv run python -m pytest -q)`
- Lint: `uv run ruff check` (a small rule set; no formatter, no type checker)
- Docs check: `uv run python tools/check_docs.py` (links, heading anchors, shell blocks)
- Run locally: follow the component READMEs in the order the root `README.md` lists
- Version lives in: `pyproject.toml`, field `version`

All components share one environment defined by the root `pyproject.toml` and
`uv.lock`. Change dependencies there and run `uv lock`. The same file lists the
component directories that are importable.

## Architecture in brief

- `components/mock-llm` — Component 1, an Anthropic Messages-compatible mock.
- `components/mock-mcp` — a mock MCP tool server built with the official MCP SDK,
  for the MCP gateway to sit in front of.
- `components/oauth-lab` — Component 2A, Keycloak browser sign-in with PKCE.
- `components/oauth-as` — Components 2B and 3, the authorization server and RFC 8693
  token exchange, plus the DPoP verifier (`dpop.py`) shared with the gateway.
- `components/gateway` — Components 4, 5 and 8: token validation, DPoP proofs, nonces
  and replay, and the Bedrock Converse adapter (`bedrock.py`). Also the MCP gateway
  (`mcp_gateway.py`), a separate process that imports the same token and proof
  checks and applies per-tool rules in front of the mock MCP server.
- `components/broker` — Components 6 and 7: the local broker that launches Claude
  Code, and the Swift Secure Enclave signer under `native/`.
- Boundaries that must hold: Claude Code never receives the gateway token or any AWS
  credential; only the gateway host holds AWS credentials; every listener binds to
  IPv4 loopback.
- The API is Anthropic Messages-compatible, not the Bedrock wire protocol, and
  text-only. Claude Code is pointed at it with `ANTHROPIC_BASE_URL` and a disposable
  `ANTHROPIC_AUTH_TOKEN`; global Claude Code settings are never modified.

## Design

- UI: none
- Design system: none

## Conventions

- Never use real patient data, production tokens or enterprise secrets. Synthetic
  identities and disposable keys only.
- Keys, certificates, tokens and replay databases live under `~/secure-claude-lab`,
  never inside the repository. Do not read, copy or create key material in the
  repository.
- Logs and audit events carry event names and request IDs only, never credentials,
  tokens or prompt content. One exception, agreed on 2026-11-27: the MCP gateway's
  audit lines also carry the user's mapped identity and the name of a tool the
  policy allowed, because no other record says who called which tool. Never
  arguments, results, or a tool name supplied by the caller.
- Prefer open-source and free components for local development.
- Document security limitations where they are introduced, and list them in the root
  `README.md` under Known limitations.
- Commit messages follow Conventional Commits (`feat:`, `fix:`, `docs:` and so on).
- Design specs and verification records written before this workflow was adopted
  live in `docs/component-NN/`. They are frozen history. New work goes under
  `workflow/`.

Workflow naming, same in every project: task folders and branches are lowercase words
joined by dashes and share one name; decision records are
`workflow/decisions/<number>-<short-title>.md` with a zero-padded number.

## Branching

- `main` is always releasable. Whether it is protected and whether changes arrive by
  pull request is the profile's merge path.
- On a branching merge path: one short-lived branch per task, cut from `main`, named
  after the task dir. It lives as long as the task, then merges and is deleted. Never
  let a task branch live long enough to need repeated merges from it — that's the
  plan's units being too big.
- Releases are tags on `main`. A release branch exists only when an old version must
  be patched while newer work ships — a hotfix there follows the bug-fix playbook and
  the fix lands on `main` too.
- Force-pushes always stop for a human, on every merge path.

## Workflow amendments

- Plan approval is always required for a change to token validation, DPoP, replay
  protection, key handling or the broker's local boundary — a mistake there defeats
  the purpose of the project.
- Never claim something is tested unless the tests were actually run. Report skipped
  tests as skipped, and say which checks were offline and which were live.
- A change to an accepted protocol behavior is followed by a live lab run before the
  task closes, recorded in the task folder — offline tests alone do not re-prove it.
- A task that adds or changes a security check shows that the check is really
  tested: remove or weaken the check, confirm at least one test fails, restore the
  file, and list in the task's record which checks were tried. A passing test proves
  the code works, not that the test would notice if it did not.
- A task that adds or changes a concept adds or updates a diagram for it under
  `docs/concepts/`, written as Mermaid so it renders on GitHub — the owner wants the
  ideas explained visually as they are built.
- The `sketch` skill and the `swe-workflow-guide` mod are not installed — the project
  has no user interface. Ignore the references to them in `CLAUDE.md` and the skill.

## Known pitfalls

- `gateway` imports from `oauth-as` and `broker` imports from `gateway`, so a change
  to `oauth-as` requires rerunning all three suites. The MCP gateway's tests import
  `mock-mcp`, and both gateways share `gateway.py`'s checks, so a change to either
  reruns the `gateway` suite.
- Components import each other as plain modules. The directories are on the import
  path only because `uv sync` installs the project in editable mode (see
  `dev-mode-dirs` in `pyproject.toml`), so run everything with `uv run`. A module
  name must be unique across `mock-mcp`, `oauth-lab`, `oauth-as`, `gateway` and `broker`, and
  installed packages are found before these directories; `tools/tests` fails if a
  dependency ever shadows one. A host without the editable install needs
  `PYTHONPATH` set to the directories a component imports from.
- Without `LAB_TLS_DIR`, 11 live Keycloak tests skip; without
  `SECURE_SIGNER_TEST_BINARY`, 6 hardware signer tests skip. A green run does not
  cover them.
- The permission rules deny the Read tool on `~/secure-claude-lab` and on key and
  certificate files, so existing lab directories cannot be inspected; build a fresh
  lab instead.
- Every pull request gets two CI runs (push and pull request). Read every line of the
  check list before calling it green — a failing job has been missed this way once.
- `astral-sh/setup-uv` has no floating major tag; pin a full release tag.
- Docker can only mount files from folders it shares. A clone in a temporary or scratch
  folder makes Keycloak fail with the realm file "Is a directory"; test clones go
  under the home folder.
- Prove a documented command by pasting it into an interactive shell, not by running
  it as a script: the two behave differently. CI rejects `#` comment lines in shell
  blocks, the one difference found so far, but cannot find the next one.
- Do not link to source line numbers (`file.py#L12`); they go stale and CI rejects
  them. Link to the file and name the function.
- The secret scan flags a literal credential in an example `curl` authorization
  header, even a placeholder. Use a shell variable in examples. Known false positives
  go in `.gitleaksignore`.
- Lab certificates last 7 days. An expired certificate looks like a trust failure.
