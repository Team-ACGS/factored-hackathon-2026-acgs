---
updated: 2026-09-27
source: setup
---

# Messaging

Status: designed, not built.

Owns the room and message history shared by a customer, Clara and, once a handoff happens, a human agent, and the async delivery path that gets a finished reply to the client without the customer-facing request ever waiting on it.
The chatbot lambda (assistant) publishes a finished reply to SQS; this module's `lambdas/notifications` consumes it, writes the room's history and pushes it to the client over an AppSync Events channel.

## Boundaries

- Owns: the `rooms` and `messages` tables (2 of the 7 confirmed DynamoDB tables), the customer's post-conversation rating and comment, the SQS-to-DynamoDB-to-AppSync-Events delivery path, one realtime channel per room.
- Does not own: what Clara decides to say (assistant), the case record and its lifecycle (cases, backed by `complaints`), who may join a room as staff (identity).
- Code: `lambdas/notifications` (does not exist yet).

## Documents

- [prd.md](prd.md): product behavior
- [trd.md](trd.md): structure and endpoints
- [ard.md](ard.md): decisions and debt
- [database.md](database.md): tables and invariants
- [flows.md](flows.md): diagrams
