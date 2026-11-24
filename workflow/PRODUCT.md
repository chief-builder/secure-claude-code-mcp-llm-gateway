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

### Sender-constrained access

- DPoP-bound access tokens with server nonces and replay protection — done
- Hardware-held DPoP key in Apple Secure Enclave — done

### Gateway and inference

- Gateway authentication and authorization — done
- Mock LLM backend — done
- AWS Bedrock Converse backend, text only — done
- Tool use, images and thinking — idea

### Local credential broker

- Single-prompt broker that launches Claude Code — done
- Token refresh for interactive sessions — idea

### MCP gateway

- Securing MCP server access through the same identity and token model — idea

### Documentation

Documentation — done: a one-page quickstart, task-based component READMEs, a glossary, explanation pages and an index that separates them from verification records.

## Not this

- Not a production gateway. It is accepted for a synthetic lab only.
- Not for real identities, production credentials or sensitive data.
- Not a general-purpose proxy: one route, text only, fixed loopback addresses.
- Not a supported product: no guaranteed fixes or response times.
