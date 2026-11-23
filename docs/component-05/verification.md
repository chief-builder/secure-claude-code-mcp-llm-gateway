# Component 5 verification

**Status** Gate 5 accepted for the synthetic lab. Second-device reachability remains pending.

| Case | Executed evidence |
|---|---|
| 5-01 — Bound invocation | An automated integration test used the actual AS and gateway applications with synthetic Keycloak and mock fixtures. It completed both nonce challenges and invoked the gateway with the AS-issued, key-bound token. Separate tests verified the signed `cnf.jkt` claim and an SSE response with a fresh proof. The reviewer completed the live browser-to-mock run over verified HTTPS. The test client verified the issued token's key binding, received `MOCK_OK` in JSON and SSE, and checked the SSE completion event. |
| 5-02 — Substitution and downgrade | The gateway rejected a token without a proof, a bearer request, an unbound token, a different signing key, an incorrect access-token hash, and a proof for a different endpoint. These cases caused zero mock calls. DPoP-required mode also rejected inconsistent AS metadata. |
| 5-03 — Proof validation | Tests rejected invalid signatures, private JWK material, wrong method or URI, stale and future proofs, duplicate headers, oversized proofs and an unexpected token hash at exchange. Tests exercised missing, invalid and expired nonce challenges. The AS required a fresh client assertion and accepted the original, unspent subject token after challenge. |
| 5-04 — Replay and failure | Separate AS processes using the same proof and distinct synthetic subjects issued exactly one token. Separate gateway processes using the same proof dispatched exactly one mock call. Tests covered replay after restart, proof and subject rollback on signing failure, gateway replay store outage, clock rollback, and a proof remaining spent after a mock timeout. The real loopback TCP lost-response test passed in both exchange profiles. The reviewer reran the DPoP case and confirmed that a lost response leaves both the subject assertion and proof spent. The test models HTTPS at the application boundary. |
| 5-05 — Regression and diagnostics | Bearer tests ran alongside DPoP tests. Captured gateway diagnostics excluded token, proof, nonce, thumbprint and prompt canaries. Tests confirmed the mock received its separate lab credential without the DPoP header. The reviewer verified the live nonce challenges and successful exchange and invocations. The sampled audit lines used distinct IDs within each service and contained no credentials or proofs. All four lab services listened on IPv4 loopback. Second-device reachability remains pending. |

Executed suites

- Authorization server — **56 passed** on the full suite before adding the DPoP lost-response case. Both lost-response variants then passed in a targeted run, and the reviewer independently reran the DPoP variant.
- Gateway — **26 passed**, also rerun by the reviewer
- Component 1 mock — **8 passed**, with the existing Starlette TestClient deprecation warning

The reviewer refreshed the AS lab TLS certificate before the live run.
The [lab walkthrough](../../components/gateway/README.md#enable-component-5-dpop)
describes switching both services to the DPoP profile and running the browser
check. Each service has an independent nonce key. Preserve it alongside the
replay database during ordinary restarts. Rotate it before serving with newly
initialized replay state.
