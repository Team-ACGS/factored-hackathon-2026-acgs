---
updated: 2026-09-27
source: task 0002
---

# Messaging

Status: infrastructure built (task 0002), code not built.

Owns the room and message history shared by a customer, Clara and, once a handoff happens, a human agent, and the path that delivers every new message to whoever is watching the room.
A message is stored once, in `messages`; everyone who cares learns about it from that table's stream, never from a second write.

## Boundaries

- Owns: the `rooms` and `messages` tables, the messaging code in `lambdas/core` (the single path that writes them), `lambdas/messages` (the API), `lambdas/chat_notifier` (the push), one realtime channel per room, the customer's post-conversation rating and comment.
- Does not own: what Clara decides to say (assistant, `lambdas/chatbot`), the case record and its lifecycle (cases, `complaints`), who may act on a room (identity).
- Code: `lambdas/messages`, `lambdas/chat_notifier`, messaging code in `lambdas/core` (none exist yet; lambdas run bootstrap bundles).

## Documents

- [prd.md](prd.md): product behavior
- [trd.md](trd.md): structure and endpoints
- [ard.md](ard.md): decisions and debt
- [database.md](database.md): tables and invariants
- [flows.md](flows.md): diagrams
