# ADR-0001: Host the identity services on one AWS host reached by tunnels first, then split

Date: 2026-11-25
Status: **accepted**

**Context.** Keycloak and the authorization server run on the developer's Mac. The
owner wants them on AWS for three reasons: so the laptop holds only client pieces,
as it would in a company; so remote MCP servers can later trust the same services;
and so that two people can use one deployment at the same time, each signing in
as a different synthetic user from their own Mac, as employees would in a company.
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
- Two people on two Macs can use one deployment while it is up. Nothing in this
  decision prevents it: each Mac opens its own tunnels, and the pinned loopback
  addresses are valid on both. It needs four things the lab does not have yet: a
  second synthetic user in the realm with its own line in the exchange policy; a
  way for the second person to open tunnels (their key and address allowed on the
  host); the three lab certificate authorities copied to the second Mac; and an
  exchange client key for the second Mac. The server already accepts several
  registered client keys, so each Mac can have its own; the setup command creates
  only one today.
- Where this still differs from a company: the second person reaches the services
  through a tunnel into the owner's AWS account instead of through real host names,
  and both Macs hold a client key. A deployment that stays up for people who are
  not given tunnel access would need real host names and certificates, and is not
  planned.
- The exchange client's private key stays on the Mac with the broker. Moving the
  servers does not remove that known limitation.
- The second slice needs the configurable-address work and benefits from real
  packages, both already on the backlog.
