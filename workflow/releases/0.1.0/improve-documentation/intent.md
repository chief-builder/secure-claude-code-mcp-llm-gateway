# Intent: improve-documentation

Release: next · Roadmap line: improve-documentation ·
Capability: Documentation

**Problem.** The repository is public as a reference implementation, but its
documentation was written for the person who built it, in the order it was built.
A newcomer meets five weaknesses, found in the publication review:

1. There is no single path through the lab. Setup is spread over five READMEs that
   hand shell variables from one to the next.
2. The READMEs are organised by build history ("Component 4", "Gate 5") instead of
   by what a reader wants to do.
3. Explanation and evidence are mixed. `docs/component-NN` holds acceptance records,
   and the two best explanations (the Component 5 walkthroughs) sit among them.
4. There is no glossary for terms such as DPoP, nonce, token exchange and client
   assertion.
5. Component 1, the mock LLM, has no README.

**Why now.** The roadmap's direction is "easy to understand and reproduce for someone
who was not part of building it". This is the first step, and MCP work would add more
material on top of the same weak structure.

**Success looks like.** Someone who has never seen the project can go from a fresh
clone to Claude Code printing the mock's reply by following one page, can look up any
unfamiliar term, and can tell at a glance which documents explain the system and
which record how it was verified.

**Constraints.** Documentation only: no change to code or behavior. The design specs
and verification records under `docs/component-NN` are frozen history; their content
is not rewritten.
