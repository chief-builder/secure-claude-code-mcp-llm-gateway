# Spec: mcp-tokens

Consumes: [intent.md](intent.md)
Status: **approved** (2026-11-26)

**Behavior.**

*Asking for a token.* A token request names its target in one of two ways, never
both:

- `audience=urn:lab:llm-gateway` with `scope=llm:invoke`, as today, for a model
  token.
- `resource=https://127.0.0.1:8083/mcp` with `scope=mcp:invoke`, for an MCP token.
  The MCP specification identifies a server by its address and has the client name
  it in the `resource` parameter; `https://127.0.0.1:8083/mcp` is where the MCP
  gateway will listen.

A request with both, neither, an unknown target, or a scope that does not belong to
its target is refused, as an unknown target or scope is today.

*What an MCP token contains.* The same claims as a model token, with two
differences: its audience is `https://127.0.0.1:8083/mcp` and its scope is
`mcp:invoke`. It carries the same mapped subject and client, lasts at most five
minutes, and is bound to the caller's DPoP key.

*MCP tokens need DPoP.* The authorization server issues MCP tokens only when it is
running with DPoP. In Bearer mode a request for one is refused as an unknown target.
An MCP token that could be replayed would defeat the purpose of the MCP gateway.

*Who may have one.* The exchange policy gains an optional list, `mcp_subjects`,
naming which of its subjects may receive MCP tokens. A policy without the list
issues none, so existing policies behave exactly as before. A subject in the policy
but not in the list is refused an MCP token and can still get a model token.

*One sign-in, two tokens.* Today an ID token can be exchanged once. After this
change it can be exchanged once per target: once for a model token and once for an
MCP token. A third exchange, or a second for the same target, is refused as a
replay.

*The LLM gateway is unchanged* and already refuses any token whose audience or scope
is not its own. A test will show it refuses an MCP token.

*The lab client.* `lab_invoke.py`'s exchange function can ask for either kind. Its
probe gains an optional step, off by default, that obtains an MCP token from the
same sign-in, checks its contents, and confirms the LLM gateway refuses it.

**Scope.** `components/oauth-as/foundation.py` (two constants),
`components/oauth-as/exchange.py`, `components/gateway/lab_invoke.py`, their tests,
a gateway test, the authorization server README and the glossary.

**Non-goals.**

- No MCP gateway, mock server or broker change; those are the next three tasks.
- No change to the quickstart or to the policy it writes. MCP is not usable end to
  end yet, so the documented lab keeps issuing model tokens only.
- No per-tool permissions in the token. Per-tool rules live at the MCP gateway.
- No refresh tokens and no change to lifetimes.
- No change to the Secure Enclave signer's list of addresses; it does not yet need
  to sign for the MCP gateway.

**Other requirements.** Security: every new refusal must look exactly like the
existing refusals of its kind, and must leave the sign-in token unused. (Corrected
during the build: the client assertion is used up by every authenticated request,
refused or not, as it is today. The first wording, "use up nothing", was wrong.)

**Acceptance criteria.**

- [x] A request with `resource` and `scope=mcp:invoke`, from a subject listed in
      `mcp_subjects`, with DPoP, returns a token whose audience is
      `https://127.0.0.1:8083/mcp`, whose scope is `mcp:invoke`, and whose `cnf.jkt`
      matches the proof key.
- [x] The same ID token yields one model token and one MCP token, in either order;
      a second request for either target is refused as a replay.
- [x] Refused, each leaving the sign-in token unused: both `audience` and `resource`; neither; an
      unknown `resource`; `mcp:invoke` with the model audience; `llm:invoke` with
      the MCP resource; a subject not in `mcp_subjects`; a policy with no
      `mcp_subjects`; and any MCP request in Bearer mode.
- [x] A policy file written before this change loads and behaves as before. A
      policy whose `mcp_subjects` names a subject that is not in `subjects`, or is
      not a list of text, is refused at startup.
