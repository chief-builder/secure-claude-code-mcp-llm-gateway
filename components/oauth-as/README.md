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

### Tokens for the MCP gateway

The server can issue a second kind of token, for the MCP gateway, so that a token
for model calls cannot be used for tools and the reverse. It does so only when
running with DPoP, and only for subjects the policy lists. Add the list to the
policy file next to `subjects`:

```json
"mcp_subjects": ["9ae7b8d8-cb6a-49f3-924c-2d73c8bd5b95"]
```

A policy without the list issues no MCP tokens. A request asks for one with
`resource=https://127.0.0.1:8083/mcp` and `scope=mcp:invoke` in place of `audience`
and `scope=llm:invoke`. One sign-in can be exchanged once for each kind. The
gateway's DPoP probe exercises this when run with `--mcp`; see the
[gateway README](../gateway/README.md#dpop-profile).

## Test it

```sh
uv run python -m pytest -q
```

Expect 88 passed. All tests run offline. A change here can break the gateway and
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
- [Tokens and modes](../../docs/concepts/tokens-and-modes.md) shows Bearer mode
  against DPoP mode, and the two kinds of token, in diagrams.
- Design specs: [Component 2](../../docs/component-02/design-spec.md),
  [Component 3](../../docs/component-03/design-spec.md),
  [Component 5](../../docs/component-05/design-spec.md).

Keep the key directory across restarts. It holds the signing key, whose identifier
must stay stable, and the replay database
`auth-server-token-exchange-replay.sqlite3`. If the replay database is ever lost,
replace `dpop-nonce.key` before serving again, so nonces issued earlier cannot be
accepted against empty state.

## Limits

- One exchange client and two fixed targets: the model gateway
  (`urn:lab:llm-gateway`, scope `llm:invoke`) and the MCP gateway
  (`https://127.0.0.1:8083/mcp`, scope `mcp:invoke`). All are fixed in code.
- The exchange client's private key is a file on the same machine. In production
  that authority belongs at a separate service boundary.
- An ID token is a bearer credential for the minute it is accepted. It can be
  exchanged once per target, so a stolen one that was already used for a model
  token could still be exchanged once for an MCP token by someone holding the
  exchange client's key.
- No refresh tokens. Access tokens last at most five minutes.
- The server accepts a client assertion typed `client-authentication+jwt`, typed
  `JWT`, or untyped, and rejects any other declared type. The type is compared as
  a media type name: case and a leading `application/` do not matter. It does not
  require the explicit type, as RFC 10070 advises.
