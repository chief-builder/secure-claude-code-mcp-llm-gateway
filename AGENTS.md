# Project: Secure Claude Code – MCP & LLM Gateway

## Objective

Build a secure, enterprise-grade LLM inference architecture connecting Claude Code on macOS to AWS Bedrock through an enterprise LLM Gateway.

The architecture will use OAuth 2.0, RFC 8693 Token Exchange, DPoP (RFC 9449), and a macOS Credential Broker.

The long-term objective is to prevent stolen access tokens from being replayed and keep AWS credentials off developer laptops.

## Development Rules

1. Design one component at a time.
2. Do not implement code until the component design has been explicitly approved.
3. Implement only the approved component.
4. Write functional and security tests for every component.
5. Review test results before proceeding.
6. Prefer open-source and free components for local development.
7. Never use real patient data (PHI), production tokens, or enterprise secrets.
8. Document architectural decisions and security limitations.
9. Never claim a component is tested unless tests were actually executed.

## Approved Component 1 Decisions

- **A:** Start with text-only responses. Add tool-use simulation only if Claude Code compatibility testing requires it.
- **B:** Use `ANTHROPIC_BASE_URL` and a disposable `ANTHROPIC_AUTH_TOKEN`. Do not modify global Claude Code settings.
- **C:** Implement an Anthropic Messages-compatible API, not the AWS Bedrock wire protocol.

## Component Roadmap

1. Claude Code → Local Mock LLM
2. Keycloak SSO + OAuth Authorization Server
3. RFC 8693 Token Exchange
4. LLM Gateway OAuth Authentication and Authorization
5. DPoP Sender-Constrained Token Security
6. macOS Credential Broker
7. Secure Enclave Integration
8. AWS Bedrock Integration

## Current Status

All eight components are implemented and accepted for the synthetic lab only.
This is lab acceptance, not production readiness. MCP support is planned and
not yet designed.

Checks that remain pending:

- Second-device reachability (all components).
- Gateway invocation with debugger-recovered credentials (Component 6).
- OS signing behavior during screen lock, independent of the helper's own
  lock check (Component 7).
- Final billed-cost reconciliation and budget-alert email delivery
  (Component 8).

Current work: preparing the repository for open-source publication on the
`publish-prep` branch.

## Repository Layout

| Path | Components |
|---|---|
| `components/mock-llm` | 1 |
| `components/oauth-lab` | 2A (Keycloak sign-in) |
| `components/oauth-as` | 2B, 3, and the shared DPoP verifier for 5 |
| `components/gateway` | 4, 5, 8 |
| `components/broker` | 6, 7 (`native/` holds the Swift signer) |
| `docs/component-NN` | Design specs and verification records |

`gateway` imports from `oauth-as`, and `broker` imports from `gateway`, so a
change to `oauth-as` requires rerunning all three suites.

## Commands

Run tests from each component directory:

```sh
cd components/oauth-lab && .venv/bin/python -m pytest -q
cd components/oauth-as  && .venv/bin/python -m pytest -q
cd components/gateway   && .venv/bin/python -m pytest -q
cd components/broker    && .venv/bin/python -m pytest -q
cd components/mock-llm  && ../../.venv/bin/python -m pytest -q
```

`mock-llm` uses the virtual environment at the repository root. Without
`LAB_TLS_DIR`, 11 live Keycloak tests skip. Without
`SECURE_SIGNER_TEST_BINARY`, 6 hardware signer tests skip. Report skipped
tests as skipped, not passed.

Lab keys, certificates and replay databases live under `~/secure-claude-lab`,
outside the repository. Do not read, copy or create key material inside the
repository.

## Security Requirements

- No production credentials or PHI.
- No AWS credentials in Claude Code.
- Prevent accidental credential exposure in logs or configuration.
- Use sender-constrained tokens for the final architecture.
- Restrict local network exposure.
- Maintain auditable authentication and authorization flows.

## Working Agreement

For every component:

Design → Review → Approve → Implement → Test → Accept

Do not advance to the next stage without explicit approval.
