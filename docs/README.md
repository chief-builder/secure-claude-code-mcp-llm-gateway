# Documentation

To run the lab, start with the quickstart in the first table. For what the project
is and what it does not protect against, read the [root README](../README.md). Every document under `docs/` is listed below exactly once.

## How it works

Explanations of the system as it is now.

| Document | What it covers |
|---|---|
| [Quickstart](quickstart.md) | Running the whole lab from a fresh clone |
| [Glossary](glossary.md) | Every protocol and project term, in plain language |
| [One request, end to end](concepts/request-walkthrough.md) | A single prompt from sign-in to the model's reply |
| [Tokens and modes](concepts/tokens-and-modes.md) | Bearer mode against DPoP mode, and the two kinds of token, in diagrams |
| [The MCP gateway, step by step](concepts/mcp-gateway.md) | The path of a tool call, the order of the checks, and how a tool is hidden, in diagrams |
| [The shape of an MCP request](concepts/mcp-request.md) | What Claude Code sends to a tool server, and why each request says the same facts twice, in diagrams |
| [Authorization server walkthrough](concepts/authorization-server-walkthrough.md) | How a DPoP-bound token is issued, step by step through the code |
| [Gateway walkthrough](concepts/gateway-walkthrough.md) | How a DPoP request is verified, step by step through the code |

Each component's own README, linked from the
[root README](../README.md#components), covers running and testing that part alone.

## How it was verified

The record of how each component was designed, approved and accepted. These are
history: they describe the system at the time each gate was passed and are not
rewritten when the code changes. Where they disagree with the code, the code is
right.

| Component | Design | Evidence |
|---|---|---|
| 1 — Mock LLM | [Design spec](component-01/design-spec.md) | [Acceptance report](component-01/acceptance-report.md) |
| 2 — Keycloak sign-in and authorization server foundation | [Design spec](component-02/design-spec.md) | [2A acceptance report](component-02/acceptance-report-2a.md), [2B acceptance report](component-02/acceptance-report-2b.md) |
| 3 — Token exchange | [Design spec](component-03/design-spec.md) | [Verification](component-03/verification.md), including the live rerun after publication |
| 4 — Gateway authentication and authorization | [Design spec](component-04/design-spec.md) | [Verification](component-04/verification.md) |
| 5 — DPoP | [Design spec](component-05/design-spec.md) | [Verification](component-05/verification.md) |
| 6 — Credential broker | [Design spec](component-06/design-spec.md) | [Verification](component-06/verification.md), [debugger key extraction](component-06/debugger-extraction-verification.md) |
| 7 — Secure Enclave | [Design spec](component-07/design-spec.md) | [Verification](component-07/verification.md) |
| 8 — Bedrock | [Design spec](component-08/design-spec.md) | [Verification](component-08/verification.md), [deployment and cost plan](component-08/deployment-cost-plan.md) |

The design specs are also the most detailed explanation of *why* each part is built
the way it is. Read them for reasoning; read the pages above for how to use it.

Work done after publication is recorded differently, as an intent, spec and plan per
task under [`workflow/releases`](../workflow/releases).
