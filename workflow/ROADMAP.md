# Roadmap

The standing document work is drawn from. Intents for new tasks start here; nothing
enters implementation that isn't traceable to a line on this page. Kept current, not
historical — shipped work moves to the root `CHANGELOG.md` when a release is cut.
Every task line names the capability in `workflow/PRODUCT.md` it serves.

## Direction

Extend the lab's identity and token model in two directions, in this order: to MCP
tool servers, first in the local lab; then to a deployment where the identity
services run on AWS instead of the developer's Mac. Alongside, keep the lab easy to
reproduce for someone who was not part of building it, and close the gaps left in
its evidence. It will not become a production
gateway, and it will not handle real identities or data.

## Current release: 0.3.0

Target: not set · Theme: the MCP gateway's first stage, in the local lab

| Task | Capability | Status | Artifacts |
|------|------------|--------|-----------|
| rfc-10070-assertion-type | Sign-in and token issuance | shipped | [workflow/releases/0.3.0/rfc-10070-assertion-type/](releases/0.3.0/rfc-10070-assertion-type/) |
| mcp-tokens | MCP gateway | in-progress | [workflow/releases/0.3.0/mcp-tokens/](releases/0.3.0/mcp-tokens/) |
| mock-mcp-server | MCP gateway | backlog | — |
| mcp-gateway | MCP gateway | backlog | — |
| broker-mcp-endpoint | MCP gateway | backlog | — |

What each task is, in build order. The design they follow is
[decision 0003](decisions/0003-mcp-through-the-broker-with-its-own-tokens.md).

- **rfc-10070-assertion-type** — Set the client assertion's type as RFC 10070 recommends. RFC 10070 (November 2026) is the published update to RFC 7523. Its audience rule, issuer as the sole value, is already implemented. What remains: the two lab clients set the header `typ` to `client-authentication+jwt`; the server keeps accepting assertions without it, as the RFC advises; and the code comment that cites the draft cites the RFC instead
- **mcp-tokens** — Issue tokens for MCP: a second audience and scope in the authorization server's token exchange, so model tokens and MCP tokens cannot stand in for each other. The audience is the MCP gateway's endpoint address, which the broker names in its request, as the MCP specification expects. A change to an accepted security module
- **mock-mcp-server** — A mock MCP server for revision 2026-07-28 of the specification, with at least two harmless tools so a rule that allows one and refuses the other can be shown. It answers `server/discover`, `tools/list` and `tools/call`, checks that the request headers match the body, and checks `Origin`
- **mcp-gateway** — The MCP gateway: verify the MCP token, the DPoP proof, the nonce and replay; check the MCP request headers against the body; answer `server/discover` itself and allow only `tools/list` and `tools/call`; apply per-tool rules by leaving disallowed tools out of the list, marking the list private so it cannot be cached across users, and refusing calls to them as unknown tools; forward to the mock with the gateway's own credential and never the user's token; publish the metadata the specification requires; audit the user and tool name, never the arguments. Proven by a test client
- **broker-mcp-endpoint** — The broker as Claude Code's local MCP endpoint: a second loopback listener protected by the session secret, speaking revision 2026-07-28 only (a probe showed the installed Claude Code speaks it), tools and MCP enabled in the launched CLI, and Claude Code shown listing only the tools the user may call

## Next release (tentative)

- One AWS host running Keycloak, the authorization server and the gateway, created from a template and reached by tunnels (Hosted identity services)
- A scripted mock model that makes Claude Code really call an MCP tool, the MCP gateway's second stage (MCP gateway)
- The three checks slipped from 0.2.0 because the owner will do them later: reachability from a second device, a gateway call with a debugger-recovered token and software key, and the operating system refusing to sign during screen lock (Sender-constrained access)
- Verify the Bedrock adapter's matched stop sequence against live Bedrock, in the same AWS session as the host (Gateway and inference)

## Backlog

