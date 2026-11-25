# Roadmap

The standing document work is drawn from. Intents for new tasks start here; nothing
enters implementation that isn't traceable to a line on this page. Kept current, not
historical — shipped work moves to the root `CHANGELOG.md` when a release is cut.
Every task line names the capability in `workflow/PRODUCT.md` it serves.

## Direction

Make the existing lab easy to understand and reproduce for someone who was not part
of building it, close the gaps in its evidence, and then extend the same identity
and token model in two directions: to MCP, and to a deployment where the identity
services run on AWS instead of the developer's Mac. It will not become a production
gateway, and it will not handle real identities or data.

## Current release: 0.2.0

Target: not set · Theme: guardrails and evidence, and the next two steps thought through

| Task | Capability | Status | Artifacts |
|------|------------|--------|-----------|
| ci-docs-and-lint-checks | Documentation | shipped | [workflow/releases/0.2.0/ci-docs-and-lint-checks/](releases/0.2.0/ci-docs-and-lint-checks/) |
| package-shared-code | Gateway and inference | in-progress | [workflow/releases/0.2.0/package-shared-code/](releases/0.2.0/package-shared-code/) |
| close-pending-checks | Sender-constrained access | backlog | — |
| shape-mcp-gateway | MCP gateway | backlog | — |
| shape-aws-hosted-identity | Hosted identity services | backlog | — |

What each task is:

- **ci-docs-and-lint-checks** — check Markdown links and anchors in CI, reject `#`
  comment lines inside shell blocks, add a linter, and replace the source-line links
  in the two code walkthroughs, which have drifted from the code.
- **package-shared-code** — replace the `sys.path.insert` imports between
  `oauth-as`, `gateway` and `broker` with a proper shared package, so a change in
  one cannot silently break another. Behavior-preserving.
- **close-pending-checks** — the checks left open at the original gates that need
  the owner's hardware or accounts and no AWS deployment: reachability from a second
  device, calling the gateway with a debugger-recovered token and software key,
  observing the operating system refuse to sign during screen lock, and reconciling
  the billed cost of the live Bedrock run with its budget alert.
- **shape-mcp-gateway** — a design conversation, no code: who it is for, the
  smallest useful version, what it reuses.
- **shape-aws-hosted-identity** — a design conversation, no code: what it means to
  run Keycloak and the authorization server on AWS instead of the Mac, including
  where the signing keys live, real host names in place of pinned loopback
  addresses, and what it costs.

## Next release (tentative)

- Build the first slice of the MCP gateway, as shaped (MCP gateway)
- Build the AWS-hosted identity services, as shaped (Hosted identity services)
- Verify the Bedrock adapter's matched stop sequence against live Bedrock, in the same AWS session (Gateway and inference)
- Adopt the explicit client-assertion `typ` from draft-ietf-oauth-rfc7523bis (Sign-in and token issuance)

## Backlog

Unscheduled work, one line each with enough context to write an intent later. Anything
discovered mid-task (bugs deferred, debt spotted, ideas) gets filed here instead of
being lost in a conversation. Each line ends with the release it was filed in, so
release planning can tell how long it has waited. Reviewed when planning each release;
pruned without guilt.

- Verify the Bedrock adapter's matched stop sequence against live Bedrock; today only offline tests cover it (Gateway and inference, filed: 0.1.0)
- Adopt the explicit client-assertion `typ` from draft-ietf-oauth-rfc7523bis once the exact value is confirmed in the draft text (Sign-in and token issuance, filed: 0.1.0)
- Token refresh so the broker can serve an interactive Claude Code session longer than five minutes (Local credential broker, filed: 0.1.0)
- Reword the `component_03_succeeded` message that `lab_exchange.py init-client` prints during setup, where it reads like a test result (Sign-in and token issuance, filed: 0.1.0)
- Add a type checker; the linter added in 0.2.0 covers names and imports only (Gateway and inference, filed: 0.2.0)
- Sign the Secure Enclave helper and decide how it authorizes its caller (Sender-constrained access, filed: 0.1.0)

## Debt register

Known structural debt, each with the pain it causes. Feeds the release-planning
conversation alongside features.

- Strict JSON parsing is duplicated in `oauth-lab/oidc.py` and `oauth-as/foundation.py`; a fix to one can miss the other (filed: 0.1.0)
- The gateway and token endpoints are hard-coded in `gateway.py`, `lab_invoke.py` and `SecureSigner.swift`; changing a port means three edits in two languages (filed: 0.1.0)
- The Bedrock request is validated twice, once in the gateway and once in the adapter transport (filed: 0.1.0)
- The mock's tests use a Starlette test client that now emits a deprecation warning (filed: 0.1.0)
