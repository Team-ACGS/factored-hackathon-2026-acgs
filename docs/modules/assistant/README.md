---
updated: 2026-10-04
source: 0022_story_actions
---

# assistant

Status: Clara answers free questions about the customer's own money (task 0019) with checked prose, the bank's own screens and choices (task 0020), remembers what the customer told her about a charge, and acts with consent: asks whether a flagged charge was theirs, blocks the card with read-back, opens fraud, claim and service cases with a prepared package, and abstains on unblock and money (task 0022). The graphs only read; every write is code on a confirming tap. Clara writing first (the watcher) is the next task.

The per-turn engine of Clara: for each customer message about an unrecognized card charge, it decides between explaining the charge, opening a claim, or protecting the card, using only the customer's own verified records, and writes to the account only with confirmation and a read-back.
The model (Claude Sonnet 4.6 on Bedrock) reads the customer's data through tools and writes prose by reference; code renders every value, checks the prose and falls back to templates; writes stay with deterministic rules and the customer's confirmation.

## Boundaries

- Owns: the turn (`core.turn`: safety floor and router, the `open_mode` graph, the reply), the read tools and the facts check, `search_policies` over the bank's documents, the fixed answers, the rules, asks, writes, memory and the handoff package.
- Does not own: case lifecycle after intake, officer assignment and ranking, the human live-chat surface, model training, Cognito and IAM setup, or the deadline table's legal accuracy.
- Code: `lambdas/chatbot`, `lambdas/crud` (the customer's own data), `lambdas/core`, `apps/customer`, `apps/ui`.

## Documents

- [prd.md](prd.md): product behavior
- [trd.md](trd.md): structure and endpoints
- [ard.md](ard.md): decisions and debt
- [database.md](database.md): tables and invariants
- [flows.md](flows.md): the turn, as a diagram
