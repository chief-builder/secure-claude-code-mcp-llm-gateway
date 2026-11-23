# Component 2B · Authorization server foundation

This FastAPI service publishes its own metadata and public signing key over HTTPS
at `127.0.0.1:8081`. It checks the pinned Keycloak discovery document and JWKS
before serving either endpoint. Its candidate exchange policy is disabled. The
only HTTP routes are metadata and JWKS.

## Start the lab

Start Component 2A Keycloak first. Keep the `LAB_TLS_DIR` exported by that setup
so 2B can validate Keycloak's certificate. From this directory in the same shell:

```sh
test -r "$LAB_TLS_DIR/ca.pem" && echo "Keycloak lab CA is available"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-test.txt
lab_home="${LAB_HOME:-$HOME/secure-claude-lab}"
mkdir -p -m 700 "$lab_home"
as_work="$(mktemp -d "$lab_home/as.XXXXXX")"
sh ../oauth-lab/make-lab-tls.sh "$as_work/tls"
.venv/bin/python app.py init-keys "$as_work/keys"
printf 'AS CA file: %s\n' "$as_work/tls/ca.pem"
.venv/bin/python app.py serve \
  --key-dir "$as_work/keys" \
  --upstream-ca "$LAB_TLS_DIR/ca.pem" \
  --tls-cert "$as_work/tls/server.pem" \
  --tls-key "$as_work/tls/server.key"
```

Use a new directory for initial key provisioning. Reuse the same key directory
on restart so the signing key and its key ID remain stable. The generated
confidential client JWK is a public placeholder for the disabled configuration
entry. Its private counterpart is discarded during setup.

A bad key, policy or upstream trust check prevents startup. A successful
upstream check is cached for up to 60 seconds. After expiry the next read
checks Keycloak again, returns HTTP 503 if the check fails, and permits a fresh
attempt after a five-second backoff.

## Check the service

In a second terminal, set `as_ca` to the AS CA file path printed during setup
and run the following commands.

```sh
curl --fail --silent --show-error --cacert "$as_ca" \
  https://127.0.0.1:8081/.well-known/oauth-authorization-server
curl --fail --silent --show-error --cacert "$as_ca" https://127.0.0.1:8081/jwks
curl --silent --show-error --include --cacert "$as_ca" \
  -d 'grant_type=urn:ietf:params:oauth:grant-type:token-exchange' \
  https://127.0.0.1:8081/token
```

Expect the AS issuer and empty grant and response type lists, a single public
RSA signing key, and a generic HTTP 404 for the token request.

Run `.venv/bin/python -m pytest -q` for the automated checks. Stop the service
with Ctrl-C. Remove the disposable `$as_work` directory when finished.

## Enable Component 3 in the synthetic lab

Use a disposable workspace and the existing verified Keycloak HTTPS setup.
Follow the key and TLS provisioning commands above, then run:

```sh
.venv/bin/python lab_exchange.py init-client "$as_work/exchanger" "$as_work/keys"
```

Obtain the synthetic employee's internal subject ID from the operator-controlled
Keycloak user record. Set `lab_subject` to that ID. Choose a separate opaque
identifier of at least 16 characters and set `gateway_subject` to that value.
The policy allows letters, digits, underscores and hyphens for both IDs.

```sh
.venv/bin/python - "$as_work/exchange-policy.json" "$lab_subject" "$gateway_subject" <<'PY'
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

.venv/bin/python app.py serve \
  --key-dir "$as_work/keys" \
  --upstream-ca "$LAB_TLS_DIR/ca.pem" \
  --tls-cert "$as_work/tls/server.pem" \
  --tls-key "$as_work/tls/server.key" \
  --exchange-policy "$as_work/exchange-policy.json"
```

Port 8081 must be free. In a second terminal, reuse the same path and subject
variables and run the probe. Sign in with the synthetic employee in the system
browser. The probe verifies the minted token and checks subject replay and
token substitution. It prints a status code and keeps tokens in process.

```sh
.venv/bin/python lab_exchange.py probe "$as_work/exchanger" \
  --keycloak-ca "$LAB_TLS_DIR/ca.pem" --as-ca "$as_work/tls/ca.pem" \
  --expected-subject "$gateway_subject"
```

Reuse the same owner-only AS key directory across enabled restarts. It also
holds the SQLite replay database. Each request uses an independently generated
correlation ID in the response and the AS audit log. Treat the minted token as
a short-lived bearer credential for this lab. One-time exchange covers repeat
redemption of the signed source assertion. The first-use race remains possible
under the conditions described in the Component 3 design.
