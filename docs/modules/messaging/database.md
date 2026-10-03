---
updated: 2026-10-03
source: 0020_rich_parts
---

# Messaging: database

Status: tables and stream built (tasks 0001 and 0002), written by the code since task 0003.
Keys live in Terraform (`infra/stacks/backend/dynamo.tf`).

## Tables owned

| Table | Keys | Purpose |
|---|---|---|
| `rooms` | `customer_id`, `room_id` | One row per conversation; `delegated_to_human` silences Clara (set by hand until handoff exists); `turn_message_id` and `turn_started_at` mark the turn in progress and `turn_status` its latest status key; will hold the customer's rating (1 to 5) and optional comment. |
| `messages` | `customer_id`, `message_key` (`<room_id>#<sent_at>#<message_id>`) | Every message of every room, in order within a room. Stream: new image. |

Every message carries `sender_type`: `customer`, `assistant` or `agent`.
It is a contract with the infrastructure: the chatbot's stream mapping filters on it.
A message may carry `origin_trace_id`, the X-Ray root of the `POST /messages` that first stored it; a reply copies the one of the message it answers.
It exists only to link traces across the stream: it is absent when there was no trace, never returned by `public()` and never published to a channel.
A Clara reply also carries `parts` (public: rendered `say` parts with citation objects), and `facts` (the typed facts it referenced), `draft` (the parts before rendering) and `source` (`composed`, `repaired`, `fallback`, `safety`, `say_key`), kept for audit and never returned; `text` is the says joined, so readers that ignore `parts` still work.
A customer's tap carries `input` (`ask_id`, `option`), kept for the turn and never returned; the open ask is Clara's latest message, not a copy on the room.

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
- One turn per room at a time: `chatbot` takes the mark with a conditional update when it is absent, held by the same message, or older than 5 minutes, and clears it when the turn ends, also on failure; a fresh mark of another message makes the record retry.
- A redelivered customer message whose reply (its successor id) is already stored runs no second turn.
- Only the holder of the turn mark sets `turn_status`; taking or clearing the mark removes it.

## Migrations of note

- 2026-10-03 (task 0020): new optional attributes `input` on `messages` and `turn_status` on `rooms`; no migration.

- 2026-10-03 (task 0019): new optional attributes `parts`, `facts`, `draft`, `source` on `messages` and the turn mark on `rooms`; no migration, readers ignore unknown attributes.

- 2026-09-27 (task 0002): stream enabled on `messages`.
