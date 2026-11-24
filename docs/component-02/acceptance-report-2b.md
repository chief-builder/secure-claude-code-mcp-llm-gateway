# Component 02B — Verification report

**Status:** Gate 2B accepted for the synthetic lab  
**Environment:** macOS, Python 3.14.7, FastAPI 0.162.0, Uvicorn 0.54.0, Keycloak 26.7.5

| Gate case | Observed evidence |
|---|---|
| 2B-01 — Independent metadata | The live HTTPS service returned issuer `https://127.0.0.1:8081`, its own JWKS URI, and empty grant and response type arrays. The metadata advertised no grant endpoints. |
| 2B-02 — Signing keys | The published JWK contained only public RSA fields. The same key and ID appeared after process restart. The AS public key verified a non-token challenge signed in isolation, and the live Keycloak RS256 signing key rejected the signature. Missing, invalid, symlinked or overly permissive signing material failed startup in automated checks. |
| 2B-03 — Pinned upstream trust | Startup succeeded against the live Keycloak realm with its CA and failed when given the unrelated AS CA. Controlled cases rejected issuer and JWKS mismatches, redirects, malformed or ambiguous JWKS, overlapping key material, oversized data and unavailability. Requests stayed within the pinned URLs. An expired trust check returned HTTP 503 when upstream was unavailable and recovered when upstream returned. |
| 2B-04 — Disabled policy | Validated the exact confidential-client candidate, source issuer and audience, requested token type, target and scope. Automated checks rejected public-client substitution, unknown or wildcard policy values, and attempts to enable exchange or issuance. The provisioned client JWK is a public placeholder. Setup discards its private counterpart. |
| 2B-05 — Missing grant and issuance routes | Live requests for token exchange, client credentials, authorization code and refresh returned generic HTTP 404 responses. Login, registration and signing routes returned 404. Sampled process logs did not contain the synthetic submitted token. |
| 2B-06 — Exposure and key hygiene | The live process had exactly one listening TCP socket on `127.0.0.1:8081`. A connection to the Mac's LAN address from that Mac failed. Sampled responses and logs contained no AS private key. No route signs or issues tokens. An off-device network probe was not performed. |

**Results:** 31 Component 2B automated cases passed. All 45 Component 2A regression cases also passed, including its live Keycloak cases. The live 2B smoke checks ran separately with disposable AS TLS and signing material. The temporary AS process was stopped after verification.

The upstream check is cached for up to 60 seconds and retried on a read after expiration. The five-second failure backoff limits repeat attempts. Signing-key file checks use Unix ownership and permission bits. Keep the keys in an owner-controlled lab directory without additional sharing permissions. The lab is restricted to synthetic identities and credentials.

## Reviewer verification and acceptance

The reviewer reran all 31 automated tests and verified the HTTPS metadata, public-only JWKS, key ID stability across restart and signing-key isolation from Keycloak. All four grant requests returned HTTP 404. The service failed startup with the wrong upstream CA, returned HTTP 503 after a live Keycloak outage and trust-cache expiry, and recovered to HTTP 200 without restarting 2B. The reviewer also confirmed that the only listener on port 8081 was bound to `127.0.0.1`.

The reviewer explicitly accepted Gate 2B for the synthetic lab with off-device reachability pending. Confidential client authentication, external assertion validation, RFC 8693 exchange and gateway token issuance remain Component 3 work.