- [x] The LLM gateway refuses an MCP token with 401, in a gateway test.
- [x] All existing tests pass unchanged, apart from additions.
- [x] Live lab run from a fresh clone: the broker and the DPoP probe succeed as
      before, and the probe's new step obtains an MCP token from the same sign-in
      and sees the LLM gateway refuse it.

**Open questions.** None. Decided at approval on 2026-11-26: a sign-in token may be
exchanged once per target; MCP tokens need an explicit `mcp_subjects` list in the
policy; and the three details (DPoP only, the gateway address as audience, the scope
name `mcp:invoke`) stand as written.

## Outcome — 2026-11-26

All acceptance criteria met.

**What was built.** The authorization server issues a second kind of token, for the
MCP gateway: audience `https://127.0.0.1:8083/mcp`, scope `mcp:invoke`, requested
with the `resource` parameter. It is issued only with DPoP and only to subjects in
the policy's optional `mcp_subjects` list. A sign-in token is accepted once per
target. The lab client can request either kind, and its probe has an optional
`--mcp` step.

**Proof.**

- Authorization server suite: 88 passed, up from 66. Gateway suite: 96 passed, up
  from 94. Every test that existed before passes unchanged, and the verifier ran
  `main`'s own copy of the exchange tests against the new code: 35 passed.
- Six mutations of the new server logic, one at a time, were each caught by the new
  tests: ignoring the target in the replay record, not checking the subject list,
  allowing MCP without DPoP, allowing `audience` with `resource`, writing the model
  audience into an MCP token, and not matching the scope to the target.
- Live lab on 2026-11-26, from a fresh clone at commit `2c8b2e0`, with a policy
  listing the synthetic user and the owner signing in:
  - `lab_invoke.py --dpop --mcp` printed `component_05_succeeded` and
    `mcp_token_succeeded`: one sign-in produced a model token and an MCP token, and
    the model gateway refused the MCP token.
  - The broker with the software key exited 0 with `MOCK_OK`; the broker with the
    Secure Enclave signer returned `MOCK_OK`.
  - The authorization server logged four successful exchanges. The gateway logged
    one `authentication_failed`, the refused MCP token, and four successful
    invocations. No service log held a traceback.
- The changes made after that run, listed below, are to the probe, a test and
  documents. They were verified by the suites, not by another live run.

**Verifier findings and what was done.** The verifier could not break token
issuance: every impossible audience and scope combination was refused, the
once-per-target rule held in every order and with ten concurrent requests, and an
unlisted subject is indistinguishable from an unknown one.

| Finding | Disposition |
|---|---|
| The live run had no record in the branch | Recorded above |
| The glossary and the request walkthrough still said an ID token is used once | Corrected in both |
| The probe checked the token's audience by containment, so a token naming both gateways would have passed its check | Fixed: the probe requires the audience alone |
| The probe could not tell a refusal for audience from a refusal for expiry | Fixed: the probe first checks the token has at least 30 seconds left |
| The gateway test covered tokens without a key binding only, a shape the server never issues for MCP | Fixed: a second test uses key-bound tokens in DPoP mode |
| A request carrying `resource` used to be refused before the client was authenticated; it is now authenticated first, uses up the client assertion, and is refused as an unknown target | Intended. It is the one case where a request refused before is refused differently now |
| Stricter than the RFCs require: a repeated `resource`, and `audience` together with `resource`, are refused | Accepted. Both are restrictions, not violations |

**Added at the owner's request after the outcome was written.** A concepts page,
`docs/concepts/tokens-and-modes.md`, with diagrams of the two modes and the two
kinds of token, and two workflow amendments: tasks that change a concept add a
diagram, and tasks that change a security check show the check is really tested.

**Decided on the owner's behalf.** An unlisted subject is refused exactly as an
unknown subject is, so a caller cannot learn who is known. The model target keeps
its replay record format unchanged, so a record written before an update still
blocks a replay after it.
