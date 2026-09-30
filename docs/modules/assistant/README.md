---
updated: 2026-09-29
source: 0010_customer_redesign
---

# assistant

Status: walking skeleton (task 0003): `chatbot` echoes each customer message and emits `turn.completed`. The customer app is a bank app with Clara as its agent (task 0010), whose chat runs on a client mock behind one switch. The turn itself is designed, not built.

The per-turn engine of Clara: for each customer message about an unrecognized card charge, it decides between explaining the charge, opening a claim, or protecting the card, using only the customer's own verified records, and writes to the account only with confirmation and a read-back.
The LLM (Claude Sonnet 5 on Bedrock) extracts and composes; a versioned rules table decides.

## Boundaries

- Owns: the turn pipeline (ingress, understand, retrieve, decide, act, compose, egress), the policy table, the intent router and injection detector's use inside the turn, the grounding check, and the structured handoff package it produces.
- Does not own: case lifecycle after intake, officer assignment and ranking, the human live-chat surface, model training, Cognito and IAM setup, or the deadline table's legal accuracy.
- Code: `lambdas/chatbot`, `lambdas/crud` (the customer's own data), `lambdas/core`, `apps/customer`, `apps/ui`.

## Documents

- [prd.md](prd.md): product behavior
- [trd.md](trd.md): structure and endpoints
- [ard.md](ard.md): decisions and debt
- [database.md](database.md): tables and invariants
- [flows.md](flows.md): the turn, as a diagram
