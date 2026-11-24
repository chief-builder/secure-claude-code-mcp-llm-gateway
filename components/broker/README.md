# Credential broker

## What it is

A local process that stands between Claude Code and the gateway. It signs the user
in, exchanges the ID token for a gateway token bound to a DPoP key, and launches
Claude Code pointed at a temporary loopback listener. Claude Code holds only a
random secret for that one session; the broker holds the gateway token and signs a
fresh proof for every request. This directory covers Component 6 (the broker) and
Component 7 (keeping the DPoP key in Apple's Secure Enclave).

## Run it

The [quickstart](../../docs/quickstart.md) runs the broker as its last step. The
command below assumes its lab paths are loaded and that Keycloak, the authorization
server, the gateway (all with DPoP) and the mock are running.

```sh
uv run python broker.py "$as_work/exchanger" \
  --keycloak-ca "$LAB_TLS_DIR/ca.pem" \
  --as-ca "$as_work/tls/ca.pem" \
  --gateway-ca "$gateway_work/tls/ca.pem"
```

Sign in with the synthetic user when the browser opens. Expect `MOCK_OK`, a broker
`invocation_succeeded` event, and a matching event in the gateway's log. A nonce
challenge produces two gateway request IDs under one broker request ID. The broker
exits when the CLI exits and closes its listener.

The first argument is the directory holding the exchange client's private key. The
broker refuses a directory inside the repository or one that other users can read.

### With the Secure Enclave signer

Build the helper and add `--secure-signer` as described in the
[signer README](native/README.md). The DPoP key is then created inside the Secure
Enclave for the session and cannot be exported.

### Options

| Option | Effect |
|---|---|
| `--model NAME` | Model name passed to the CLI. Default `sonnet` |
| `--claude PATH` | The Claude Code executable. Default `claude` on `PATH` |
| `--secure-signer PATH` | Use the Secure Enclave helper for the DPoP key |
| `--text-only` | The restricted profile required by the Bedrock backend |

## Test it

```sh
uv run python -m pytest -q
```

Expect 13 passed and 6 skipped. The 6 are hardware tests that run only when
`SECURE_SIGNER_TEST_BINARY` points at the built helper on a Mac with a Secure
Enclave; the [signer README](native/README.md) gives the command.

## How it works

- [`broker.py`](broker.py) — key and token acquisition, the local listener and its
  boundary checks, the clean child environment, and supervision of the CLI.
- [`hardware_signer.py`](hardware_signer.py) — the pipe protocol to the signing
  helper, with size limits and a timeout.
- [`native/SecureSigner.swift`](native/SecureSigner.swift) — the helper: it creates
  the key, refuses to sign for any address but the two lab endpoints, and exits when
  the screen locks.
- [One request, end to end](../../docs/concepts/request-walkthrough.md) shows where
  the broker sits in the whole flow.
- Design specs: [Component 6](../../docs/component-06/design-spec.md),
  [Component 7](../../docs/component-07/design-spec.md).

The child gets a minimal environment and a temporary configuration directory, with
tools, hooks and slash commands disabled. For the mock, the broker moves one inline
system message from the CLI into the request's top-level `system` field.

## Limits

- A smoke harness, not a daily tool: one fixed prompt, tools disabled, and no token
  refresh. The session ends when the five-minute token expires.
- Code running as the same macOS user can read the child's session secret or drive
  the broker. Hardware custody stops the key being copied; it does not decide who
  may use it.
- The software DPoP key can be extracted by a debugger with Developer Tools
  authorization ([evidence](../../docs/component-06/debugger-extraction-verification.md)).
- The signing helper is an unsigned local build and detects screen lock by polling.
