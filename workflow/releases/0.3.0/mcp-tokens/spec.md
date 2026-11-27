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

- [ ] A request with `resource` and `scope=mcp:invoke`, from a subject listed in
      `mcp_subjects`, with DPoP, returns a token whose audience is
      `https://127.0.0.1:8083/mcp`, whose scope is `mcp:invoke`, and whose `cnf.jkt`
      matches the proof key.
- [ ] The same ID token yields one model token and one MCP token, in either order;
      a second request for either target is refused as a replay.
- [ ] Refused, each leaving the sign-in token unused: both `audience` and `resource`; neither; an
      unknown `resource`; `mcp:invoke` with the model audience; `llm:invoke` with
      the MCP resource; a subject not in `mcp_subjects`; a policy with no
      `mcp_subjects`; and any MCP request in Bearer mode.
- [ ] A policy file written before this change loads and behaves as before. A
      policy whose `mcp_subjects` names a subject that is not in `subjects`, or is
      not a list of text, is refused at startup.
- [ ] The LLM gateway refuses an MCP token with 401, in a gateway test.
- [ ] All existing tests pass unchanged, apart from additions.
- [ ] Live lab run from a fresh clone: the broker and the DPoP probe succeed as
      before, and the probe's new step obtains an MCP token from the same sign-in
      and sees the LLM gateway refuse it.

**Open questions.** None. Decided at approval on 2026-11-26: a sign-in token may be
exchanged once per target; MCP tokens need an explicit `mcp_subjects` list in the
policy; and the three details (DPoP only, the gateway address as audience, the scope
name `mcp:invoke`) stand as written.
