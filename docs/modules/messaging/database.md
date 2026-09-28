---
updated: 2026-09-27
source: task 0002
---

# Messaging: database

Status: tables and stream built (tasks 0001 and 0002), no data.
Keys live in Terraform (`infra/stacks/backend/dynamo.tf`).

## Tables owned

| Table | Keys | Purpose |
|---|---|---|
| `rooms` | `customer_id`, `room_id` | One row per conversation; says whether the room is delegated to a human; holds the customer's rating (1 to 5) and optional comment. |
| `messages` | `customer_id`, `message_key` (`<room_id>#<sent_at>#<message_id>`) | Every message of every room, in order within a room. Stream: new image. |

Every message carries `sender_type`: `customer`, `assistant` or `agent`.
It is a contract with the infrastructure: the chatbot's stream mapping filters on it.

## Tables referenced

None.

## Invariants kept in code

- Only the messaging code in `lambdas/core` writes `messages` and `rooms`, with conditional writes on deterministic ids, so a retry never duplicates a message.
- A message is written once; delivery and the chatbot react to the stream, never to a second write or a queue.
- A room outlives any single case: the agent joins the room the customer was already in.

## Migrations of note

- 2026-09-27 (task 0002): stream enabled on `messages`.
