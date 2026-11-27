# MCP gateway

## What it is

The service that stands between a caller and an MCP tool server. It accepts only a
DPoP-bound MCP token from the lab's authorization server, decides for each user
which tools they may see and call, and forwards an allowed call with its own
credential. It lives in this folder beside the [LLM gateway](README.md) and shares
that gateway's token and proof checks, but runs as a separate process with
separate credentials. [The MCP gateway, step by step](../../docs/concepts/mcp-gateway.md)
shows the path of a call in diagrams.

Claude Code is not connected to it yet; that needs the broker, which is the next
piece of work. Today it is exercised by the lab's test client.

## Run it

Complete steps 1 to 5 of the [quickstart](../../docs/quickstart.md) first, so
Keycloak, the mock model, the authorization server and the LLM gateway are running
and `lab.env` exists. Ports 8083 and 8767 must be free.

In a terminal with the paths loaded, create what the MCP gateway needs. This makes
a certificate, a nonce key, a credential shared with the mock tool server, and a
tool policy that allows the synthetic user `lab_echo` only. It also adds the
synthetic user to the authorization server's list of users who may have MCP tokens.

```sh
(
  set -eu
  cd "$repo"
  mcp_work="$(mktemp -d "$(dirname "$as_work")/mcp.XXXXXX")"
  sh components/oauth-lab/make-lab-tls.sh "$mcp_work/tls"
  umask 077
  mkdir -m 700 "$mcp_work/dpop"
  uv run python -c 'import secrets,sys; sys.stdout.buffer.write(secrets.token_bytes(32))' \
    > "$mcp_work/dpop/nonce.key"
  uv run python -c 'import secrets; print(secrets.token_urlsafe(32))' > "$mcp_work/upstream.token"
  printf '{"tools": {"synthetic-gateway-subject-01": ["lab_echo"]}}' > "$mcp_work/tool-policy.json"
  uv run python - "$as_work/exchange-policy.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
policy = json.loads(path.read_text())
policy["mcp_subjects"] = list(policy["subjects"])
path.write_text(json.dumps(policy))
PY
  printf 'export mcp_work=%q\n' "$mcp_work" >> "${LAB_HOME:-$HOME/secure-claude-lab}/lab.env"
  echo "MCP lab created"
)
```

The authorization server reads its policy at startup. Press Ctrl-C in its terminal
and start it again with the same command as in the quickstart.

Open two more terminals and load the paths in each, as the quickstart describes;
`lab.env` now also sets `mcp_work`.

**Mock tool server**

```sh
cd "$repo/components/mock-mcp"
MOCK_MCP_TOKEN="$(cat "$mcp_work/upstream.token")" uv run python mock_mcp.py
```

**MCP gateway**

```sh
cd "$repo/components/gateway"
MCP_GATEWAY_UPSTREAM_TOKEN="$(cat "$mcp_work/upstream.token")" \
  uv run python mcp_gateway.py \
  --as-ca "$as_work/tls/ca.pem" \
  --tls-cert "$mcp_work/tls/server.pem" \
  --tls-key "$mcp_work/tls/server.key" \
  --dpop-nonce-key "$mcp_work/dpop/nonce.key" \
  --dpop-replay-dir "$mcp_work/dpop" \
  --tool-policy "$mcp_work/tool-policy.json"
```

In another terminal, reload the paths and check it is up. The second command shows
the metadata it publishes, which needs no credential:

```sh
. "${LAB_HOME:-$HOME/secure-claude-lab}/lab.env"
curl --fail --silent --cacert "$mcp_work/tls/ca.pem" https://127.0.0.1:8083/health && echo
curl --fail --silent --cacert "$mcp_work/tls/ca.pem" \
  https://127.0.0.1:8083/.well-known/oauth-protected-resource/mcp && echo
```

Then run the test client. It opens the Keycloak sign-in page; sign in as
`synthetic-employee` with the password `synthetic-local-only`.

```sh
cd "$repo/components/gateway"
uv run python lab_invoke.py "$as_work/exchanger" \
  --keycloak-ca "$LAB_TLS_DIR/ca.pem" \
  --as-ca "$as_work/tls/ca.pem" \
  --gateway-ca "$gateway_work/tls/ca.pem" \
  --dpop --mcp --mcp-gateway-ca "$mcp_work/tls/ca.pem"
```

It prints three lines:

```text
component_05_succeeded
mcp_token_succeeded
mcp_gateway_succeeded
```

The last line means that, with an MCP token from the same sign-in, the client
discovered the gateway, was shown `lab_echo` and not `lab_add`, called `lab_echo`
and got its text back, and was refused `lab_add` as an unknown tool. The gateway's
terminal shows a line for each, naming the user and, for the allowed call, the tool.

To stop, press Ctrl-C in both terminals. To delete what the first block created,
in a terminal with the paths loaded:

```sh
rm -rf "$mcp_work"
```

## Test it

```sh
uv run python -m pytest -q tests/test_mcp_gateway.py
```

Expect 52 passed. All tests run offline, against the SDK-built
[mock tool server](../mock-mcp/README.md) in the same process and against
hand-made stand-ins for malformed replies.

## How it works

- [`mcp_gateway.py`](mcp_gateway.py). The request handler, `mcp`, runs the checks
  in a fixed order and forwards nothing until all pass: no `Origin` header; one
  DPoP credential; a valid MCP token; a valid proof with a current nonce; the lab
  client and the `mcp:invoke` scope; headers that agree with the body
  (`read_request`); the proof recorded against replay; then the per-tool rule.
- The token, proof and replay checks are imported from [`gateway.py`](gateway.py)
  and the authorization server's folder. They are the same code the LLM gateway
  runs, given a different audience and scope.
- `upstream_request` builds the tool server's request from named fields only, and
  `checked_result` accepts back only a complete result.
- The tool policy is a JSON file naming each user's tools by their mapped identity,
  read once at startup by `load_tool_policy`.
- [The MCP gateway, step by step](../../docs/concepts/mcp-gateway.md), with
  diagrams, and
  [the design decision](../../workflow/decisions/0003-mcp-through-the-broker-with-its-own-tokens.md).

## Limits

- Tools only, and one tool server. Prompts, resources, subscriptions, tasks,
  streamed replies and requests for user input are refused.
- An ordinary MCP client cannot use it. It requires a DPoP-bound token and proof,
  where the MCP specification's own model is a bearer token, and the lab's
  authorization server has no sign-in page for such a client. The metadata is
  published because the specification requires it.
- The policy is read once at startup, and it has no rules about a tool's arguments.
- A user the policy does not name is a valid caller with no tools.
- The audit log is the only record of who called which tool, since the tool server
  sees only the gateway's credential. It records the user's mapped identity and the
  name of an allowed tool, never arguments or results.
- The tool server is reached over plain HTTP on loopback with a shared secret.
- DPoP only. It will not start without a nonce key and a replay folder.
