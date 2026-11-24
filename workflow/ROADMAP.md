# Roadmap

The standing document work is drawn from. Intents for new tasks start here; nothing
enters implementation that isn't traceable to a line on this page. Kept current, not
historical — shipped work moves to the root `CHANGELOG.md` when a release is cut.
Every task line names the capability in `workflow/PRODUCT.md` it serves.

## Direction

Make the existing lab easy to understand and reproduce for someone who was not part
of building it, then extend the same identity and token model to MCP. It will not
become a production gateway, and it will not handle real identities or data.

## Current release: next

Target: not set · Theme: a reference others can follow

| Task | Capability | Status | Artifacts |
|------|------------|--------|-----------|
| improve-documentation | Documentation | in-progress | [workflow/releases/next/improve-documentation/](releases/next/improve-documentation/) |

## Next release (tentative)

- Shape the MCP gateway capability (MCP gateway)

## Backlog

Unscheduled work, one line each with enough context to write an intent later. Anything
discovered mid-task (bugs deferred, debt spotted, ideas) gets filed here instead of
being lost in a conversation. Each line ends with the release it was filed in, so
release planning can tell how long it has waited. Reviewed when planning each release;
pruned without guilt.

- Verify the Bedrock adapter's matched stop sequence against live Bedrock; today only offline tests cover it (Gateway and inference, filed: next)
- Adopt the explicit client-assertion `typ` from draft-ietf-oauth-rfc7523bis once the exact value is confirmed in the draft text (Sign-in and token issuance, filed: next)
- Check reachability of the lab listeners from a second device; pending since the original gates (Gateway and inference, filed: next)
- Call the gateway with a debugger-recovered token and software key, to complete the Component 6 extraction evidence (Sender-constrained access, filed: next)
- Observe the operating system refusing to sign during screen lock, independently of the helper's own lock check (Sender-constrained access, filed: next)
- Reconcile the final billed cost of the live Bedrock run and confirm the budget-alert email (Gateway and inference, filed: next)
- Token refresh so the broker can serve an interactive Claude Code session longer than five minutes (Local credential broker, filed: next)
- Check Markdown links and anchors in CI, so a renamed heading cannot silently break a link (Documentation, filed: next)
- Replace the source-line links in the two code walkthroughs, which have drifted from the code, with links that do not go stale (Documentation, filed: next)
- Reword the `component_03_succeeded` message that `lab_exchange.py init-client` prints during setup, where it reads like a test result (Sign-in and token issuance, filed: next)
- Sign the Secure Enclave helper and decide how it authorizes its caller (Sender-constrained access, filed: next)

## Debt register

Known structural debt, each with the pain it causes. Feeds the release-planning
conversation alongside features.

- Components import each other through `sys.path.insert`, so a change in `oauth-as` can break `gateway` and `broker` without any import error at edit time (filed: next)
- `manual_claude_check.py` imports fixtures from test modules, tying a runnable script to test internals (filed: next)
- Strict JSON parsing is duplicated in `oauth-lab/oidc.py` and `oauth-as/foundation.py`; a fix to one can miss the other (filed: next)
- The gateway and token endpoints are hard-coded in `gateway.py`, `lab_invoke.py` and `SecureSigner.swift`; changing a port means three edits in two languages (filed: next)
- The Bedrock request is validated twice, once in the gateway and once in the adapter transport (filed: next)
- The mock's tests use a Starlette test client that now emits a deprecation warning (filed: next)
- No lint or type check is configured (filed: next)
