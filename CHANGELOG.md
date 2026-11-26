# Changelog

What changed in each release, for someone using the lab. Newest first.

## 0.2.0 — guardrails, and the next two steps thought through

No change to how the lab behaves. This release adds checks that keep the project
honest, removes a structural shortcut, and records the designs for what comes next.

### For someone running the lab

- **After updating, run `uv sync` again.** Components now find each other through
  the project's installed environment instead of changing the import path at run
  time. Every documented command is unchanged.
- **If you copied only the `gateway` and `oauth-as` folders to another machine**, as
  the original live Bedrock run did, that no longer works on its own. Clone the
  repository there and run `uv sync --locked --no-dev`, or start the gateway with
  `PYTHONPATH=../oauth-as`.
- **The cost of the live Bedrock run is now on record:** about $0.04, with nothing
  left billing.

### For someone reading or changing the code

- **Continuous integration checks the documentation.** A broken link, a link to a
  missing heading, a comment line in a shell block (which the default macOS shell
  rejects when pasted) or a link to a source line number fails the build.
- **Continuous integration lints the Python code** with a small rule set: syntax
  errors, undefined names and unused imports.
- **Tests guard the import path.** They fail if an installed package would shadow
  one of the lab's own modules.
- **The build tool is pinned**, like every other dependency.

### Designs recorded, not yet built

- **Identity services on AWS.** Keycloak, the authorization server and the gateway
  on one AWS host reached by tunnels first, then split onto separate hosts. The
  token-signing key stays a file.
- **An MCP gateway.** Claude Code will reach MCP tool servers through the local
  broker, with its own DPoP-bound tokens and rules per tool, targeting revision
  2026-07-28 of the MCP specification.

The reasoning for each is in `workflow/decisions/`.

### Still open

Three checks planned for this release moved to the next one: reachability from a
second device, a gateway call with a debugger-recovered token, and signing during
screen lock.

## 0.1.0 — first public release

The complete synthetic lab, published as a reference implementation.

### For someone running the lab

- **The whole path works end to end.** Claude Code talks to a local credential
  broker, which signs the user in through Keycloak, exchanges the ID token at a
  separate authorization server for a DPoP-bound gateway token, and calls the LLM
  gateway with a fresh proof per request. The gateway forwards to a mock model or to
  Amazon Bedrock.
- **The DPoP key can live in Apple's Secure Enclave**, where it cannot be copied.
- **One quickstart page** takes a fresh clone to a working lab in about ten minutes.
- **One environment.** `uv sync` at the repository root installs everything.
- **Lab keys live outside the repository**, under `~/secure-claude-lab`.

### Behavior worth knowing about

- The gateway sends an `error` event when a streaming response fails part-way,
  instead of ending the stream as if it had completed.
- The authorization server accepts only its own issuer identifier as the audience of
  a client assertion, following the update to RFC 7523 now in draft.
- The mock model refuses to start without `MOCK_LLM_TOKEN`.
- The Bedrock adapter returns the matched stop sequence. This is covered by offline
  tests only.

### For someone reading the code

- Offline test suites for all five components run in continuous integration on
  Python 3.12 and 3.14, with a secret scan.
- Design specs and verification records for all eight components are under `docs/`,
  indexed in `docs/README.md`.
- A glossary, a request walkthrough and two code walkthroughs explain how the parts
  fit together.

### Known limits

This is a lab, not a product. The root README lists the limits and the checks that
were planned but not completed.
