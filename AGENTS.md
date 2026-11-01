# Project: Secure Claude Code – MCP & LLM Gateway

## Objective

Build a secure, enterprise-grade LLM inference architecture connecting Claude Code on macOS to AWS Bedrock through an enterprise LLM Gateway.

The architecture will use OAuth 2.0, RFC 8693 Token Exchange, DPoP (RFC 9449), and a macOS Credential Broker.

The long-term objective is to prevent stolen access tokens from being replayed and keep AWS credentials off developer laptops.

## Development Rules

1. Design one component at a time.
2. Do not implement code until the component design has been explicitly approved.
3. Implement only the approved component.
4. Write functional and security tests for every component.
5. Review test results before proceeding.
6. Prefer open-source and free components for local development.
7. Never use real patient data (PHI), production tokens, or enterprise secrets.
8. Document architectural decisions and security limitations.
9. Never claim a component is tested unless tests were actually executed.

## Approved Component 1 Decisions

- **A:** Start with text-only responses. Add tool-use simulation only if Claude Code compatibility testing requires it.
- **B:** Use `ANTHROPIC_BASE_URL` and a disposable `ANTHROPIC_AUTH_TOKEN`. Do not modify global Claude Code settings.
- **C:** Implement an Anthropic Messages-compatible API, not the AWS Bedrock wire protocol.

## Component Roadmap

1. Claude Code → Local Mock LLM
2. Keycloak SSO + OAuth Authorization Server
3. RFC 8693 Token Exchange
4. LLM Gateway OAuth Authentication and Authorization
5. DPoP Sender-Constrained Token Security
6. macOS Credential Broker
7. Secure Enclave Integration
8. AWS Bedrock Integration

## Current Status

Component 1: Design approved. Implementation not started.

## Security Requirements

- No production credentials or PHI.
- No AWS credentials in Claude Code.
- Prevent accidental credential exposure in logs or configuration.
- Use sender-constrained tokens for the final architecture.
- Restrict local network exposure.
- Maintain auditable authentication and authorization flows.

## Working Agreement

For every component:

Design → Review → Approve → Implement → Test → Accept

Do not advance to the next stage without explicit approval.
