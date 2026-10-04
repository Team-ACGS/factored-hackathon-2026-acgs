---
updated: 2026-10-04
source: 0022_story_actions
---

# Cases

Status: Clara opens fraud, claim and service cases with the handoff package and its summary, and the customer sees them (task 0022); the agent console and resolutions are designed, not built.

Owns the case record created when the assistant decides `CLAIM` or `PROTECT`, the structured handoff package that carries verified facts to a human, and the agent console where that human works the case.
Cases only ever writes the `Open` status; every later transition (analysis, chargeback, ruling, closure) is human work the module merely reads.

## Boundaries

- Owns: the case record and its lifecycle read path, the handoff package's storage and display, the agent console (`apps/support`).
- Does not own: deciding when a handoff happens or what it contains (assistant), categorizing/ranking/assigning cases to officers (inbox), the chat transport itself (messaging), any decision about money.
- Code: the case-writing code in `lambdas/core` (shared package, no lambda-to-lambda calls, used by both `lambdas/crud` and `lambdas/chatbot`), `lambdas/crud` (agent/officer API), `apps/support` (none of this exists yet).

## Documents

- [prd.md](prd.md): product behavior
- [trd.md](trd.md): structure and endpoints
- [ard.md](ard.md): decisions and debt
- [database.md](database.md): tables and invariants
- [flows.md](flows.md): diagrams
