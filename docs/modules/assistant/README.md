---
updated: 2026-09-27
source: setup
---

# assistant

Status: designed, not built.

The per-turn engine of Clara: for each customer message about an unrecognized card charge, it decides between explaining the charge, opening a claim, or protecting the card, using only the customer's own verified records, and writes to the account only with confirmation and a read-back.
The LLM (Claude Sonnet 5 on Bedrock) extracts and composes; a versioned rules table decides.

## Boundaries

- Owns: the turn pipeline (ingress, understand, retrieve, decide, act, compose, egress), the policy table, the intent router and injection detector's use inside the turn, the grounding check, and the structured handoff package it produces.
- Does not own: case lifecycle after intake, officer assignment and ranking, the human live-chat surface, model training, Cognito and IAM setup, or the deadline table's legal accuracy.
- Code: `lambdas/chatbot`, `lambdas/core`, `apps/customer` (none exist yet).

## Documents

- [prd.md](prd.md): product behavior
- [trd.md](trd.md): structure and endpoints
- [ard.md](ard.md): decisions and debt
- [database.md](database.md): tables and invariants
- [flows.md](flows.md): the turn, as a diagram
