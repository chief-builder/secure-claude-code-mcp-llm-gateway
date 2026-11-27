# Plan: mcp-tokens

Consumes: [spec.md](spec.md)
Status: draft — needs the owner's approval, because it changes token issuance

**Design summary.** A target is a small record: the audience written into the
token, the scope it requires, how a request names it (`audience` or `resource`),
and whether it needs DPoP. There are two, defined as constants next to the existing
ones. `Exchange.issue` resolves the request to one target before looking at the
subject token, and everything after that uses the target's audience and scope where
it used the fixed constants. The replay key for the subject token gains the
target's audience, which is what turns "once" into "once per target". The policy
loader accepts one more optional key and validates it at startup.

Alternatives considered: a second token endpoint for MCP (duplicates the checks
that must stay identical); putting both audiences in one token (removes the
separation this task exists to create); letting the policy file define targets
freely (more than two fixed gateways need, and a misconfiguration could mint tokens
for arbitrary audiences).

**Units.**

| # | Unit | Check | Status |
|---|------|-------|--------|
| 1 | Constants and the policy's optional `mcp_subjects`, validated at startup | Old policy files load unchanged; malformed lists refused; tests | todo |
| 2 | Target resolution in the token request: `audience` or `resource`, scope matched to target, MCP only with DPoP | Every refusal in the spec tested, each shown to use up nothing | todo |
| 3 | Issue the MCP token; replay key per target | One ID token gives one of each, in either order; third use refused | todo |
| 4 | Gateway test: the LLM gateway refuses an MCP token | 401 in the gateway suite | todo |
| 5 | `lab_invoke.py`: exchange for either target; optional probe step | Offline test decodes what it sends; suites pass | todo |
| 6 | README and glossary | Documentation check passes | todo |
| 7 | Live lab run from a fresh clone, with a policy that lists the subject | Broker and probe as before; MCP step succeeds | todo |
| 8 | Verifier agent, then land | Acceptance criteria met | todo |

**Risks.** The existing tests post requests without `resource`; a mistake in target
resolution would show as widespread failures, which is the early signal. The replay
key change must not let an old-format record and a new-format record both be
accepted for the same token during an upgrade: records live at most a few minutes,
and the lab restarts with fresh state, but the verifier should look at it.
