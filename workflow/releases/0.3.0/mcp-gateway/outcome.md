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
| `gateway` suite | 160 passed: 97 for the LLM gateway (96 unmodified, 1 new for the two parameters) and 63 for the MCP gateway |
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

The whole live run was repeated the same day after the fixes that verification
led to, from a fresh clone of the fixed code, with the same result and the same
log lines. The metadata then showed `"bearer_methods_supported":[]` and a request
with no credential got 401 with a challenge naming the scope and the metadata
address. Again the first attempt timed out waiting for sign-in and the second
succeeded.

Not run live: the refusals other than the hidden tool and the missing credential.
They are covered offline only. The Secure Enclave signer was not involved.

## Checks shown to be tested

Each change was made on its own, the `gateway` suite run, and the file restored.
The final list has 52 changes and all are caught. Of the first 39, two were missed
on the first pass, because the stand-in replies used were also invalid in a second
way; those two tests were corrected. Verification then found eight more that no
test caught; tests were added, and the changes that came with the fixes joined the
list.

In `gateway.py`: the audience parameter ignored; the scope parameter ignored.

In `mcp_gateway.py`:

- *Caller's credentials.* `Origin` header allowed; token audience not the MCP
  gateway's; scope not the MCP scope; client and scope check skipped; proof not
  bound to the token's key; proof accepted over plain HTTP; proof not recorded
  against replay; proof verifier built for the LLM gateway's address; starting
  without DPoP; the metadata address or the scope missing from challenges; the
  metadata claiming bearer tokens work; `no-store` missing from refusals.
- *Request.* Missing revision header allowed; revision header not compared with
  the body; older revision accepted; `Mcp-Method` not compared; `Mcp-Name` not
  compared; `Mcp-Name` allowed to be missing; `Mcp-Name` allowed on other methods;
  capabilities allowed to be absent; notifications and extra fields allowed;
  request size unlimited; a query string allowed; a compressed request allowed;
  values that cannot be written back out accepted.
- *Rules.* Per-tool rule skipped on calls; the unknown-tool reply naming the tool;
  tool list not filtered; tool list marked public; other methods forwarded; policy
  tool names unchecked.
- *Tool server.* Caller's capabilities forwarded; caller's whole request
  forwarded; a call's extra fields forwarded; revision header not sent upstream;
  incomplete results accepted; reply id not checked; reply version not checked;
  reply type not checked; a compressed reply accepted; reply size unlimited, and
  limited only per piece; duplicate tool names accepted; result items that are
  not objects accepted; the tool server's extra fields passed through; a caller's
  disconnect ignored.
- *Audit log.* Subject written unchecked; a refused tool's name written; the
  subject written before the client and scope are accepted.

## Verification

An independent verifier agent tried to make the gateway forward, reveal or log
something it should not, and could not. It tried duplicate and malformed headers,
duplicate JSON fields, look-alike tool names, tokens, proofs and nonces from the
other gateway, and hostile tool-server replies. It did find the following, all
acted on:

1. *Three inputs crashed the handler instead of being refused.* An out-of-range
   number or half of a character pair, in a tool-server reply or in a caller's
   request id or arguments, is read by Python but cannot be written back out. The
   result was an unhandled error, in one case after the log had already recorded
   the call as made. Both are now refused as malformed, 400 for a request and 502
   for a reply, before anything else happens.
2. *Eight checks could be removed with every test still passing,* and the offline
   test of the probe did not show that each of the probe's own checks could fail.
   Tests added for all of them.
3. *The metadata said bearer tokens could be sent in a header.* The gateway
   refuses them. The field is now an empty list, which RFC 9728 defines as "none".
4. *The 401 challenge did not name the scope,* which the MCP specification
   recommends. It now does.
5. *Tool-server text is relayed as received,* and nothing said so. Duplicate tool
   names and result items that are not objects are now refused. The README's
   limits and the concept page now say that descriptions, schemas and results,
   including error text, reach the caller unedited, and that the concept page's
   earlier claim about hiding the software behind the gateway applied to
   discovery only.
6. *A filtered page can be empty and still point to a next page,* which tells a
   caller hidden tools exist. Documented as a limit and filed in the backlog.
7. *`Mcp-Param` headers are not forwarded.* Documented as a limit.

Left as it is, and why: one proof can be presented several times while the
request keeps failing the header check, because the proof is recorded only once
the request is well formed. The LLM gateway behaves the same way, nothing is
forwarded, and the proof lasts 30 seconds.

Not verified by anyone: that the three Mermaid diagrams render on GitHub. An
expired nonce, as opposed to a forged one, is tested only in the shared verifier's
own suite, not in this one.
