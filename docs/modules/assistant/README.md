---
updated: 2026-10-03
source: 0020_rich_parts
---

# assistant

Status: Clara answers free questions about the customer's own money (task 0019) with checked prose, the bank's own screens of what she read and read-only choices (task 0020): `chatbot` runs the deterministic safety floor, then the `open_mode` graph (Claude Sonnet 4.6 over ten read-only tools), publishes what she is checking while she works, and replies with parts (`say`, `view`, `ask`) whose every value is a rendered fact. The story path with write asks (block, claim, handoff) is designed for B4, not built.

The per-turn engine of Clara: for each customer message about an unrecognized card charge, it decides between explaining the charge, opening a claim, or protecting the card, using only the customer's own verified records, and writes to the account only with confirmation and a read-back.
The model (Claude Sonnet 4.6 on Bedrock) reads the customer's data through tools and writes prose by reference; code renders every value, checks the prose and falls back to templates; writes stay with deterministic rules and the customer's confirmation (B4).

## Boundaries

- Owns: the turn (`core.turn`: safety floor and router, the `open_mode` graph, the reply), the read tools and the facts check, `search_policies` over the bank's documents, the fixed answers, and, from B4, the rules, asks, writes and the handoff package.
- Does not own: case lifecycle after intake, officer assignment and ranking, the human live-chat surface, model training, Cognito and IAM setup, or the deadline table's legal accuracy.
- Code: `lambdas/chatbot`, `lambdas/crud` (the customer's own data), `lambdas/core`, `apps/customer`, `apps/ui`.

## Documents

- [prd.md](prd.md): product behavior
- [trd.md](trd.md): structure and endpoints
- [ard.md](ard.md): decisions and debt
- [database.md](database.md): tables and invariants
- [flows.md](flows.md): the turn, as a diagram
