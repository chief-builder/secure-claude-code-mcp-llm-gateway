# Debugger-assisted software key extraction verification

**Status** Synthetic key recovery and independent signing verified.
Gateway invocation using the recovered token and key remains pending.
Gate 6 was accepted for the synthetic lab with the recovered-credential gateway invocation check pending. Cleanup of recovered artifacts has not been confirmed.

## Scope and observed results

These checks used disposable Python processes owned by the reviewer on the
reviewer's Mac. LLDB obtained debugger access under macOS Developer Tools
authorization. System Integrity Protection was enabled during the earlier
environment check. The authorization requirement is part of the test conditions.

| Check | Result |
|---|---|
| Attach to a disposable Python process | LLDB attached to PID 57991, paused it, and detached successfully. The reviewer subsequently confirmed the process exited. |
| Recover a software DPoP key | The second disposable process, PID 59161, held a fresh ProofClient key. LLDB acquired Python's interpreter lock and executed Python serialization inside that process. The export returned zero and wrote an owner-only key file. |
| Compare recovered and original key identity | A separate Python process loaded the recovered key and matched its public-key thumbprint to the original process's thumbprint. |
| Sign independently with the recovered key | The separate process signed and verified a fresh synthetic challenge successfully. |
| Obtain a real lab access token and matching key | A third disposable process, PID 60913, completed the broker's browser sign-in and exchange flow and held the resulting synthetic gateway token and DPoP key. |
| Recover that token and matching key | The reviewer reported the new token-and-key extraction directory after running the debugger export. Loading these two files and verifying their binding in a separate client remains pending. |
| Invoke the live gateway with recovered credentials | Pending. No successful gateway response from the recovered pair has been observed. |

The extraction used debugger-injected Python serialization. It demonstrates
that an authorized debugger can cause this software signer to export its
private key. It does not establish raw memory-scanning capability or access
by a process lacking macOS debugging authorization.

## Local artifacts at the last checkpoint

These paths contain synthetic lab material and should be cleaned up after
verification. Their continued existence and the process lifetimes have not
been rechecked.

| Purpose | Reported directory |
|---|---|
| Earlier key-only recovery | `/var/folders/h7/mhpz888d6xzcm62796jyks1c0000gn/T/dpop-extraction-5ajbkdcd` |
| Token and key recovery | `/var/folders/h7/mhpz888d6xzcm62796jyks1c0000gn/T/dpop-token-extraction-dq0dxtm1` |

The first directory contains `recovered.key` and `expected-thumbprint.txt`.
The second is expected to contain `recovered.key` and `access.token`.
Keep the raw values out of terminal output, screenshots and documentation.

## Remaining steps to complete the gateway check

1. Confirm the AS, gateway, Keycloak and mock are still listening on the
   established loopback ports and that their TLS certificates are current.
2. Check the recovered token's expiration locally without printing the token.
   The token is short-lived. If expired, repeat acquisition and recovery
   with a fresh synthetic session before attempting invocation.
3. In a separate test client, load the recovered private key and access token.
   Derive the public JWK and its thumbprint from the recovered key.
   Verify the token signature against the pinned AS JWKS, plus its issuer,
   audience, type, times, scope and `cnf.jkt`. Require the binding to match
   the recovered key.
4. Use that recovered pair to make one synthetic Messages request to the
   existing lab gateway. Generate a fresh proof for the gateway endpoint
   and complete its nonce challenge using another fresh proof. Record the
   HTTP result, request ID and whether the response contains `MOCK_OK`.
5. Match that request ID to the gateway's invocation audit event. A successful
   response would demonstrate that debugger-recovered software key material
   and its still-valid token can authorize a request from a second process.
   If the request fails, record the precise stage and sanitized result.
   Expiration alone does not resolve the key-extraction question.
6. Delete both sets of recovered files and remove their temporary directories.
   Stop any remaining disposable test processes after confirming their identity,
   since recorded PIDs may be reused. Confirm LLDB has detached.
7. Update this record and the Component 6 verification record with the observed
   result and the Developer Tools authorization condition.

The response containing the next invocation instructions was hidden by the
chat interface during the walkthrough. The reviewer supplied a screenshot
of that message. No gateway invocation result was provided afterward.

## Cleanup of the known extraction files

Run after completing or abandoning the invocation check.

```sh
rm -f \
  "/var/folders/h7/mhpz888d6xzcm62796jyks1c0000gn/T/dpop-extraction-5ajbkdcd/recovered.key" \
  "/var/folders/h7/mhpz888d6xzcm62796jyks1c0000gn/T/dpop-extraction-5ajbkdcd/expected-thumbprint.txt" \
  "/var/folders/h7/mhpz888d6xzcm62796jyks1c0000gn/T/dpop-token-extraction-dq0dxtm1/recovered.key" \
  "/var/folders/h7/mhpz888d6xzcm62796jyks1c0000gn/T/dpop-token-extraction-dq0dxtm1/access.token"

rmdir \
  "/var/folders/h7/mhpz888d6xzcm62796jyks1c0000gn/T/dpop-extraction-5ajbkdcd" \
  "/var/folders/h7/mhpz888d6xzcm62796jyks1c0000gn/T/dpop-token-extraction-dq0dxtm1"
```

File deletion removes the named artifacts. Secure erasure on SSD storage is
outside this check.

## Follow-up for Component 7

Repeat the key-custody comparison with the proposed Secure Enclave signer.
Verify authorized signing and whether raw private key export is prevented.
Evaluate permission to invoke the signer separately. Protecting key export
does not by itself stop a caller that can ask the broker to make requests.
