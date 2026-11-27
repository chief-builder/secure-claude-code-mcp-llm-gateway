# Glossary

Terms used across this project, in plain language. Each entry says what the term
means here and links to the standard that defines it.

## Identity and sign-in

### Identity provider

The service that knows who the user is and signs them in. In
the lab this is Keycloak. It issues ID tokens; it never sees inference requests.

### OpenID Connect (OIDC)

A sign-in protocol built on OAuth 2.0. The user signs in
through a browser, and the application receives a signed ID token describing them.
[OpenID Connect Core](https://openid.net/specs/openid-connect-core-1_0.html)

### ID token

A signed statement from the identity provider that a particular user
signed in, for a particular application, at a particular time. Here it is the input
to token exchange and is used once.

### PKCE (Proof Key for Code Exchange)

A protection for browser sign-in. The
application sends a hash of a random secret when sign-in starts and the secret itself
when it finishes, so an intercepted authorization code is useless on its own.
[RFC 7636](https://www.rfc-editor.org/rfc/rfc7636.html)

### Keycloak

The open-source identity provider the lab runs in Docker. It signs the synthetic user
in and issues the ID token. [Keycloak](https://www.keycloak.org/)

### Realm

Keycloak's name for one isolated set of users, clients and keys. The lab
uses a single realm called `claude-security-lab`.

## Tokens and authorization

### Authorization server (AS)

The service that decides whether to issue an access
token and signs it. In the lab it is a separate service from Keycloak, at
`https://127.0.0.1:8081`. Keycloak says who the user is; the authorization server
says what they may call.

### Issuer

The URL that identifies whoever signed a token. A verifier accepts a
token only if its `iss` claim names the issuer it trusts and the signature checks
against that issuer's published keys.

### Access token

A short-lived signed credential that authorizes calls to one
service. Here it is a JWT naming the gateway as its audience, valid for at most five
minutes. [RFC 9068](https://www.rfc-editor.org/rfc/rfc9068.html)

### JWT (JSON Web Token)

A compact signed JSON document made of a header, a set of
claims and a signature. [RFC 7519](https://www.rfc-editor.org/rfc/rfc7519.html)

### Claim

One named field inside a token, such as `iss` (issuer), `aud` (audience),
`sub` (subject), `exp` (expiry) or `scope`.

### Audience

The service a token is meant for. A service must reject a token whose
audience is somebody else.

### Scope

What a token permits. The lab has one scope, `llm:invoke`.

### JWKS (JSON Web Key Set)

The public keys a service publishes so others can check
its signatures. [RFC 7517](https://www.rfc-editor.org/rfc/rfc7517.html)

### Token exchange

Trading one token for another with a different audience or
purpose. Here the broker trades the Keycloak ID token for a gateway access token, so
the gateway never has to trust Keycloak directly.
[RFC 8693](https://www.rfc-editor.org/rfc/rfc8693.html)

### Subject token

The token handed in during token exchange — here, the ID token.

### Client assertion (`private_key_jwt`)

How the exchange client proves its own
identity to the authorization server: it signs a short-lived JWT with its private
key instead of sending a shared password.
[RFC 7523](https://www.rfc-editor.org/rfc/rfc7523.html), as updated by
[RFC 10070](https://www.rfc-editor.org/rfc/rfc10070.html): the assertion names the
authorization server's issuer as its only audience, and the lab's clients mark it
with the type `client-authentication+jwt`, as the RFC recommends.

### Bearer token

A token that works for whoever holds it. If it is stolen, the
thief can use it. DPoP exists to remove that property.

## Sender-constrained tokens

### Sender-constrained token

A token that only works together with proof that the
caller holds a particular private key. Stealing the token alone is not enough.

### DPoP (Demonstrating Proof of Possession)

The mechanism used here to
sender-constrain tokens. The client holds a key pair, the access token records that
key's thumbprint, and every request carries a freshly signed proof.
[RFC 9449](https://www.rfc-editor.org/rfc/rfc9449.html)

### DPoP proof

A small JWT, signed by the client's DPoP key and sent in the `DPoP`
header, that names the HTTP method and URL of this one request, when it was made, a
unique identifier, the server's nonce and a hash of the access token.

### Key thumbprint (`jkt`)

A hash of a public key, used as its short identity. The
access token carries it in the `cnf.jkt` claim; the gateway checks that the proof was
signed by the key with that thumbprint.
[RFC 7638](https://www.rfc-editor.org/rfc/rfc7638.html)

### Nonce

A short-lived value the server hands to the client, which the client must
include in its next proof. It shows the proof was made recently and for this server.
The first request without one is answered with a challenge and retried.

### Replay protection

Refusing a credential that has been used before. The
authorization server records used client assertions, subject tokens and proofs, and
the gateway records used proofs, each in a small SQLite database until they expire.

## The lab's own parts

### Gateway

The service in front of the model. It checks the access token, the DPoP
proof, the nonce and replay state, then forwards the request. It is the only place
that holds AWS credentials.

### Credential broker

A local process that signs in, exchanges tokens, holds the
gateway token and DPoP key, and launches Claude Code. Claude Code talks only to the
broker, on loopback, with a random secret that is valid for one session.

### Secure Enclave

Hardware in Apple devices that can create a private key and sign
with it without ever revealing the key to software. The lab can keep the DPoP key
there. [Apple documentation](https://support.apple.com/guide/security/secure-enclave-sec59b0b31ff/web)

### Mock LLM

A stand-in for a model that speaks the Anthropic Messages API and
always answers `MOCK_OK`. It lets the whole security path be tested without calling a
real model.

### Anthropic Messages API

The HTTP API Claude Code uses to talk to a model. The
gateway accepts this format and, for Bedrock, translates it.

### Bedrock Converse

The AWS API the gateway calls for real inference. The adapter
converts Messages requests to Converse and the replies back again.

### Instance role

Temporary AWS credentials given to a virtual machine by AWS
itself. The gateway host uses one, so no long-lived AWS key exists anywhere.

### Loopback

The address `127.0.0.1`, reachable only from the same machine. Every
lab service listens there and nowhere else.

### Lab CA

A throwaway certificate authority created per service so the lab can use
real HTTPS. Its certificates last seven days.
