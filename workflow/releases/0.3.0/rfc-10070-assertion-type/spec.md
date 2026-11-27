# Spec: rfc-10070-assertion-type

Release: 0.3.0 · Roadmap line: rfc-10070-assertion-type ·
Capability: Sign-in and token issuance
Status: draft

Intent and spec on one page; the change is small.

**Problem.** When the broker asks the authorization server for a token, it proves
which application it is with a signed statement called a client assertion. RFC 10070
(November 2026) updates the rules for these. The lab already follows its main rule:
the assertion names the authorization server's issuer as its only audience. It does
not yet follow the second: the RFC says a client assertion "SHOULD be explicitly
typed by using the `typ` header parameter value `client-authentication+jwt`". The
lab's assertions carry the generic type `JWT`, which the signing library adds by
default, and the server does not look at the type at all. One code comment and one
design note still cite the draft, not the RFC.

**Why now.** It is the first task of 0.3.0 because the next one, tokens for MCP,
changes the same module, and a second kind of token makes it more useful to tell
kinds of signed statement apart.

**Behavior after this change.**

- The two lab clients that build client assertions, `lab_exchange.py` and
  `lab_invoke.py` (which the broker uses), set `typ` to
  `client-authentication+jwt`.
- The authorization server accepts a client assertion whose type is
  `client-authentication+jwt`, the generic `JWT`, or absent. The RFC says it is
  "NOT RECOMMENDED for servers to reject JWTs that do not have explicit types",
  so older clients keep working.
- The authorization server rejects a client assertion that declares itself to be
  some other kind of token, such as an access token (`at+jwt`) or a DPoP proof
  (`dpop+jwt`), with `invalid_client`. Today it would ignore the type.
- Nothing else about token exchange changes: the audience rule, replay protection,
  lifetimes and the issued token are as before.

**Scope.** `components/oauth-as/exchange.py` (one check, one comment),
`components/oauth-as/lab_exchange.py`, `components/gateway/lab_invoke.py`, the
authorization server's tests, and the documents that describe the assertion.

**Non-goals.**

- Requiring the new type. The RFC advises against it.
- Changing how the audience is compared. The server already requires the issuer as
  a plain string, which is stricter than the RFC needs.
- Type checks on other tokens. The gateway already requires `at+jwt` on access
  tokens and `dpop+jwt` on proofs.

**Acceptance criteria.**

- [ ] An assertion typed `client-authentication+jwt` is accepted, and both lab
      clients send that type.
- [ ] An assertion typed `JWT`, and one with no type, are accepted.
- [ ] An assertion typed `at+jwt` or `dpop+jwt`, otherwise valid, is rejected with
      `invalid_client` and consumes nothing: the same subject token can still be
      exchanged afterwards.
- [ ] No source file or current document cites the draft where the RFC applies.
- [ ] All five suites, the tools tests, lint and the documentation check pass, and
      the gateway and broker suites are rerun because they import this module.
- [ ] A live lab run from a fresh clone ends with the broker exiting 0 and printing
      `MOCK_OK`, and the DPoP probe succeeds.

**Open questions.**

1. Should the server reject assertions that declare a different token type, as
   described above, or keep ignoring the type? Recommended: reject. A type the
   server never reads protects nothing.
