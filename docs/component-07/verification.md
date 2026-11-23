# Component 7 verification

**Status** Gate 7 accepted for the synthetic lab. Independent OS signing behavior during screen lock and second-device reachability remain pending. The earlier recovered-credential invocation check also remains deferred.

The approved Swift helper uses Apple's Security framework for an ephemeral
P-256 Secure Enclave key and CryptoKit for signature conversion and local
verification. The broker selects it with `--secure-signer`.

| Check | Executed result |
|---|---|
| Native build | Compiled successfully using Swift 6.3.3 on arm64 macOS. |
| Hardware creation and export boundary | Hardware availability was true. Initialization created an Enclave key, verified a test signature and required the supported private-key external-representation API to fail. |
| Protocol interoperability | Actual hardware-generated token-endpoint and gateway proofs passed the existing Python DPoP verifier. JOSE signatures were 64 bytes. Two helper sessions had different thumbprints. |
| Request restrictions and helper death | Tests rejected an export operation, an unapproved endpoint and a token supplied to the token-endpoint proof request. Helper death prevented further signing. Duplicate IPC members terminated the helper. A deterministic DER fixture verified leading-zero padding in both JOSE integers. |
| Regression | The final combined broker and hardware suite passed 18 tests. Gateway regressions passed 26 tests, AS regressions passed 57 tests, and mock regressions passed 8 tests with the existing Starlette warning. |
| Reviewer regression | The reviewer rebuilt the helper and reran all 18 broker and hardware tests successfully. The live Keycloak suite passed all 45 tests. |
| Live hardware invocation | The reviewer launched the broker with the hardware signer, completed sign-in and exchange, and observed Claude Code return MOCK_OK. The gateway's nonce and success request IDs matched the broker's two attempt events. The AS recorded a nonce challenge and successful exchange. After exit, the broker process, helper and callback listener were absent. |
| Physical lock and unlock | The reviewer locked the Mac with a disposable hardware session active. The helper exited and subsequent signing was rejected. A new hardware session signed successfully after unlock. |
| IPC timeout | A disposable helper that never replied was rejected after 5.0 seconds. |
| Simulated signing denial | A controlled helper fixture returned its public key, then exited on the signing request. The adapter rejected signing, confirmed helper exit and returned no proof. |
| Actual Apple signing denial | The reviewer created a disposable Secure Enclave key with user-presence access control and disabled interactive authentication. Key creation succeeded. The signing API returned LocalAuthentication error -1004 (notInteractive) and no signature. This diagnostic uses a stricter access-control profile than the broker default. |
| Remaining conditions | Direct observation of OS signing restrictions with a retained key reference independently of the helper's lock policy remains untested. Second-device reachability and the previously deferred recovered-credential invocation remain pending. |

The lock-state check was adapted to observed macOS behavior. The screen-lock
field is absent while unlocked. The helper requires an active, completed
console login, fails if session information is unavailable, and checks the
explicit lock flag before signing and every 250 ms. The physical lock test verified application-level session termination.
It did not isolate the OS key-access decision with a retained reference.
Polling has an observation window.

The signing helper uses a local unsigned lab build. Hardware-backed key
custody does not establish caller authorization. Further debugger extraction
and recovered-credential reuse tests remain pending as requested. No new
credential extraction experiment was performed.

[Build and verification instructions](../../components/broker/native/README.md)

## What the verification establishes

| Concept | Observed evidence | Interpretation |
|---|---|---|
| Private-key custody | Secure Enclave key creation and signatures succeeded. The supported raw private-key export operation failed. | The helper can request signing while the private key remains protected by the hardware-backed API. This evidence covers the tested API behavior. |
| Public-key distribution | Hardware-generated proofs passed the Python verifier and the live AS/gateway path. | The public JWK and signatures interoperate with the existing DPoP contract. The helper's private-key reference stays on the Mac. |
| Key access policy | A user-presence-protected key returned notInteractive when authentication UI was prohibited. | Apple enforced that diagnostic key's authentication requirement during signing. The default broker profile has a different policy. |
| Broker lock policy | Physical screen lock ended the helper session. A new session worked after unlock. | Application-level termination was observed. The OS key-access decision with a retained reference is still a pending condition. |
| Caller authorization | Component 6 demonstrated that a second client holding the local session secret could invoke during the session. | Secure Enclave custody alone leaves this local caller boundary to be strengthened separately. |

The Swift helper holds a key reference and public key. The broker holds the
access token, server nonces and completed proofs. The session uses a
nonpermanent hardware key. Persistent Keychain storage and recovery were
outside these tests. No per-proof Touch ID prompt is claimed for the default
profile. See the [design overview](design-spec.md#secure-enclave-overview)
for the distinction between hardware custody, access policy and caller
authorization.

## Apple API denial evidence

The reviewer ran `SigningDenialCheck.swift` and observed:

```text
User-presence-protected hardware key created
Apple signing API rejected the operation: domain=com.apple.LocalAuthentication code=-1004
No signature returned
```

The code is `LAError.Code.notInteractive`. User authentication was required
for this key, while the diagnostic's authentication context prohibited UI.
This verifies a real signing-time denial. The earlier controlled helper
fixture separately verified the Python adapter's handling of a failed signer.
The diagnostic did not test a person cancelling Touch ID or the default
broker key's OS access decision during screen lock.
[Apple notInteractive documentation](https://developer.apple.com/documentation/localauthentication/laerror-swift.struct/code/notinteractive)
