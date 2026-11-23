# Security policy

## Scope

This repository is a reference implementation for a synthetic lab. It is not
a supported product and must not be deployed with real identities, production
credentials or sensitive data. The
[known limitations](README.md#known-limitations) are documented design
boundaries, not vulnerabilities.

Reports are welcome for anything that breaks a property the lab claims to
have, for example:

- an access token accepted without a valid DPoP proof for its bound key;
- a replayed proof, nonce, client assertion or subject token being accepted;
- a token accepted with the wrong issuer, audience, scope, type or lifetime;
- credentials, tokens or prompt content appearing in logs;
- a lab service listening beyond loopback with the documented setup.

## Reporting

Please use GitHub's private vulnerability reporting for this repository
(Security tab → Report a vulnerability). Do not open a public issue for a
suspected vulnerability.

This is a personal project maintained on a best-effort basis. There is no
guaranteed response time.

## Lab credentials in the repository

`components/oauth-lab/realm.json` contains a password for a synthetic Keycloak
user. It is intentional, works only against the loopback lab realm, and is not
a secret.
