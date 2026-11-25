# Changelog

What changed in each release, for someone using the lab. Newest first.

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
