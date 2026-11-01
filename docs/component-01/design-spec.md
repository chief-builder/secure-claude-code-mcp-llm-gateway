# Component 01 — Claude Code → Local Mock LLM

**Project:** Secure Claude Code – MCP & LLM Gateway  
**Version:** 1.0  
**Status:** Design Approved — Implementation Not Started  
**Platform:** macOS

## 1. Objective

Validate communication between Claude Code running on macOS and a locally hosted, Anthropic Messages-compatible mock LLM API.

The component must support HTTP requests, deterministic mock responses, and Server-Sent Events (SSE) streaming.

No real LLM inference, OAuth authentication, DPoP, credential broker, or AWS Bedrock integration is included.

## 2. Architecture

```text
+---------------------------------------+
| Managed macOS laptop                  |
|                                       |
|  +---------------------------------+  |
|  | Claude Code CLI                 |  |
|  +---------------------------------+  |
|                |                      |
|                | HTTP POST            |
|                | /v1/messages         |
|                v                      |
|  +---------------------------------+  |
|  | Local Mock LLM API              |  |
|  | Python FastAPI                  |  |
|  | 127.0.0.1:8765                  |  |
|  +---------------------------------+  |
|                |                      |
|                | JSON or SSE          |
|                v                      |
|        Claude Code CLI                |
+---------------------------------------+
```

All inference traffic between Claude Code and the mock server remains on the Mac's loopback interface.

## 3. Approved Design Decisions

**Decision A — Mock behavior**

Start with text-only deterministic responses. Introduce tool-use simulation only if actual Claude Code compatibility testing demonstrates that it is necessary.

**Decision B — Client configuration**

Use `ANTHROPIC_BASE_URL` and a disposable `ANTHROPIC_AUTH_TOKEN`. Do not make global changes to Claude Code configuration.

**Decision C — Protocol**

Implement an Anthropic Messages-compatible HTTP API rather than the native AWS Bedrock wire protocol.

## 4. Technology Stack

| Component | Technology |
|---|---|
| Client | Claude Code CLI |
| Operating system | macOS |
| Mock API | Python 3.12+ and FastAPI |
| HTTP server | Uvicorn |
| Transport | HTTP over IPv4 loopback |
| Bind address | 127.0.0.1 |
| Port | 8765 |
| Response format | JSON and SSE |
| Authentication | Disposable test credential |
| Actual model inference | None |

## 5. Claude Code Configuration

The test environment will use:

```bash
export ANTHROPIC_BASE_URL=http://127.0.0.1:8765
export ANTHROPIC_AUTH_TOKEN=local-mock-only
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
```

These variables are intended only for the isolated lab session.

The disposable token has no enterprise privileges and is not an OAuth Access Token.

The nonessential-traffic setting does not guarantee complete network isolation. External network activity must be assessed independently.

## 6. API Contract

### POST /v1/messages

Accept an Anthropic Messages-compatible request.

Relevant request fields:

- `model`
- `max_tokens`
- `messages`
- `system`
- `stream`
- `tools`

Additional valid optional fields should not be rejected unnecessarily.

If `stream` is false, return an Anthropic-compatible JSON message.

If `stream` is true, return an SSE stream.

### GET /health

Returns the mock service's readiness status.

### HEAD /api/hello

Provides compatibility with optional client connection probes.

### POST /v1/messages/count_tokens

Deferred unless compatibility testing shows that it is required.

The server must also accept supported query parameters such as `?beta=true`.

## 7. Non-Streaming Response Contract

A successful mock completion will include:

- A message ID
- `type: message`
- `role: assistant`
- A model identifier
- A text content block
- `stop_reason: end_turn`
- Token usage fields

Expected text:

**MOCK_OK — Local inference working**

Token usage values are synthetic.

## 8. Streaming Contract

Use `Content-Type: text/event-stream`.

The expected sequence is:

1. `message_start`
2. `content_block_start`
3. One or more `content_block_delta` events
4. `content_block_stop`
5. `message_delta`
6. `message_stop`

The server must flush streaming events incrementally, maintain proper event ordering and terminate responses correctly.

Streaming must support:

- Multiple content deltas
- Client cancellation
- Clean connection termination
- Deliberately interrupted streams for negative testing

Only text content streaming is required in the initial implementation.

## 9. Trust Boundaries and Security

Claude Code is treated as an inference client, not as a secure credential vault.

The mock service:

- Must bind to `127.0.0.1`, not `0.0.0.0`.
- Must not connect to AWS Bedrock.
- Must not forward inference requests to external services.
- Must not handle production credentials.
- Must not contain or process real PHI.
- Must not execute model-requested tools.
- Must not log authorization headers or prompt bodies by default.
- Must return appropriate errors for malformed requests.
- Must not require root privileges.

Loopback HTTP is acceptable for this synthetic local lab. It is not considered sufficient protection for production credentials.

## 10. Acceptance Tests

### Connectivity

- C1: Claude Code sends inference requests to `127.0.0.1:8765`.
- C2: The mock returns a valid Anthropic-compatible response.
- C3: Claude Code displays `MOCK_OK` without invoking a real model.

### Protocol

- P1: Non-streaming JSON response succeeds.
- P2: SSE events arrive in valid order and complete correctly.
- P3: Multiple sequential requests succeed.
- P4: Valid optional fields do not cause unnecessary request failures.

### Security

- S1: The mock listens only on loopback.
- S2: No AWS or enterprise credentials are required.
- S3: Invalid disposable test credentials are rejected.
- S4: Standard logs contain neither authorization headers nor prompt bodies.
- S5: No real LLM inference request occurs.

### Failure Handling

- F1: Malformed requests return appropriate HTTP 4xx responses.
- F2: Interrupted streams and client cancellation are handled.
- F3: Unknown routes cannot forward traffic to another server.

## 11. Deferred Functionality

The following are excluded from Component 1:

- Keycloak SSO
- OAuth Authorization Code + PKCE
- RFC 8693 Token Exchange
- LLM Gateway Access Token validation
- DPoP
- macOS Credential Broker
- Secure Enclave
- MCP tool execution
- AWS Bedrock inference
- Production-grade network and endpoint protection

## 12. Approval and Implementation Status

**Design decisions A, B and C:** Approved.

**Architecture and protocol contract:** Baseline approved for implementation, subject to compatibility testing.

**Implementation:** Not started.

**Testing:** Not started.

**Next milestone:** Implement and validate Component 1 only.

Do not proceed to Component 2 until Component 1 acceptance criteria have been reviewed and passed.
