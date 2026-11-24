# Quickstart

From a fresh clone to Claude Code getting an answer through the whole security path:
browser sign-in, token exchange, a DPoP-bound token, the gateway and the mock model.
It takes about ten minutes. Everything runs on your Mac, on loopback, with throwaway
keys. Unfamiliar terms are in the [glossary](glossary.md).

This path uses the software DPoP key and the mock model. The
[Secure Enclave signer](../components/broker/native/README.md) and the
[Bedrock backend](../components/gateway/README.md#bedrock-backend) are optional next
steps.

## Before you start

You need:

- macOS with [Docker](https://docs.docker.com/desktop/) running
- Python 3.12 or newer and [uv](https://docs.astral.sh/uv/)
- OpenSSL and curl (both ship with macOS)
- the [Claude Code CLI](https://code.claude.com/docs) on your `PATH` as `claude`
- these ports free on `127.0.0.1`: 8080, 8081, 8082, 8765 and 8766

Use only the synthetic user below. Never put real credentials into the lab.

## 1. Install

From the repository root:

```sh
uv sync
```

## 2. Create the lab's keys and certificates

Still in the repository root, run this block once. It creates a private directory
under `~/secure-claude-lab`, gives each service its own certificate authority and
HTTPS certificate, creates the authorization server's signing key and the exchange
client's key, and writes a policy that maps the synthetic user to a gateway identity.
Nothing is written inside the repository.

```sh
(
  set -eu
  repo="$PWD"
  lab_home="${LAB_HOME:-$HOME/secure-claude-lab}"
  mkdir -p -m 700 "$lab_home"
  kc_work="$(mktemp -d "$lab_home/keycloak-tls.XXXXXX")"
  as_work="$(mktemp -d "$lab_home/as.XXXXXX")"
  gateway_work="$(mktemp -d "$lab_home/gateway.XXXXXX")"

  # One throwaway certificate authority and HTTPS certificate per service.
  sh components/oauth-lab/make-lab-tls.sh "$kc_work/tls"
  sh components/oauth-lab/make-lab-tls.sh "$as_work/tls"
  sh components/oauth-lab/make-lab-tls.sh "$gateway_work/tls"

  cd components/oauth-as
  # The authorization server's signing key, and the exchange client's key pair.
  uv run python app.py init-keys "$as_work/keys"
  uv run python lab_exchange.py init-client "$as_work/exchanger" "$as_work/keys"
  # Policy: the synthetic Keycloak user (its ID is fixed in realm.json) may exchange,
  # and appears to the gateway under a separate opaque identity.
  uv run python - "$as_work/exchange-policy.json" \
    9ae7b8d8-cb6a-49f3-924c-2d73c8bd5b95 synthetic-gateway-subject-01 <<'PY'
import json
import sys
from pathlib import Path
from foundation import EXCHANGE_CANDIDATE

Path(sys.argv[1]).write_text(json.dumps({
    "exchange_enabled": True,
    "issuance_enabled": True,
    "candidate": EXCHANGE_CANDIDATE,
    "subjects": {sys.argv[2]: sys.argv[3]},
}))
PY

  # A credential between gateway and mock, and one DPoP nonce key per service.
  umask 077
  mkdir -m 700 "$gateway_work/dpop"
  uv run python -c 'import secrets; print(secrets.token_urlsafe(32))' > "$gateway_work/mock.token"
  uv run python -c 'import secrets,sys; sys.stdout.buffer.write(secrets.token_bytes(32))' \
    > "$as_work/keys/dpop-nonce.key"
  uv run python -c 'import secrets,sys; sys.stdout.buffer.write(secrets.token_bytes(32))' \
    > "$gateway_work/dpop/nonce.key"

  # Remember the paths so every terminal can load them.
  printf 'export repo=%q\nexport LAB_TLS_DIR=%q\nexport as_work=%q\nexport gateway_work=%q\n' \
    "$repo" "$kc_work/tls" "$as_work" "$gateway_work" > "$lab_home/lab.env"
  echo "Lab created. Paths saved in $lab_home/lab.env"
)
```

Every terminal you open from here on starts by loading those paths:

```sh
. "${LAB_HOME:-$HOME/secure-claude-lab}/lab.env"
```

## 3. Start Keycloak

In a terminal with the paths loaded:

```sh
cd "$repo/components/oauth-lab"
docker compose up -d
curl --fail --silent --retry 40 --retry-delay 3 --retry-all-errors --max-time 5 \
  --cacert "$LAB_TLS_DIR/ca.pem" --output /dev/null \
  https://127.0.0.1:8080/realms/claude-security-lab/.well-known/openid-configuration \
  && echo "Keycloak is ready"
```

The first start downloads the Keycloak image and can take a minute or two.

## 4. Start the three services

Each runs in the foreground and logs to its terminal, so use three terminals. Load
the paths in each one first.

**Terminal A — mock model**

```sh
cd "$repo/components/gateway"
MOCK_LLM_TOKEN="$(cat "$gateway_work/mock.token")" \
  uv run python -m uvicorn app.main:app --app-dir ../mock-llm \
  --host 127.0.0.1 --port 8765 --no-access-log
```

**Terminal B — authorization server**

```sh
cd "$repo/components/oauth-as"
uv run python app.py serve \
  --key-dir "$as_work/keys" \
  --upstream-ca "$LAB_TLS_DIR/ca.pem" \
  --tls-cert "$as_work/tls/server.pem" \
  --tls-key "$as_work/tls/server.key" \
  --exchange-policy "$as_work/exchange-policy.json" \
  --dpop-nonce-key "$as_work/keys/dpop-nonce.key"
```

**Terminal C — gateway**

```sh
cd "$repo/components/gateway"
GATEWAY_MOCK_TOKEN="$(cat "$gateway_work/mock.token")" \
  uv run python gateway.py \
  --as-ca "$as_work/tls/ca.pem" \
  --tls-cert "$gateway_work/tls/server.pem" \
  --tls-key "$gateway_work/tls/server.key" \
  --dpop-nonce-key "$gateway_work/dpop/nonce.key" \
  --dpop-replay-dir "$gateway_work/dpop"
```

## 5. Check that everything is up

In a fourth terminal with the paths loaded:

```sh
curl --fail --silent http://127.0.0.1:8765/health && echo
curl --fail --silent --cacert "$as_work/tls/ca.pem" \
  https://127.0.0.1:8081/.well-known/oauth-authorization-server && echo
curl --fail --silent --cacert "$gateway_work/tls/ca.pem" https://127.0.0.1:8082/health && echo
```

You should see the mock's `"status":"healthy"`, the authorization server's metadata
including `"dpop_signing_alg_values_supported":["ES256"]`, and the gateway's
`{"status":"ok"}`.

## 6. Run Claude Code through the broker

In the same fourth terminal:

```sh
cd "$repo/components/broker"
uv run python broker.py "$as_work/exchanger" \
  --keycloak-ca "$LAB_TLS_DIR/ca.pem" \
  --as-ca "$as_work/tls/ca.pem" \
  --gateway-ca "$gateway_work/tls/ca.pem"
```

Your browser opens the Keycloak sign-in page.

- **Certificate warning.** The browser does not know the lab's certificate authority,
  so it warns about `127.0.0.1:8080`. Continue past the warning, or add
  `$LAB_TLS_DIR/ca.pem` to a dedicated browser profile for a clean run.
- **Sign in** as `synthetic-employee` with the password `synthetic-local-only`. You
  have five minutes.

The broker then exchanges the token, launches Claude Code with one fixed prompt, and
exits. A successful run ends like this:

```text
INFO broker event=login_succeeded broker_request_id=…
INFO broker event=exchange_verified broker_request_id=…
INFO broker event=gateway_nonce_required broker_request_id=… gateway_request_id=…
INFO broker event=gateway_response broker_request_id=… gateway_request_id=…
INFO broker event=invocation_succeeded broker_request_id=…
MOCK_OK — Local inference working
```

`MOCK_OK` is the mock model's reply, delivered to the real Claude Code CLI through
the broker and the gateway. The authorization server's terminal shows a nonce
challenge and `exchange_succeeded`; the gateway's shows a nonce challenge and
`invocation_succeeded`. [One request, end to end](concepts/request-walkthrough.md)
explains each of those lines.

## 7. Shut down and clean up

Press Ctrl-C in terminals A, B and C. Then, in a terminal with the paths loaded:

```sh
cd "$repo/components/oauth-lab"
docker compose down
```

To delete the lab's keys and certificates, remove the three directories named in
`lab.env` and the file itself, or the whole `~/secure-claude-lab` folder if nothing
else is in it. If you added the lab certificate authority to a browser profile,
remove it there too.

The certificates last seven days. After that, clean up and start again from step 2.

## If something goes wrong

| Symptom | Likely cause and fix |
|---|---|
| A service exits with "address already in use" | Something else holds the port. Find it with `lsof -nP -iTCP:8081 -sTCP:LISTEN` (change the number) and stop it |
| `docker compose` says `Set LAB_TLS_DIR` | The paths are not loaded in this terminal. Run the `lab.env` line from step 2 |
| The authorization server exits with "pinned upstream trust unavailable" | Keycloak is not ready or not running. Repeat step 3 |
| The broker prints only `session_failed` | Sign-in timed out or was cancelled, a service is down, or `claude` is not on your `PATH`. Check step 5, then run the broker again |
| Everything worked last week and now fails on trust | The seven-day certificates expired. Clean up and start from step 2 |

## Where to go next

- [One request, end to end](concepts/request-walkthrough.md) — what just happened.
- [Component READMEs](../README.md#components) — run and test each part on its own.
- [Documentation index](README.md) — explanations and verification records.
