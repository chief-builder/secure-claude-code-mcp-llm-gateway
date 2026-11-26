# ADR-0001: Host the identity services on one AWS host reached by tunnels first, then split

Date: 2026-11-25
Status: **accepted**

**Context.** Keycloak and the authorization server run on the developer's Mac. The
owner wants them on AWS for three reasons: so the laptop holds only client pieces,
as it would in a company; so remote MCP servers can later trust the same services;
and so other people can run the lab against servers instead of their own machine.
Every address in the code is pinned to `127.0.0.1`: the issuer, the Keycloak realm,
the gateway endpoint and the sign-in callback in Python, and the two endpoints the
Secure Enclave signer will sign for in Swift.

**Decision.** Build in two slices. First, run Keycloak, the authorization server and
the gateway on a single AWS host, each listening on that host's loopback, and reach
them from the Mac through authenticated tunnels to the same port numbers. The pinned
addresses stay valid, so no component code changes. Second, split identity
(Keycloak and the authorization server) and the gateway onto separate hosts, which
requires making the addresses configuration. The deployment is created from a
template, runs only for a working session, and is removed with one command.

**Alternatives considered.**

- Two hosts from the start: keeps the signing key and the Bedrock role apart from
  day one, but begins with a change to accepted security modules before anything
  runs on AWS.
- One host only: cheapest, but leaves the signing key and the Bedrock credentials on
  one machine permanently, which undercuts the separation the project exists to show.
- Public endpoints with real DNS and certificates: closest to production, but needs
  a domain, costs more and exposes the services to the internet.
- Always on: needed for a shared deployment, but bills continuously and must be
  patched and watched.

**Consequences.**

- The first slice is quick and changes no protocol code.
- During the first slice the token-signing key, the identity provider and the
  Bedrock role share one host. A compromise of that host is a compromise of all
  three. This is weaker than today, where the signing key is on the Mac and the
  Bedrock role on AWS, and it is accepted only until the second slice. The first
  slice must still separate the services by operating-system user and keep the
  instance role away from the identity processes.
- "A lab others can reach" is met as: anyone can create their own copy from the
  template in their own AWS account. It is not a shared deployment. A shared one
  would need to stay up, real host names, and a way to register each person's
  client, none of which is planned.
- The exchange client's private key stays on the Mac with the broker. Moving the
  servers does not remove that known limitation.
- The second slice needs the configurable-address work and benefits from real
  packages, both already on the backlog.
