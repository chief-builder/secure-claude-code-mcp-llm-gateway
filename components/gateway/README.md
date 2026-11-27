# LLM gateway

## What it is

The service in front of the model, at `https://127.0.0.1:8082`. It accepts Anthropic
Messages requests, checks the caller's access token and DPoP proof, and forwards the
request to the mock or to Amazon Bedrock. It is the only component that holds
credentials for the model backend. This directory covers Component 4 (token checks
and policy), the gateway side of Component 5 (DPoP proofs, nonces and replay) and
Component 8 (the Bedrock adapter).

## Run it

The [quickstart](../../docs/quickstart.md) creates the gateway's certificate, mock
credential and nonce key (step 2) and starts the mock and the gateway with DPoP
(step 4). The commands below assume its lab paths are loaded, and that Keycloak, the
authorization server and the mock are running. Port 8082 must be free.

### DPoP profile

This is the profile the quickstart starts. The authorization server must also be
running with its `--dpop-nonce-key` option.

```sh
GATEWAY_MOCK_TOKEN="$(cat "$gateway_work/mock.token")" \
  uv run python gateway.py \
  --as-ca "$as_work/tls/ca.pem" \
  --tls-cert "$gateway_work/tls/server.pem" \
  --tls-key "$gateway_work/tls/server.key" \
  --dpop-nonce-key "$gateway_work/dpop/nonce.key" \
  --dpop-replay-dir "$gateway_work/dpop"
```

Exercise it from another terminal with the probe, and sign in with the synthetic
user when the browser opens:

```sh
uv run python lab_invoke.py "$as_work/exchanger" \
  --keycloak-ca "$LAB_TLS_DIR/ca.pem" --as-ca "$as_work/tls/ca.pem" \
  --gateway-ca "$gateway_work/tls/ca.pem" --dpop
```

It prints `component_05_succeeded`. Add `--mcp` to also obtain an MCP token from the
same sign-in and check that this gateway refuses it; that needs the policy's
`mcp_subjects` list (see the
[authorization server README](../oauth-as/README.md#tokens-for-the-mcp-gateway)) and
prints `mcp_token_succeeded` as well. The probe completes each service's nonce
challenge, checks the issued token and its key binding, and makes one JSON and one
streaming call with fresh proofs. The authorization server logs a nonce challenge
and a successful exchange; the gateway logs a nonce challenge and two
`invocation_succeeded` events with different request IDs.

### Bearer profile

To see the gateway without DPoP, stop the authorization server and the gateway and
start both without their DPoP options: the authorization server without
`--dpop-nonce-key`, and the gateway without `--dpop-nonce-key` and
`--dpop-replay-dir`. Then run the probe without `--dpop`. It prints
`component_04_succeeded`. Both services must use the same profile; the gateway
refuses to trust an authorization server whose DPoP setting differs from its own.

### Bedrock backend

The Bedrock backend replaces the mock with Amazon Bedrock's Converse API. It needs
the DPoP profile and a routes file, and is meant to run on an AWS host with an
instance role:

```sh
--backend bedrock --bedrock-routes /absolute/path/to/reviewed-routes.json
```

[`bedrock-routes.example.json`](bedrock-routes.example.json) shows the shape of that
file. Its placeholders fail validation on purpose; replace them with a reviewed
model alias, Region, model and IAM resources. The live deployment, its transport
and its cost plan are described in the
[Component 8 design](../../docs/component-08/design-spec.md). Nothing in this
repository calls AWS unless you start the gateway this way on a host with AWS
credentials.

The gateway imports modules from `../oauth-as`. On another host, clone the
repository and run `uv sync --locked --no-dev`, which puts that directory on the
import path. If you copy only the `gateway` and `oauth-as` directories into a plain
virtual environment, as the original live run did, start the gateway with
`PYTHONPATH=../oauth-as` or it fails with `No module named 'dpop'`.

### The real Claude Code CLI, offline

With the lab services stopped, this runs the installed Claude Code CLI through the
broker's local listener, the DPoP gateway and the Bedrock adapter, using synthetic
SDK responses. It needs no other servers, no browser and no AWS credentials:

```sh
uv run python manual_claude_check.py
```

Expect the CLI to print `MOCK_OK`, followed by
`Offline Claude Code adapter check passed`. A model-alias warning can appear because
`lab-claude-text` is a synthetic route name.

## Test it

```sh
uv run python -m pytest -q
```

Expect 96 passed. All tests run offline. The Bedrock tests use injected SDK clients
or the SDK's own stubber with synthetic credentials; they never resolve AWS
credentials or call Bedrock.

## How it works

- [`gateway.py`](gateway.py) — credential parsing, access token validation, the
  cached trust in the authorization server's keys, policy, request limits, and
  forwarding with cancellation and deadlines.
- [`bedrock.py`](bedrock.py) — route validation, translation between Messages and
  Converse for JSON and streaming, error mapping, and the instance-role client.
- [`lab_invoke.py`](lab_invoke.py) — the probe, and the DPoP client the broker reuses.
- [Gateway walkthrough](../../docs/concepts/gateway-walkthrough.md) follows one DPoP
  request through the code.
- Design specs: [Component 4](../../docs/component-04/design-spec.md),
  [Component 5](../../docs/component-05/design-spec.md),
  [Component 8](../../docs/component-08/design-spec.md).

Keep the nonce key and the replay database
(`llm-gateway-request-proof-replay.sqlite3`, in the `--dpop-replay-dir`) together
across restarts. If the replay database is ever lost, replace the nonce key before
serving again, so nonces issued earlier cannot be accepted against empty state.

The broker's `--text-only` profile, used with the Bedrock backend, caps output at
128 tokens and turns off thinking, prompt caching and automatic retries. The adapter
strips only empty or disabled feature fields and bounded client metadata; any active
unsupported feature is rejected.

## Limits

- Text only. Tool use, images, thinking and prompt caching are rejected by the
  Bedrock adapter.
- One Bedrock route, one request at a time, at most 128 output tokens.
- Request and response bodies are capped at 1 MB, and a call at 60 seconds.
- Returning the matched stop sequence from Bedrock is covered by offline tests only.
- The address, audience and scope are fixed in code.
- No mutual TLS. The live Bedrock run reached the gateway through SSH forwarding.