Unscheduled work, one line each with enough context to write an intent later. Anything
discovered mid-task (bugs deferred, debt spotted, ideas) gets filed here instead of
being lost in a conversation. Each line ends with the release it was filed in, so
release planning can tell how long it has waited. Reviewed when planning each release;
pruned without guilt.

- Verify the Bedrock adapter's matched stop sequence against live Bedrock; today only offline tests cover it (Gateway and inference, filed: 0.1.0)
- Token refresh so the broker can serve an interactive Claude Code session longer than five minutes (Local credential broker, filed: 0.1.0)
- Reword the `component_03_succeeded` message that `lab_exchange.py init-client` prints during setup, where it reads like a test result (Sign-in and token issuance, filed: 0.1.0)
- Add a type checker; the linter added in 0.2.0 covers names and imports only (Gateway and inference, filed: 0.2.0)
- One AWS host running Keycloak, the authorization server and the gateway on its loopback, created from a template, up only for a session, removed with one command, reached from the Mac by tunnels to the same ports; no component code change. To settle in its spec: template tool, tunnel method (SSH or Systems Manager), instance size, separating the services by operating-system user, keeping the instance role away from the identity processes, mock or Bedrock backend, and the cost ceiling (Hosted identity services, filed: 0.2.0)
- Two synthetic users on two Macs against one deployment: a second user in the realm and the exchange policy, a client key per Mac registered with the authorization server (the server accepts several; the setup command creates one), tunnel access for the second person, and the lab certificate authorities on the second Mac. Prove it with both signed in at once and each token carrying its own subject (Hosted identity services, filed: 0.2.0)
- Make the issuer, Keycloak, gateway and callback addresses configuration instead of constants, in Python and in the Swift signer's endpoint list; a change to accepted security modules, needed before the services can sit on separate hosts (Hosted identity services, filed: 0.2.0)
- Split identity (Keycloak and the authorization server) and the gateway onto separate hosts, so the signing key and the Bedrock role no longer share a machine (Hosted identity services, filed: 0.2.0)
- Turn the components into real packages so a service can be deployed without the whole repository; the units are the identity host and the gateway host (Hosted identity services, filed: 0.2.0)
- A small exchange service next to the authorization server that holds the exchange client's key, so laptops stop holding a long-lived application credential; the broker would send it the ID token and DPoP proof and get the bound token back. Low priority by the owner's choice; needs shaping first, including how the service decides a laptop may ask (Sign-in and token issuance, filed: 0.2.0)
- A scripted mock model that asks for one MCP tool once, so Claude Code really calls it through the broker and gateway and prints the result (MCP gateway, filed: 0.2.0)
- Tool use in the Bedrock adapter, then a real model choosing to call an MCP tool; needs paid AWS time (MCP gateway, filed: 0.2.0)
- Compare the token flow with MCP's Enterprise-Managed Authorization extension and decide whether to offer it alongside. It decides at the identity provider and takes two token requests where ours takes one; the IETF draft under it allows DPoP-bound grants and tokens, so it need not mean bearer tokens. Keycloak can accept such grants only experimentally and cannot issue them (MCP gateway, filed: 0.2.0)
- Let an upstream MCP server ask the user for input mid-call (the specification's multi-round-trip requests) and long-lived change notifications; the first gateway version refuses both (MCP gateway, filed: 0.2.0)
- Read the November 2026 AWS bill once it is final and record the figures against the estimate of about $0.04 for the live Bedrock run; at the same time identify the one key pair left in `us-east-1` and delete it if it belonged to the run (Gateway and inference, filed: 0.2.0)
- Sign the Secure Enclave helper and decide how it authorizes its caller (Sender-constrained access, filed: 0.1.0)

## Debt register

Known structural debt, each with the pain it causes. Feeds the release-planning
conversation alongside features.

- Strict JSON parsing is duplicated in `oauth-lab/oidc.py` and `oauth-as/foundation.py`; a fix to one can miss the other (filed: 0.1.0)
- The Bedrock request is validated twice, once in the gateway and once in the adapter transport (filed: 0.1.0)
- The mock's tests use a Starlette test client that now emits a deprecation warning (filed: 0.1.0)
