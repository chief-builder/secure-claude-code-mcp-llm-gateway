# The MCP gateway, step by step

The MCP gateway stands between a caller and a tool server. This page shows what
happens to one tool call, and where each check sits. It builds on
[the shape of an MCP request](mcp-request.md) and
[tokens and modes](tokens-and-modes.md). Unfamiliar terms are in the
[glossary](../glossary.md).

## Who holds what

```mermaid
flowchart LR
    C["Caller<br/>holds: MCP token,<br/>DPoP private key"]
    G["MCP gateway<br/>holds: tool policy,<br/>tool server credential"]
    T["Tool server<br/>holds: the tools"]
    A["Authorization server<br/>holds: token signing key"]
    C -->|"MCP token + fresh proof"| G
    G -->|"its own credential,<br/>a request it built itself"| T
    G -.->|"fetches public keys"| A
```

The caller's token and proof stop at the gateway. The tool server never sees them,
and never learns who the user is. The gateway never sees the caller's private key.
In the lab the caller is a test client today; once the broker work is done it will
be the broker, acting for Claude Code.

## One allowed call

```mermaid
sequenceDiagram
    participant C as Caller
    participant G as MCP gateway
    participant T as Tool server
    C->>G: tools/call lab_echo, with token and proof
    Note over G: Token is for this gateway and bound to a key
    Note over G: Proof is signed by that key, for this address, with a fresh nonce
    Note over G: Headers agree with the body
    Note over G: Proof recorded, so it cannot be used again
    Note over G: Policy allows this user lab_echo
    G->>T: tools/call lab_echo, with the gateway's credential
    T-->>G: Result
    Note over G: Reply is one complete result
    G-->>C: Result
    Note over G: Audit line with user and tool name
```

## The checks, in order

Every request passes these in order and stops at the first that fails. Nothing is
sent to the tool server until all have passed.

```mermaid
flowchart TD
    R["Request arrives"] --> O{"Origin header?"}
    O -->|"yes"| X1["403"]
    O -->|"no"| K{"Exactly one<br/>DPoP credential?"}
    K -->|"no"| X2["400 or 401"]
    K -->|"yes"| T{"Valid MCP token?<br/>audience, signature,<br/>lifetime, key binding"}
    T -->|"no"| X3["401"]
    T -->|"yes"| P{"Valid proof?<br/>key, address, nonce"}
    P -->|"no"| X4["401, with a nonce<br/>if one is needed"]
    P -->|"yes"| S{"Lab client and<br/>mcp:invoke scope?"}
    S -->|"no"| X5["403"]
    S -->|"yes"| H{"Headers agree<br/>with the body?"}
    H -->|"no"| X6["400"]
    H -->|"yes"| Y{"Proof unused?"}
    Y -->|"no"| X7["401"]
    Y -->|"yes"| M{"Which method?"}
    M -->|"server/discover"| D["Gateway answers itself"]
    M -->|"tools/list"| L["Forward, then remove<br/>tools not allowed"]
    M -->|"tools/call"| A{"Tool allowed<br/>for this user?"}
    M -->|"anything else"| X8["404"]
    A -->|"no"| X9["Unknown tool"]
    A -->|"yes"| F["Forward the call"]
```

A model token fails at the token check, because its audience is the LLM gateway. A
proof made for the LLM gateway fails at the proof check, because a proof names the
address it was made for.

## Hiding a tool

The policy lists each user's tools. Two things follow from it, and the second is
the one that enforces it:

- `tools/list` shows only the user's tools. The list is marked private so that no
  cache hands one user's list to another.
- `tools/call` for any other tool is refused with the same "unknown tool" reply,
  byte for byte, whether the tool exists or not. The caller cannot tell a hidden
  tool from one that was never there, and the tool server is not contacted.

Leaving a tool out of the list would not be enough on its own. A caller who knew
the name could still ask for it.

## What the gateway does not pass on

| From the caller | Reaches the tool server? |
|---|---|
| The MCP token and the DPoP proof | No. The gateway sends its own credential |
| The tool name and arguments | Yes, for an allowed tool |
| The capabilities the caller declares, such as being able to prompt the user | No. The gateway sends an empty set, so a tool server cannot ask the user for input |
| Any other field of the request | No. The gateway builds a new request from named fields |
| The protocol revision | The gateway always sends 2026-07-28, in the header and the body, so the tool server applies this revision's rules |

And in the other direction, the gateway passes back only a complete result. A reply
that is a stream, asks for input, or hands back a task is refused.

## Why the gateway answers discovery itself

`server/discover` asks a server which kinds of feature it offers. The gateway
answers "tools only" under its own name, without asking the tool server. The tool
server would also claim prompts and resources, which the gateway refuses, and would
reveal what software sits behind the gateway.

Code: [`mcp_gateway.py`](../../components/gateway/mcp_gateway.py) and its
[tests](../../components/gateway/tests/test_mcp_gateway.py). How to run it:
[MCP gateway README](../../components/gateway/README-mcp.md).
