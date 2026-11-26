# ADR-0002: The token-signing key stays a file, not an AWS KMS key

Date: 2026-11-25
Status: **accepted**

**Context.** The authorization server's RSA signing key is the most valuable secret
in the lab: whoever holds it can mint gateway tokens. Today it is an owner-only file
on the developer's Mac. On AWS it could instead be created in AWS KMS, where it
cannot be exported and each signature is an audited API call.

**Decision.** Keep the signing key as an owner-only file on the host's encrypted
disk when the authorization server moves to AWS. Moving it into KMS is not planned.

**Alternatives considered.**

- KMS from the start: strongest custody, but changes the signing code in the same
  step as the move, and adds a per-signature cost and an IAM policy to review.
- A file first with KMS as a planned follow-up: keeps the two changes apart, but
  commits to work the owner has decided not to schedule.

**Consequences.**

- The signing code and its tests are unchanged by the move.
- Anyone who gains access to the host as the authorization server's user, or as
  root, can copy the key. The deployment is short-lived and each one generates a new
  key, which limits how long a copied key is useful to the life of that deployment
  plus the five-minute token lifetime.
- The README's known limitations should say so once the deployment exists.
- If the lab ever becomes long-lived or shared, this decision should be revisited
  first.
