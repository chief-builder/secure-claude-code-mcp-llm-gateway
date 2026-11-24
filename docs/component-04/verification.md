# Component 4 verification

**Status** Gate 4 accepted for the synthetic lab. Second-device reachability remains pending.

## End-to-end verification

Green marks successful behavior. Red marks an expected rejection that passed
its check. Gray marks pending or out-of-scope checks. Each marker identifies
whether the evidence came from the live lab or the automated suite.

```mermaid
flowchart TD
    C["Lab browser and invocation probe"]
    K["Keycloak<br/>PASS · Live browser sign-in over verified HTTPS"]
    A["Component 3 authorization server<br/>PASS · Live exchange issued a gateway token"]
    T["Gateway signing trust<br/>PASS · Live AS keys loaded with correct CA<br/>PASS · Automated key rotation and refresh throttling"]
    G["Component 4 gateway<br/>PASS · Live exchanged token accepted<br/>PASS · Automated client, scope and body checks"]
    M["Component 1 mock<br/>PASS · Live JSON and SSE returned MOCK_OK<br/>PASS · Automated header allowlist and separate credential"]
    R["Probe received the response<br/>PASS · Live JSON and SSE message_stop<br/>PASS · Automated backpressure and cancellation"]
    Audit["Gateway audit<br/>PASS · Two live success events with distinct request IDs<br/>PASS · Automated credential and prompt canary checks"]
    Bind["Network bindings<br/>PASS · Live AS, gateway and mock on IPv4 loopback"]
    WrongCA["EXPECTED REJECTION · Wrong CA<br/>Live AS trust loader reported 503"]
    Direct["EXPECTED REJECTION · Direct Keycloak tokens<br/>Live ID and access tokens received 401 invalid_token"]
    Deny["EXPECTED REJECTION · Invalid requests<br/>Automated invalid tokens, denied policy and malformed inputs<br/>Zero mock calls"]
    Pending["PENDING · Second-device reachability<br/>OUT OF SCOPE · Claude Code compatibility"]

    C -->|"Sign in"| K
    K -->|"Keycloak ID token via probe"| A
    A -->|"Exchanged token via probe"| G
    A -->|"Publish metadata and JWKS"| T
    T -->|"Trusted signing keys"| G
    G -->|"Forward authorized request"| M
    M -->|"JSON or SSE through gateway"| R
    G -.-> Audit
    G -.-> Bind
    T -.-> WrongCA
    K -.->|"Direct submission to gateway"| Direct
    G -.-> Deny
    Bind -.-> Pending

    classDef passed fill:#dcfce7,stroke:#15803d,color:#14532d
    classDef rejected fill:#fee2e2,stroke:#b91c1c,color:#7f1d1d
    classDef pending fill:#f3f4f6,stroke:#6b7280,color:#374151
    class K,A,T,G,M,R,Audit,Bind passed
    class WrongCA,Direct,Deny rejected
    class Pending pending
```

| Check | Executed evidence |
|---|---|
| 4-01 | A loopback HTTPS smoke check loaded signing metadata and keys from a temporary signing fixture, authenticated to the gateway, and received `MOCK_OK` in JSON and SSE from the real Component 1 mock. SSE included `message_stop`. The fixture used temporary loopback ports. After refreshing Keycloak TLS, the reviewer completed the live browser sign-in and Component 3 exchange. The gateway returned `MOCK_OK` in JSON and SSE, and the probe verified the `message_stop` event. |
| 4-02 and 4-03 | Automated tests rejected missing, malformed and duplicate credentials, incorrect claims or protected headers, and a signature from a different key using the expected key ID. Wrong client and scope were denied. Rejections caused zero mock calls. JSON and SSE succeeded with the same valid token. The reviewer submitted live Keycloak ID and access tokens directly to the gateway. Both were rejected with HTTP 401 and the Bearer `invalid_token` challenge. |
| 4-04 | Tests verified signing-key rotation, unknown-key refresh throttling, failure with expired trust or changed metadata pins, rejection of redirects, and mock connection and read failures. The reviewer verified the gateway's trust loader against the live AS. The correct CA loaded public signing keys. The unrelated gateway CA caused the trust loader to return a 503 failure. |
| 4-05 | Tests checked actual body bytes, incremental streaming, slow downstream backpressure, cancellation and upstream closure, and deadline behavior before and after response headers. Unknown query parameters did not reach the mock. |
| 4-06 | Tests inspected allowlisted mock-bound headers and independently generated request IDs. Synthetic token, mock credential, prompt, and caller-supplied header canaries were absent from captured diagnostics. The reviewer observed two live invocation success events with distinct request IDs and no tokens, credentials or prompt content in those entries. The AS, gateway and mock listeners were confirmed on IPv4 loopback. Second-device reachability remains pending. |

Executed suites

- Gateway tests — **21 passed**, also rerun by the reviewer
- Component 1 mock tests — **8 passed**, with the existing Starlette TestClient deprecation warning
- Component 3 authorization-server tests — **39 passed**

The reviewer replaced the expired Keycloak TLS certificate in the existing
container mount and verified realm discovery over HTTPS before starting
the exchange-enabled AS. The [gateway lab walkthrough](../../components/gateway/README.md)
covers the browser-backed check. The invocation probe used disposable
synthetic credentials. Claude Code compatibility was outside this probe.
