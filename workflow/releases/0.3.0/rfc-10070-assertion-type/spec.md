# Spec: rfc-10070-assertion-type

Release: 0.3.0 · Roadmap line: rfc-10070-assertion-type ·
Capability: Sign-in and token issuance
Status: **approved** (2026-11-26)

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

- [x] An assertion typed `client-authentication+jwt` is accepted, and both lab
      clients send that type.
- [x] An assertion typed `JWT`, and one with no type, are accepted.
- [x] An assertion typed `at+jwt` or `dpop+jwt`, otherwise valid, is rejected with
      `invalid_client` and consumes nothing: the same subject token can still be
      exchanged afterwards.
- [x] No source file or current document cites the draft where the RFC applies.
- [x] All five suites, the tools tests, lint and the documentation check pass, and
      the gateway and broker suites are rerun because they import this module.
- [x] A live lab run from a fresh clone ends with the broker exiting 0 and printing
      `MOCK_OK`, and the DPoP probe succeeds.

**Open questions.** None. Decided at approval on 2026-11-26: the server rejects
assertions that declare a different token type, and the task closes with a live run.

## Outcome — 2026-11-26

All acceptance criteria met.

**What was built.** The authorization server accepts a client assertion whose type
is `client-authentication+jwt`, `JWT`, or absent, and rejects any other declared
type with `invalid_client`. Both lab clients set the recommended type. Documents
cite RFC 10070.

**Proof.**

- Authorization server suite: 65 passed, up from 55, with tests for six accepted
  forms, six rejected ones and nine values that are not text. The gateway suite: 94
  passed, with a new test that decodes what the lab client actually sends. Both new
  tests were shown to fail when the code they guard is removed.
- Live lab from a fresh clone, with the owner signing in: the broker with the
  software key exited 0 with `MOCK_OK`, the DPoP probe succeeded, and the broker
  with the Secure Enclave signer returned `MOCK_OK`. The authorization server logged
  three successful exchanges and no service log held a traceback.
- The live run came before the change described in the first row below. The lab's
  clients send the exact recommended type, which is accepted before and after that
  change, so the run was not repeated.

**Verifier findings and what was done.** The verifier could not break the security
claim: the check runs after the signature is verified, uses up nothing when it
refuses, answers exactly like every other client refusal, and touches only client
assertions.

| Finding | Disposition |
|---|---|
| Types written in another case or with a leading `application/`, such as `jwt` or `application/jwt`, were refused. RFC 7515 treats the type as a media type name where neither matters, and RFC 10070 advises against refusing generic assertions | Fixed: the type is now compared that way. Decided on the owner's behalf, as a detail inside the approved rule |
| Nothing offline checked the type the lab clients send; removing it would have passed every suite | Fixed for `lab_invoke.py`, which the probe and the broker use. `lab_exchange.py` uses the same constant on the matching line and is covered by reading only; its probe needs an authorization server in Bearer mode and was not run |
| The new test did not show that a refused assertion's identifier stays unused | Fixed: the same identifier and subject token are accepted once the type is right, and refused on a third use |
| The Component 3 design note was reworded to say the earlier audience change followed the RFC, when it followed the draft | Corrected to say the draft was later published as the RFC |
| The glossary read as if the RFC requires the type | Corrected: it is a recommendation |
| A type written as JSON `null` is treated as absent | Accepted. The header is signed by the registered client, and `null` declares no other type |
| The 0.1.0 changelog entry still says "now in draft" | Left as written; it is the record of a past release. The 0.3.0 entry will describe this change |

**Still stricter than the RFC requires, by choice.** The audience must be the issuer
as plain text; the one-element list form is refused. The RFC permits this.
