# Component 6 lab credential broker

The foreground broker launches the installed Claude Code CLI for a single
synthetic text prompt. Start the existing Keycloak, DPoP-enabled authorization
server and gateway, and the mock before running it. Verify that all three lab
CAs are current. The [Component 5 walkthrough](../gateway/README.md#enable-component-5-dpop)
covers those services.

From this directory, install the lab dependencies and run the tests.

```sh
uv sync
uv run python -m pytest -q
```

## Browser-to-Claude Code check

Set `as_work` to the Component 3 lab directory, `LAB_TLS_DIR` to the Keycloak
TLS directory, and `gateway_work` to the Component 4 gateway lab directory.
The broker reads the synthetic exchange client's private key from
`$as_work/exchanger`, which must be an owner-only directory outside the
repository. The lab setup already creates it that way.

```sh
uv run python broker.py "${as_work:?Set the AS lab directory}/exchanger" \
  --keycloak-ca "${LAB_TLS_DIR:?Set the Keycloak TLS directory}/ca.pem" \
  --as-ca "$as_work/tls/ca.pem" \
  --gateway-ca "${gateway_work:?Set the gateway lab directory}/tls/ca.pem"
```

Sign in with the synthetic user in the system browser. Expect `MOCK_OK`,
a broker success event, and a matching gateway event. The process exits
after the CLI exits and closes its temporary listener. A nonce challenge
can produce two gateway response IDs under the same broker request ID.

The lab launcher supplies a clean child environment and temporary configuration,
disables tools and hooks, and uses a fixed text prompt. It adapts one inline
system message from the installed CLI to the mock's top-level `system` field
for a single user turn. This compatibility step is scoped to the text mock.
