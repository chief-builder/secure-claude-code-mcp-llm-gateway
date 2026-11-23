# Component 2A · Keycloak browser SSO

This macOS lab uses Docker Compose, OpenSSL, Python 3.12+ and a disposable
browser profile. The native public client opens the system browser and reports
only the login outcome. See the [design spec](../../docs/component-02/design-spec.md)
for the callback and claims contracts.

## Start the lab

From this directory, run these commands in a local terminal. Keep the shell
open so the TLS path is available for cleanup.

```sh
uv sync
lab_home="${LAB_HOME:-$HOME/secure-claude-lab}"
mkdir -p -m 700 "$lab_home"
lab_work="$(mktemp -d "$lab_home/keycloak-tls.XXXXXX")"
export LAB_TLS_DIR="$lab_work/tls"
sh make-lab-tls.sh "$LAB_TLS_DIR"
docker compose up -d
```

When Keycloak is ready, its discovery document is available under the
`claude-security-lab` realm at `https://127.0.0.1:8080`. The two fixed ports
are 8080 for HTTPS and 8766 for the temporary HTTP callback.

Use a dedicated lab browser profile with the disposable CA trusted for the
Keycloak URL. Follow your local browser's certificate trust process and remove
any added trust after the lab. The Python client uses the CA file directly.
Use the system browser with the lab profile active, or configure Python's
`BROWSER` setting with a launcher for that profile.

```sh
uv run python login.py --ca-file "$LAB_TLS_DIR/ca.pem"
```

Sign in as `synthetic-employee` with `synthetic-local-only`. The terminal prints
`component_02a_login_succeeded` after token verification. Run the command again
in the same browser profile to check session reuse. Ctrl-C cancels a pending
login and closes the callback. Keep production credentials out of the lab.

## Verify and clean up

```sh
uv run python -m pytest -q
docker compose down
```

The test suite uses the running realm for live protocol cases when
`LAB_TLS_DIR` is set. Unset it for tests that use local fixtures. Run tests
separately from an interactive login because both use the fixed callback port.

Remove the disposable TLS directory after shutdown and clear the lab browser
profile, including its history and cookies. The Compose service uses a disposable
container database. To apply realm changes, run `docker compose down` before
bringing the service back up.
