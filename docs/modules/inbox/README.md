---
updated: 2026-09-27
source: setup
---

# Inbox

Status: designed, not built.

Owns the routing of a case that already exists: categorizing it into disputes, fraud or follow-up, ranking it against every other case in the same area with a versioned, explainable formula, and assigning it to the next eligible officer.
The backoffice app is where that officer then works the case: reviews evidence, starts a chargeback if needed, decides; the resolution itself is written through the cases module, inbox only writes ranking and assignment fields.

## Boundaries

- Owns: categorization, the priority score, the ranked queue per area, assignment (round robin, eligibility, hold-and-flag), the backoffice app (`apps/backoffice`).
- Does not own: the case record and its lifecycle, including officer resolutions (cases), deciding when a case is created or what it contains (assistant), the agent console for a live-chat handoff (cases, `apps/support`), the improvement console for the separate `analysts` group (not built now), any decision about money.
- Code: `lambdas` (exact lambda name not yet decided), `apps/backoffice` (neither exists yet).

## Documents

- [prd.md](prd.md): product behavior
- [trd.md](trd.md): structure and endpoints
- [ard.md](ard.md): decisions and debt
- [database.md](database.md): tables and invariants
