# Component 02A — Verification report

**Status:** Gate 2A accepted for the synthetic lab  
**Environment:** macOS, Python 3.14.7, Keycloak 26.7.5, isolated Chrome session

| Gate case | Observed evidence |
|---|---|
| 2A-01 — Discovery | Live HTTPS metadata and JWKS accepted with the lab CA. Untrusted TLS failed. Fixture tests rejected wrong issuer, off-boundary endpoints, and missing required metadata. |
| 2A-02 — Browser sign-in | Chrome rejected an incorrect synthetic password, completed the native callback flow and reused the browser SSO session on a second attempt with fresh state, nonce and PKCE. A correlated cancellation error was exercised with a loopback test. The browser was automated through an isolated launcher using the disposable server certificate's public key pin. The ordinary desktop launcher and manual Ctrl-C flow were not separately exercised. |
| 2A-03 — PKCE and codes | The live realm rejected plain and missing PKCE challenges, missing and wrong verifiers, changed client and redirect URI, and reused and expired codes. The expiration probe redeemed after 62 seconds and failed as expected. |
| 2A-04 — Redirect registration | The live realm rejected alternate host, port and path without redirecting to them. The native listener refused to launch a browser when its fixed port was occupied. |
| 2A-05 — Callback | Fixtures rejected uncorrelated, expired, malformed and duplicated fields and wrong Host and path. Loopback tests verified that concurrent duplicate callbacks cause one redemption and an OAuth error causes none. |
| 2A-06 — ID Token | The live client validated a Keycloak-issued ID Token. Signed fixtures rejected issuer, audience, authorized party, nonce, time, signature, key, algorithm and access-token hash failures, including duplicate claims. A live Keycloak access token was not separately injected into the ID-token slot. |
| 2A-07 — Hygiene and regression | Confirmed Docker published HTTPS at `127.0.0.1:8080`. The callback binds to IPv4 loopback and closes after success or a correlated error. Automated assertions checked generic callback responses and absence of callback test data from client output. Sampled Keycloak logs had no tested secret patterns. Component 1 passed its eight regression tests with the existing Starlette warning and returned `MOCK_OK` over loopback. The Claude Code CLI and off-host reachability were not separately retested. |

The repository test suite passed **45 cases**, including **11 live Keycloak protocol cases**. The browser and code-expiration checks ran separately. Results use synthetic credentials and cover the specified cases sampled above. Browser history and cookies remain browser-managed. Local denial of service against the fixed callback port remains possible.

## Reviewer verification and acceptance

The reviewer reran all 45 automated tests and confirmed HTTPS discovery, the Keycloak loopback binding, default browser sign-in and session reuse, wrong-password rejection, forged callback rejection with the real login still succeeding, and Ctrl-C cancellation with the callback listener released. A live token substitution probe accepted the genuine ID token and rejected the access token from the same Keycloak response. The Claude Code CLI returned `MOCK_OK` and the local mock logged a successful messages request after an earlier HTTP 422.

The reviewer explicitly accepted Gate 2A for the synthetic lab and approved implementing Component 2B. Off-device reachability remains pending because a second device was unavailable. RFC 8693 exchange remains deferred to Component 3.
