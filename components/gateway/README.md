# Component 4 lab gateway

Use only the synthetic lab identity and disposable credentials. Run from this
directory with Python 3.12 or newer.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python -m pytest -q
```

## Run the browser-to-mock check

1. Start [Keycloak](../oauth-lab/README.md) and the
   [exchange-enabled authorization server](../oauth-as/README.md). Verify the
   Keycloak discovery endpoint using the Keycloak lab CA. If a lab certificate
   has expired, provision fresh lab TLS and update the corresponding CA
   paths before proceeding. The imported synthetic subject must match the AS
   exchange policy.
2. Generate the gateway TLS files and a separate mock credential in an
   owner-only lab directory. From the gateway directory, run:

   ```sh
   lab_home="${LAB_HOME:-$HOME/secure-claude-lab}"
   mkdir -p -m 700 "$lab_home"
   gateway_work="$(mktemp -d "$lab_home/gateway.XXXXXX")"
   sh ../oauth-lab/make-lab-tls.sh "$gateway_work/tls"
   (umask 077
    .venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))' > "$gateway_work/mock.token")
   printf '%s\n' "$gateway_work"
   ```

3. In a second terminal, from the gateway directory, set `gateway_work`
   to the printed path and start the mock on IPv4 loopback.

   ```sh
   MOCK_LLM_TOKEN="$(cat "$gateway_work/mock.token")" \
     .venv/bin/python -m uvicorn app.main:app --app-dir ../mock-llm \
     --host 127.0.0.1 --port 8765 --no-access-log
   ```

4. In the gateway terminal, set `as_work` to the Component 3 lab directory
   and start the gateway.

   ```sh
   GATEWAY_MOCK_TOKEN="$(cat "$gateway_work/mock.token")" \
     .venv/bin/python gateway.py --as-ca "$as_work/tls/ca.pem" \
     --tls-cert "$gateway_work/tls/server.pem" --tls-key "$gateway_work/tls/server.key"
   ```

5. In another terminal, from the gateway directory, set `gateway_work`,
   `as_work`, and `LAB_TLS_DIR` to the same lab paths and run the probe.

   ```sh
   .venv/bin/python lab_invoke.py "$as_work/exchanger" \
     --keycloak-ca "$LAB_TLS_DIR/ca.pem" --as-ca "$as_work/tls/ca.pem" \
     --gateway-ca "$gateway_work/tls/ca.pem"
   ```

   Sign in with the synthetic employee in the lab browser profile. The
   probe expects the mock text in both JSON and SSE, plus the SSE
   `message_stop` event. It prints `component_04_succeeded` on success.
   Check the gateway terminal for two `invocation_succeeded` events with
   distinct request IDs. Verify the listener with
   `lsof -nP -iTCP:8082 -sTCP:LISTEN`.

## Enable Component 5 DPoP

Run the DPoP profile in the same synthetic lab after checking the current
Keycloak, AS and gateway certificates. Use the lab paths above. The AS and
gateway each need their own nonce authentication key. Generate the files
once for a DPoP lab run.

```sh
(
  set -euC
  umask 077
  : "${as_work:?Set the authorization-server lab directory}"
  : "${gateway_work:?Set the gateway lab directory}"
  mkdir -p "$gateway_work/dpop"
  chmod 700 "$gateway_work/dpop"
  .venv/bin/python -c 'import secrets,sys; sys.stdout.buffer.write(secrets.token_bytes(32))' \
    > "$as_work/keys/dpop-nonce.key"
  .venv/bin/python -c 'import secrets,sys; sys.stdout.buffer.write(secrets.token_bytes(32))' \
    > "$gateway_work/dpop/nonce.key"
)
```

Stop the existing AS and gateway before starting the DPoP profile on the
same ports. Leave Keycloak and the mock running. Add these options to the
existing commands.

| Service | Additional options |
|---|---|
| Authorization server | `--dpop-nonce-key "$as_work/keys/dpop-nonce.key"` alongside `--exchange-policy` |
| Gateway | `--dpop-nonce-key "$gateway_work/dpop/nonce.key" --dpop-replay-dir "$gateway_work/dpop"` |
| Invocation probe | `--dpop` alongside the existing CA options |

Expect `component_05_succeeded`. The probe completes each endpoint's nonce
challenge, verifies the AS-signed token and its key binding, and verifies
JSON and SSE using fresh request proofs. In the server logs, expect an AS
nonce challenge and successful exchange, then a gateway nonce challenge
and two successful invocations. The probe keeps credentials in memory and
prints only its outcome.

Keep each service's nonce key and replay database together across restarts.
If replay state is lost or reset, replace that service's nonce key before
serving again so previously issued nonces cannot be accepted with empty
state. To return to the bearer profile, restart both services without their
DPoP options and run the probe without `--dpop`.

New lab directories use `auth-server-token-exchange-replay.sqlite3` for the
authorization server and `llm-gateway-request-proof-replay.sqlite3` for the
gateway. An existing directory continues to use its original database
filename. If both names exist for one service, startup fails so the service
cannot accidentally select a different replay history.

## Component 8A offline Converse verification

The Bedrock adapter has its own optional SDK dependencies. From this directory:

```sh
.venv/bin/python -m pip install -r requirements-bedrock.txt
.venv/bin/python -m pytest -q
```

Tests inject synthetic SDK clients or use botocore Stubber with explicit
synthetic credentials. They exercise the normal DPoP gateway route, JSON
translation and SSE completion without resolving AWS credentials or calling
Bedrock. The existing mock profile remains the default.

`bedrock-routes.example.json` documents the configuration shape. Its
placeholders intentionally fail validation. For stage 8B, replace them with
the reviewed alias, Region, model and IAM resources on the isolated AWS host.
The backend selects a refreshing EC2 instance-role provider and disables
SDK retries, environment proxies and configured endpoint overrides.

The Bedrock-specific additions to the gateway launch command are:

```sh
--backend bedrock --bedrock-routes /absolute/path/to/reviewed-routes.json
```

Supply the existing required DPoP and TLS options. The local mock profile
uses its separate mock credential. The Bedrock profile uses the workload
role. Stage 8B's remote endpoints, tunnel, deployment and live cost plan
require the separate review described in the Component 8 design.

## Actual Claude Code offline text check

With the lab services stopped, run from this directory:

```sh
.venv/bin/python manual_claude_check.py
```

Expect the installed Claude Code CLI to print `MOCK_OK`, followed by
`Offline Claude Code adapter check passed`. A model-alias warning can
appear because `lab-claude-text` is a synthetic route name. This is one
non-interactive text invocation with tools disabled.

The harness launches the actual CLI and the broker's temporary local listener.
It uses the normal DPoP gateway and Converse conversion, with synthetic SDK
responses and in-process signing-trust fixtures. No other servers or AWS
credentials are needed. Browser sign-in, hardware signing and remote TLS are
outside this specific check. Temporary credentials, replay files, local
listener and child configuration are cleaned up on exit.

The explicit broker `--text-only` profile supplies a 128-token cap, disables
thinking and caching, omits effort and structured-output requests, and
disables automatic CLI retries. The adapter validates and removes only
empty/disabled feature fields and bounded client metadata. Active unsupported
features remain rejected.
