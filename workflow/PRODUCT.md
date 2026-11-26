# Product

What this product is for and what it does. The roadmap says what happens next; this
file says why it matters. Grown by the shape playbook; statuses kept true by hygiene.

## Users and what they need

- **Engineers building an LLM gateway.** They want to see how token exchange, DPoP
  and a gateway fit together in running code, with tests they can read. Most public
  material covers one standard at a time.
- **Security architects reviewing such a design.** They want the threat model, the
  limits, and evidence of what was actually verified, so they can judge what carries
  over to their own environment.
- **People learning to build with AI coding tools.** They want to see a gated,
  evidence-based workflow applied to security-sensitive code.

## Capability map

### Sign-in and token issuance

- Keycloak browser sign-in with PKCE — done
- Authorization server metadata and signing keys — done
- RFC 8693 token exchange with one-time use — done
- RFC 7523bis explicit assertion type (`typ`) — idea
- An exchange service that keeps the exchange client's key off laptops — idea

### Sender-constrained access

- DPoP-bound access tokens with server nonces and replay protection — done
- Hardware-held DPoP key in Apple Secure Enclave — done

### Gateway and inference

- Gateway authentication and authorization — done
- Mock LLM backend — done
- AWS Bedrock Converse backend, text only — done
- Tool use in the Bedrock adapter — planned
- Images and thinking — idea

### Local credential broker

- Single-prompt broker that launches Claude Code — done
- Token refresh for interactive sessions — idea

### MCP gateway

Claude Code calling tools on MCP servers under the user's identity, with tokens that
cannot be replayed and tool-server credentials that never reach the laptop.
Decision: [MCP through the broker, with its own tokens and per-tool rules](decisions/0003-mcp-through-the-broker-with-its-own-tokens.md).

- Tokens for MCP with their own audience and scope, from the existing token exchange — planned
- A mock MCP server with harmless tools — planned
- MCP gateway: token, DPoP proof and replay checks, then per-tool rules — planned
- Broker as the local MCP endpoint for Claude Code — planned
- Claude Code really calling a tool, driven by a scripted mock model — planned
- A real model on Bedrock choosing to call a tool — planned
- Upstream servers asking the user for input mid-call, and change notifications — idea
- MCP's Enterprise-Managed Authorization extension as an alternative token flow — idea

### Hosted identity services

Keycloak, the authorization server and the gateway running on AWS, so the laptop
holds only Claude Code, the broker and the signing helper. Decisions:
[one host first, then split](decisions/0001-one-aws-host-reached-by-tunnels-first.md);
[the signing key stays a file](decisions/0002-token-signing-key-stays-a-file.md).

- One AWS host with all three services, created from a template and reached by tunnels, with no component code change — planned
- Two synthetic users on two Macs using one deployment at the same time — planned
- Addresses as configuration instead of pinned to `127.0.0.1`, in Python and in the Swift signer — planned
- Identity services and the gateway on separate hosts — planned
- An always-on deployment with real host names, for people without tunnel access — idea

### Documentation

Documentation — done: a one-page quickstart, task-based component READMEs, a glossary, explanation pages and an index that separates them from verification records.

## Not this

- Not a production gateway. It is accepted for a synthetic lab only.
- Not for real identities, production credentials or sensitive data.
- Not a general-purpose proxy: one route, text only, fixed loopback addresses.
- Not a supported product: no guaranteed fixes or response times.
- Not a gateway for ordinary MCP clients that sign in on their own: those get bearer
  tokens, which is the weakness this project exists to remove.
- Not a front for real tool servers with real credentials: mock tools only.
