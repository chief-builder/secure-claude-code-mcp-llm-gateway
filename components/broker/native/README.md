# Secure Enclave signer

From the broker directory, build with Apple's installed command-line tools.

```sh
mkdir -p .env.native
xcrun swiftc native/SecureSigner.swift -o .env.native/secure-signer
```

Run the [broker command](../README.md#run-it) with this additional option.

```sh
--secure-signer "$PWD/.env.native/secure-signer"
```

The selected hardware profile creates a new session key and fails on
unavailable hardware or signing errors. The helper uses only inherited
pipes. Its private-key reference stays in the Swift process. Startup checks
that public verification succeeds and the supported raw private-key export
API fails. The Python broker receives the public JWK and completed proofs.

To run the hardware and broker tests, use the broker's Python environment.

```sh
SECURE_SIGNER_TEST_BINARY="$PWD/.env.native/secure-signer" \
  uv run python -m pytest -q
```

The helper polls the current console-session dictionary every 250 ms and
before signing. On this Mac, the lock field is absent while unlocked. It
requires an active, completed console login, treats an explicit lock flag
as locked, and exits on lock or unavailable session information. A
physical lock and unlock was checked during acceptance; see the
[verification record](../../../docs/component-07/verification.md). The polling
interval leaves a small observation window.
The native program currently uses an unsigned local lab build. Production
requires a separate signed deployment and caller-authorization review.
