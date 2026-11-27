# Outcome: mcp-gateway

Consumes: [spec.md](spec.md), [plan.md](plan.md)
Date: 2026-11-27

## What was built

`components/gateway/mcp_gateway.py`: the MCP gateway, a separate service on
`https://127.0.0.1:8083/mcp` for MCP revision 2026-07-28. Two functions in the
accepted `gateway.py` each gained one parameter (`audience`, `scope`) whose default
is the LLM gateway's value. The lab's test client can now use its MCP token at the
gateway.

## Differences from the spec and plan

- An older protocol revision named consistently in the header and the body is
  refused with the unsupported-version error, not the header-mismatch error. This
  is what the MCP specification defines; the spec's criterion carries a note.
- The plan gave each of eleven units its own commit. Units 2 to 6 were written
  together and share one commit, because the handler could not be tested in
  slices without stand-ins that would then be thrown away.
- The component has its own README, `README-mcp.md`, beside the LLM gateway's.

## What was run

Offline:

| Check | Result |
|---|---|
| `gateway` suite | 149 passed: 97 for the LLM gateway (96 unmodified, 1 new for the two parameters) and 52 for the MCP gateway |
| `mock-llm`, `mock-mcp`, `oauth-as` suites | 8, 28 and 88 passed |
| `oauth-lab` suite | 34 passed, 11 skipped (need Keycloak) |
| `broker` suite | 13 passed, 6 skipped (need the hardware signer) |
| `tools` suite, lint, documentation check | 28 passed; no problems |

Live, on one Mac, from a fresh clone of the branch under the home folder, on
2026-11-27:

1. Quickstart steps 1 to 5: Keycloak in Docker, the mock model, the authorization
   server and the LLM gateway, all in DPoP mode.
2. The setup block from `README-mcp.md`, pasted into a default interactive shell.
   It printed `MCP lab created`.
3. The authorization server restarted; the mock tool server and the MCP gateway
   started with the README's commands. The health and metadata commands, pasted
   into an interactive shell, returned `{"status":"ok"}` and the metadata document.
   A request with no credential got 401.
4. The test client, with the owner signing in to Keycloak as the synthetic user.
   The first attempt timed out because nobody signed in and printed
   `component_05_failed`. The second printed `component_05_succeeded`,
   `mcp_token_succeeded` and `mcp_gateway_succeeded`.

The MCP gateway's log for that run, request IDs removed:

```text
mcp_gateway event=dpop_nonce_required request_id=…
mcp_gateway event=discovered request_id=… subject=synthetic-gateway-subject-01
mcp_gateway event=tools_listed request_id=… subject=synthetic-gateway-subject-01
mcp_gateway event=tool_called request_id=… subject=synthetic-gateway-subject-01 tool=lab_echo
mcp_gateway event=tool_refused request_id=… subject=synthetic-gateway-subject-01
```

The authorization server logged two successful exchanges from the one sign-in.
Afterwards every service was stopped, Keycloak removed, and the run's keys and the
clone deleted.

Not run live: the refusals other than the hidden tool and the missing credential.
They are covered offline only. The Secure Enclave signer was not involved.

## Checks shown to be tested

Each change was made on its own, the `gateway` suite run, and the file restored.
All 39 were caught. Two were missed on the first pass, because the stand-in replies
used were also invalid in a second way; those two tests were corrected and the
changes then caught.

In `gateway.py`: the audience parameter ignored; the scope parameter ignored.

In `mcp_gateway.py`:

- *Caller's credentials.* `Origin` header allowed; token audience not the MCP
  gateway's; scope not the MCP scope; client and scope check skipped; proof not
  bound to the token's key; proof accepted over plain HTTP; proof not recorded
  against replay; proof verifier built for the LLM gateway's address; starting
  without DPoP; the metadata address missing from challenges.
- *Request.* Missing revision header allowed; revision header not compared with
  the body; older revision accepted; `Mcp-Method` not compared; `Mcp-Name` not
  compared; `Mcp-Name` allowed to be missing; `Mcp-Name` allowed on other methods;
  capabilities allowed to be absent; notifications and extra fields allowed;
  request size unlimited.
- *Rules.* Per-tool rule skipped on calls; the unknown-tool reply naming the tool;
  tool list not filtered; tool list marked public; other methods forwarded; policy
  tool names unchecked.
- *Tool server.* Caller's capabilities forwarded; caller's whole request
  forwarded; revision header not sent upstream; incomplete results accepted; reply
  id not checked; reply type not checked; reply size unlimited; the tool server's
  extra fields passed through; a caller's disconnect ignored.
- *Audit log.* Subject written unchecked; a refused tool's name written.

## Verification

