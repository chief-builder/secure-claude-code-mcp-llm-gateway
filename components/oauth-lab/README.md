# Keycloak sign-in

## What it is

The lab's identity provider and a small native client for it. Keycloak runs in
Docker with one synthetic user. The client opens the system browser, signs the user
in with OpenID Connect and PKCE, and validates the ID token that comes back. It
reports only whether sign-in succeeded. This is Component 2A of the build.

## Run it

The [quickstart](../../docs/quickstart.md) creates the lab's certificates and starts
Keycloak (steps 1 to 3). With that done and the lab paths loaded, sign in from this
directory:

```sh
uv run python login.py --ca-file "$LAB_TLS_DIR/ca.pem"
```

Sign in as `synthetic-employee` with `synthetic-local-only`. The terminal prints
`component_02a_login_succeeded` after the token is verified. Run it again in the
same browser profile to see the existing session reused. Ctrl-C cancels a pending
sign-in and closes the callback listener.

The browser does not know the lab's certificate authority. Either continue past the
warning for `127.0.0.1:8080`, or use a dedicated browser profile that trusts
`$LAB_TLS_DIR/ca.pem`; set Python's `BROWSER` variable to a launcher for that
profile if it is not your default. Remove the trust and clear the profile when you
finish.

Stop Keycloak with `docker compose down`. Its database lives in the container, so
this also resets the realm. Run it before bringing Keycloak up again after a change
to `realm.json`.

## Test it

```sh
uv run python -m pytest -q
```

Expect 34 passed and 11 skipped. The 11 are live protocol tests that run only when
`LAB_TLS_DIR` is set and Keycloak is up; with both, expect 45 passed. Do not run
the tests during an interactive sign-in, because both use callback port 8766.

## How it works

- [`oidc.py`](oidc.py) — pinned discovery, key loading, code redemption and ID token
  validation.
- [`login.py`](login.py) — the one-time loopback callback listener and the checks on
  what the browser returns.
- [`realm.json`](realm.json) — the realm, the public client and the synthetic user.
- [`compose.yaml`](compose.yaml) and [`make-lab-tls.sh`](make-lab-tls.sh) — Keycloak
  over HTTPS with a throwaway certificate authority.
- [Design spec](../../docs/component-02/design-spec.md) and the
  [acceptance report](../../docs/component-02/acceptance-report-2a.md).

## Limits

- Fixed addresses: Keycloak on `127.0.0.1:8080`, the callback on `127.0.0.1:8766`.
- One synthetic user whose password is in the repository. Never add real accounts.
- Keycloak runs in development mode with a disposable database.
- Certificates last seven days.
