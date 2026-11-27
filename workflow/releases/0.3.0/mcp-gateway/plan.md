# Plan: mcp-gateway

Consumes: [spec.md](spec.md)
Status: draft — needs the owner's approval, because it changes token validation

**Design summary.** A new module, `components/gateway/mcp_gateway.py`, holds the
MCP gateway. It imports the LLM gateway's existing security functions and does not
copy them. Two of those functions gain a parameter each; nothing else in accepted
code changes.

**The change to accepted code, in full.** In `components/gateway/gateway.py`:

- `validate_access_token(token, trust, scheme)` gains `audience=TARGET`, and the
  one comparison `claims.get("aud") != TARGET` becomes `!= audience`.
- `enforce_policy(claims, scheme)` gains `scope=SCOPE`, and the comparison and the
  scope named in the challenge use it.

The defaults are today's values, so the LLM gateway's calls and behavior do not
change and its 96 tests must pass unmodified. `components/oauth-as` is not touched.

**What is reused unchanged.** `Trust` (fetching and pinning the authorization
server's keys), `access_credential` (one credential only), `Verifier` from
`dpop.py` constructed for `https://127.0.0.1:8083/mcp`, `record_proof` with
`ReplayStore` using its own database file, `strict_json`, and `Failure`.

**What is new, all in `mcp_gateway.py`.**

- `load_tool_policy(path)`: strict parsing of the policy file; anything unexpected
  stops startup.
- `read_request(request)`: body limit, strict JSON, one JSON-RPC request, and the
  header-against-body comparison, including the specification's encoded form of
  `Mcp-Name`.
- `upstream_request(method, params)`: builds the request for the tool server from
  named fields only.
- `checked_result(method, reply, allowed)`: validates the tool server's reply and
  filters a tool list.
- `create_app(...)` with the request handler, which runs the spec's eight steps in
  order, and the metadata route.
- `main()`: the same options as the LLM gateway plus `--tool-policy`; the upstream
  credential comes from `MCP_GATEWAY_UPSTREAM_TOKEN`.

**Details the spec left to the plan.**

- Refusals before the request is read (401, 403, 431) have no body. They carry the
  LLM gateway's challenge text for that kind of refusal, with the metadata address
  added.
- Header and method refusals carry a JSON-RPC error with the request's `id`.
- A request `id` must be text or a whole number.
- The replay database is a separate file in the replay folder; a proof for the LLM
  gateway already fails here on its address.
- Tests reach the SDK-built mock in-process, so `components/mock-mcp` is added to
  the importable folders in `pyproject.toml`. Malformed tool-server replies come
  from small hand-made fakes.
- The probe gains `--mcp-gateway-ca`; with it, the `--mcp` step goes on to call
  the gateway.

**Units.** Each ends in a passing check and its own commit.

| # | Unit | Check | Status |
|---|------|-------|--------|
| 1 | The two parameters in `gateway.py` | LLM gateway suite passes unmodified; new tests show a wrong audience and a wrong scope are refused when passed in | todo |
| 2 | Policy loading, startup rules, metadata route | Tests for good and malformed policies, missing DPoP options, the metadata document | todo |
| 3 | Steps 1 to 5 and 7: credential, token, proof, client and scope, replay | Tests for every refusal in the spec's third criterion | todo |
| 4 | Step 6 and `server/discover`: request parsing and header checks | Tests for the fourth and fifth criteria | todo |
| 5 | `tools/list` and `tools/call`: rules, forwarding, reply checks, disconnect | Tests against the SDK mock and the fakes | todo |
| 6 | Audit log, and the convention change in `workflow/PROJECT.md` | Tests read the log lines | todo |
| 7 | The probe | Offline test of its request building | todo |
| 8 | Each security check broken in turn | A test fails for each; list in the outcome | todo |
| 9 | README, diagram page, glossary, root README, limitations | Documentation check; commands pasted into an interactive shell | todo |
| 10 | Live lab run with the owner signing in | Probe succeeds through the running services | todo |
| 11 | Verifier agent, then pull request | Acceptance criteria met | todo |

**Risks.**

- Making `mock-mcp` importable adds a fifth folder to the import path; the
  existing test that guards against module-name clashes must cover it.
- The live run needs a fourth certificate and a policy that lists the synthetic
  user under `mcp_subjects`; the quickstart does not create either, so the run's
  commands are recorded in the task folder, not the quickstart.
- The Secure Enclave signer has a fixed list of addresses it will sign for and
  does not include the MCP gateway. The probe uses the software key, so this task
  is unaffected; the broker task will have to decide.
