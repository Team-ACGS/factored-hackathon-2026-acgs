---
updated: 2026-09-27
source: 0003_walking_skeleton
---

# Messaging: database

Status: tables and stream built (tasks 0001 and 0002), written by the code since task 0003.
Keys live in Terraform (`infra/stacks/backend/dynamo.tf`).

## Tables owned

| Table | Keys | Purpose |
|---|---|---|
| `rooms` | `customer_id`, `room_id` | One row per conversation; `delegated_to_human` silences Clara (set by hand until handoff exists); will hold the customer's rating (1 to 5) and optional comment. |
| `messages` | `customer_id`, `message_key` (`<room_id>#<sent_at>#<message_id>`) | Every message of every room, in order within a room. Stream: new image. |

Every message carries `sender_type`: `customer`, `assistant` or `agent`.
It is a contract with the infrastructure: the chatbot's stream mapping filters on it.

## Tables referenced

None.

## Invariants kept in code

- Only `core.messaging` writes `messages` and `rooms`, "only if absent", so a retry never duplicates a message or a room.
- `room_id` and `message_id` are UUIDv7 minted by the client; `sent_at` in `message_key` is the millisecond of `message_id`, so the key order is the send order, and the latest room is the greatest `room_id`.
- A reply's `message_id` is the successor of the id it answers (same millisecond, random part plus one) and it keeps its `sent_at`, so nothing sorts between them and a redelivered record writes the same key.
- `created_at` is the server time of the first write and is what the chat displays.
- `customer_id` always comes from the token's `sub` or the stream record, never from a request body.
- A message is written once; delivery and the chatbot react to the stream, never to a second write or a queue.
- A room outlives any single case: the agent joins the room the customer was already in.

## Migrations of note

- 2026-09-27 (task 0002): stream enabled on `messages`.
