# Component 6 lab credential broker

The foreground broker launches the installed Claude Code CLI for a single
synthetic text prompt. Start the existing Keycloak, DPoP-enabled authorization
server and gateway, and the mock before running it. Verify that all three lab
CAs are current. The [Component 5 walkthrough](../gateway/README.md#enable-component-5-dpop)
covers those services.

From this directory, install the lab dependencies and run the tests.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python -m pytest -q
```

## Browser-to-Claude Code check

Set `as_work` to the Component 3 lab directory, `as_tls` to its current TLS
directory, `LAB_TLS_DIR` to the current Keycloak TLS directory, and
`gateway_work` to the Component 4 gateway lab directory. Create a temporary
owner-only directory outside the repository. The broker requires the existing
synthetic exchange client's private key under that directory.

```sh
(
  set -eu
  umask 077
  broker_work="$(mktemp -d /tmp/llm-broker-key.XXXXXX)"
  trap 'rm -f "$broker_work/assertion.key"; rmdir "$broker_work"' EXIT
  install -m 600 "${as_work:?Set the AS lab directory}/exchanger/assertion.key" \
    "$broker_work/assertion.key"

  .venv/bin/python broker.py "$broker_work" \
    --keycloak-ca "${LAB_TLS_DIR:?Set the Keycloak TLS directory}/ca.pem" \
    --as-ca "${as_tls:?Set the current AS TLS directory}/ca.pem" \
    --gateway-ca "${gateway_work:?Set the gateway lab directory}/tls/ca.pem"
)
```

Sign in with the synthetic user in the system browser. Expect `MOCK_OK`,
a broker success event, and a matching gateway event. The process exits
after the CLI exits and closes its temporary listener. A nonce challenge
can produce two gateway response IDs under the same broker request ID.

The lab launcher supplies a clean child environment and temporary configuration,
disables tools and hooks, and uses a fixed text prompt. It adapts one inline
system message from the installed CLI to the mock's top-level `system` field
for a single user turn. This compatibility step is scoped to the text mock.
