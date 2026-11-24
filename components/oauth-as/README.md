# Authorization server

## What it is

A small authorization server, separate from Keycloak, at `https://127.0.0.1:8081`.
It trusts Keycloak only to say who the user is. It decides whether to issue a
gateway access token, signs it with its own key, and can bind it to the caller's
DPoP key. This directory covers Component 2B (metadata and signing keys), Component
3 (token exchange) and the server side of Component 5 (DPoP). The DPoP verifier in
[`dpop.py`](dpop.py) is shared with the gateway.

## Run it

The [quickstart](../../docs/quickstart.md) creates the keys and policy (step 2) and
starts the server with token exchange and DPoP (step 4). The commands below assume
its lab paths are loaded and Keycloak is running. Port 8081 must be free.

### Metadata and keys only

Leave out the exchange options to serve only metadata and the public signing key:

```sh
uv run python app.py serve \
  --key-dir "$as_work/keys" \
  --upstream-ca "$LAB_TLS_DIR/ca.pem" \
  --tls-cert "$as_work/tls/server.pem" \
  --tls-key "$as_work/tls/server.key"
```

Check it from another terminal:

```sh
curl --fail --silent --show-error --cacert "$as_work/tls/ca.pem" \
  https://127.0.0.1:8081/.well-known/oauth-authorization-server && echo
curl --fail --silent --show-error --cacert "$as_work/tls/ca.pem" \
  https://127.0.0.1:8081/jwks && echo
curl --silent --show-error --include --cacert "$as_work/tls/ca.pem" \
  -d 'grant_type=urn:ietf:params:oauth:grant-type:token-exchange' \
  https://127.0.0.1:8081/token
```

Expect the issuer with empty grant and response type lists, one public RSA signing
key, and HTTP 404 for the token request.

### Token exchange

Add the policy to enable the token endpoint with Bearer tokens:

```sh
uv run python app.py serve \
  --key-dir "$as_work/keys" \
  --upstream-ca "$LAB_TLS_DIR/ca.pem" \
  --tls-cert "$as_work/tls/server.pem" \
  --tls-key "$as_work/tls/server.key" \
  --exchange-policy "$as_work/exchange-policy.json"
```

Then run the probe from another terminal and sign in with the synthetic user:

```sh
uv run python lab_exchange.py probe "$as_work/exchanger" \
  --keycloak-ca "$LAB_TLS_DIR/ca.pem" --as-ca "$as_work/tls/ca.pem" \
  --expected-subject synthetic-gateway-subject-01
```

It prints `component_03_succeeded` after checking the issued token and confirming
that a reused ID token, a Keycloak access token and the issued token itself are all
refused as input.

### Token exchange with DPoP

Add `--dpop-nonce-key "$as_work/keys/dpop-nonce.key"` to the previous `serve`
command. The server then requires a DPoP proof and issues tokens bound to the
caller's key. This is the form the quickstart uses; exercise it with the gateway's
[DPoP probe](../gateway/README.md#dpop-profile).

## Test it

```sh
uv run python -m pytest -q
```

Expect 55 passed. All tests run offline. A change here can break the gateway and
broker, which import from this directory, so run their suites too.

## How it works

- [`foundation.py`](foundation.py) — pinned addresses, key loading with ownership
  and permission checks, and strict JSON and key-set parsing.
- [`app.py`](app.py) — startup, metadata, and the cached check of Keycloak's
  discovery document and keys. A successful check is cached for 60 seconds; a failed
  one returns HTTP 503 and is retried after five seconds.
- [`exchange.py`](exchange.py) — client authentication, ID token validation, the
  policy, token signing, and the SQLite store that makes each assertion, ID token
  and proof single-use.
- [`dpop.py`](dpop.py) — DPoP proof validation and stateless nonces.
- [Authorization server walkthrough](../../docs/concepts/authorization-server-walkthrough.md)
  follows one exchange through the code.
- Design specs: [Component 2](../../docs/component-02/design-spec.md),
  [Component 3](../../docs/component-03/design-spec.md),
  [Component 5](../../docs/component-05/design-spec.md).

Keep the key directory across restarts. It holds the signing key, whose identifier
must stay stable, and the replay database
`auth-server-token-exchange-replay.sqlite3`. If the replay database is ever lost,
replace `dpop-nonce.key` before serving again, so nonces issued earlier cannot be
accepted against empty state.

## Limits

- One exchange client, one audience (`urn:lab:llm-gateway`) and one scope
  (`llm:invoke`), all fixed in code.
- The exchange client's private key is a file on the same machine. In production
  that authority belongs at a separate service boundary.
- An ID token is a bearer credential for the minute it is accepted. One-time use
  stops a second exchange, not the first.
- No refresh tokens. Access tokens last at most five minutes.
- The client assertion's explicit type from the RFC 7523 update is not yet required.
