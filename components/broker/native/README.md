# Secure Enclave signer

From the broker directory, build with Apple's installed command-line tools.

```sh
mkdir -p .env.native
xcrun swiftc native/SecureSigner.swift -o .env.native/secure-signer
```

Run the Component 6 broker command with this additional option.

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
  .venv/bin/python -m pytest -q
```

The helper polls the current console-session dictionary every 250 ms and
before signing. On this Mac, the lock field is absent while unlocked. It
requires an active, completed console login, treats an explicit lock flag
as locked, and exits on lock or unavailable session information. This
session check needs manual physical lock/unlock verification before Gate 7
acceptance. Its polling interval creates a small observation window.
The native program currently uses an unsigned local lab build. Production
requires a separate signed deployment and caller-authorization review.
