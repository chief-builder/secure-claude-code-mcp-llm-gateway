# Plan: rfc-10070-assertion-type

Consumes: [spec.md](spec.md)
Status: **approved** (2026-11-26)

**Design summary.** One constant for the type and one tuple of accepted values in
`exchange.py`. The check sits in `Exchange.authenticate`, after the signature is
verified and with the other claim checks, so it applies only to client assertions.
It cannot go in the shared `token_parts` helper, which also parses Keycloak ID
tokens and gateway access tokens. A rejected type raises the same `invalid_client`
rejection as any other bad assertion, before the assertion's identifier is recorded
as used.

**Units.**

| # | Unit | Check | Status |
|---|------|-------|--------|
| 1 | Server: accept `client-authentication+jwt`, `JWT` and no type; reject other types. Cite the RFC in the comment | New tests for each case pass; the existing 55 pass | **done** |
| 2 | Clients: `lab_exchange.py` and `lab_invoke.py` set the type; the tests' default assertion uses it | All suites pass | **done** |
| 3 | Documents: glossary, the authorization server README, the Component 3 design note, the roadmap | Documentation check passes; no stale citation | **done** |
| 4 | Live lab run from a fresh clone | Broker exits 0 with `MOCK_OK`; DPoP probe succeeds | **done** |
| 5 | Verifier agent, then land | Acceptance criteria met | **done** |

**Risks.** A client somewhere that sends an unusual type would start being
rejected; in this lab the only clients are the two being changed. The signing
library adds `typ: JWT` unless told otherwise, so the "no type" case needs a test
that really omits the header.
