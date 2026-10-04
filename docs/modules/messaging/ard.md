---
updated: 2026-10-04
source: 0022_story_actions
---

# Messaging: architecture decisions and debt

Status: built for customers (task 0003).

## 2026-09-27: a message is written once and delivered from the table's stream

- Decision: `lambdas/messages` writes the message; the `messages` DynamoDB stream feeds two consumers, `chat-notifier` (push to the room's channel) and `chatbot` (reply); the reply is an ordinary message on the same path. Supersedes the SQS reply queue and `lambdas/notifications`.
- Alternatives rejected: chatbot publishing replies to SQS for a notifications lambda to write and push (a dual write that can lose a message); EventBridge fan-out (a second write, no order per room).
- Reason: the write and the event are one operation, order is kept per `customer_id`, and two consumers fit the recommended two readers per shard.
- Debt created: a third consumer has to go through EventBridge Pipes; a poison record blocks its customer's messages until three retries send it to the DLQ.
- Revisit when: a third reader of the stream is needed.
- Source: task 0002

## 2026-09-27: notifier and chatbot are separate stream consumers

- Decision: `chat-notifier` and `chatbot` each have their own mapping, retries and DLQ; the chatbot mapping only passes messages with `sender_type = customer`.
- Alternatives rejected: one consumer that pushes and answers.
- Reason: a Bedrock failure never blocks the push; each role holds only what it needs; Clara cannot answer herself.
- Debt created: none.
- Revisit when: never, unless the reply path changes.
- Source: task 0002

## 2026-09-27: realtime delivery is AppSync Events, not SSE or polling

- Decision: messaging pushes new messages to the client over an AppSync Events API, one channel per room; the SPAs subscribe over WebSocket.
- Alternatives rejected: SSE (`docs/product/03-architecture.md`, v1 2026-09-26, superseded); polling every 2 seconds (`docs/tasks/_drafts/turn_flow.md`, draft, superseded).
- Reason: arbitrated by Sebastian in the confirmed architecture (`docs/tasks/_drafts/architecture_and_layout.md`, Decided section): managed pub/sub over WebSocket without a GraphQL schema, no lambda holds a connection open.
- Debt created: none.
- Revisit when: never, unless AppSync Events itself is revisited.
- Source: setup

## 2026-09-27: rooms/messages is its own table set, separate from the case record

- Decision: messaging owns 2 of the 7 confirmed DynamoDB tables (`rooms`, `messages`), separate from `complaints` (the table the cases module treats as the case record) and from the customer, product, transaction and staff tables; a room's history exists independently of whether a complaint is ever opened.
- Alternatives rejected: storing chat history on the case record itself [inferido].
- Reason: the full table list is confirmed at 7 (`customers`, `products`, `transactions`, `complaints`, `staff`, `rooms`, `messages`), with no separate `cases` table, `cases` is a module name only (setup decision, 2026-09-27); also keeps the module boundary the brief states directly: "cases owns the case, messaging owns the chat transport and history".
- Debt created: none.
- Revisit when: never, unless the cases/messaging boundary itself is revisited.
- Source: setup

## 2026-09-27: turn logic follows turn_flow.md, compute follows the confirmed architecture

- Decision: `docs/tasks/_drafts/turn_flow.md` (intent, state, decision, 13 intents) governs the assistant's turn logic that produces the message this module carries; it does not govern messaging's transport. Compute stays lambdas, DynamoDB Streams and AppSync Events, not that document's ECS/SSE draft.
- Alternatives rejected: building messaging's delivery path around `turn_flow.md`'s ECS/SSE session model.
- Reason: settled explicitly (setup decision, 2026-09-27).
- Debt created: none.
- Revisit when: never, unless the compute shape is revisited.
- Source: setup

## 2026-09-27: a human agent's message takes the same write path as the bot's

- Decision: the messaging code in `lambdas/core` is the only writer of `messages`; an agent's message enters through `POST /messages` like a customer's, and Clara's reply goes through the same code.
- Alternatives rejected: `apps/support` writing the table directly.
- Reason: one writer keeps ordering and idempotency in one place.
- Debt created: none.
- Revisit when: never, unless a second writer is deliberately introduced.
- Source: setup, updated by task 0002

## 2026-09-27: the customer's rating and comment are stored on the room

- Decision: the post-conversation rating (1 to 5, optional comment) is stored on the room, not on a separate feedback table.
- Alternatives rejected: a dedicated feedback table, the shape `docs/product/02-technical-flows.md` sketches ("Stored as feedback row linked to the conversation trace").
- Reason: settled explicitly (setup decision, 2026-09-27).
- Debt created: none.
- Revisit when: never, unless a rating needs to outlive or span rooms.
- Source: setup

## 2026-09-27: a reply's id is the successor of the id it answers

- Decision: the chatbot's reply takes the answered message's UUIDv7 with its 74 random bits plus one, and the answered `sent_at`.
- Alternatives rejected: a UUIDv5 of the answered id (not a UUIDv7, sorts anywhere); the answered `sent_at` plus one millisecond (another message can share that millisecond).
- Reason: no id can sort between an integer and its successor, so the reply is always right after the message it answers, and a redelivered stream record computes the same key and hits the conditional write.
- Debt created: none; the successor overflows only when the random part is all ones (2^-74), and then the reply fails instead of misordering.
- Revisit when: a reply answers something other than one customer message.
- Source: 0003_walking_skeleton

## 2026-09-27: the customer API is send and latest room only

- Decision: `POST /messages` (201 new, 200 with the stored message on a retry, text trimmed and at most 2000 characters) and `GET /messages/rooms/latest`, which returns the whole room and `server_time`.
- Alternatives rejected: a history route per room with a cursor; returning 409 on a retried id.
- Reason: the customer app only reopens its latest room; a retry answering the stored message lets the client treat both answers as "sent".
- Debt created: history is not paginated, a very long room grows the response toward the 6 MB Lambda limit.
- Revisit when: the support app needs another room than the latest, or a room passes a few hundred messages.
- Source: 0003_walking_skeleton

## 2026-09-27: the client mints ids on server time and retries with the same id

- Decision: `server_time` from the latest-room call corrects the device clock before minting UUIDv7 ids; network, 429 and 5xx errors retry automatically with the same id; a manual retry reuses the id for 90 seconds, after that the failed bubble is dropped and the text is sent as a new message.
- Alternatives rejected: minting on the device clock (a skewed phone fails the 2 minute window on every send); always reusing the id (a late manual retry is rejected forever).
- Reason: the 2 minute window protects the key order; the client must stay inside it without the customer noticing.
- Debt created: none.
- Revisit when: the window changes.
- Source: 0003_walking_skeleton

## 2026-09-27: subscribe to all of the customer's rooms before reading history

- Decision: the customer app subscribes to `/rooms/{sub}/*`, waits for the subscription ack, then reads history; pushes, history and POST answers merge by `message_id`, and only the open room is shown.
- Alternatives rejected: reading history first (a reply written in between is lost); subscribing to the room channel (the room id is unknown until history answers, and a new room has none).
- Reason: nothing can fall between the history read and the live feed, and the order of arrival does not matter.
- Debt created: after the live connection drops the chat only shows a notice; it does not resubscribe and reread history on its own.
- Resolved by: 0022_story_actions, 2026-10-04
- Revisit when: customers report missing replies, or before the demo.
- Source: 0003_walking_skeleton

## 2026-09-27: no customer text in logs, traces or events

- Decision: handlers log ids only, Tracer never captures responses, `post_confirmation` logs the `sub` instead of the email, `turn.completed` carries ids and `trace_id`.
- Alternatives rejected: Powertools defaults, which put every handler response (the message text) in X-Ray metadata.
- Reason: text is customer data; it lives in `messages` under IAM isolation and nowhere else.
- Debt created: none.
- Revisit when: debugging needs text, which then goes through the table, not the logs.
- Source: 0003_walking_skeleton

## 2026-09-29: a message's traces are linked by an annotation, not by X-Ray

- Decision: `messages` stores the root of its trace as `origin_trace_id` on the message and annotates its own subsegment with it (on a retry, the stored value, so the retry joins the first trace's filter); `chatbot` and `chat-notifier` annotate the per-record subsegment, not the invocation segment, because a notifier batch mixes messages; the reply copies the answered message's value.
- Alternatives rejected: relying on X-Ray to link across the stream, which it does not; annotating only the two consumers, which leaves `messages` out of the one filter.
- Reason: one filter expression, `annotation.origin_trace_id = "<root>"`, returns every trace of a message, and only an id crosses the stream.
- Debt created: none.
- Revisit when: a consumer processes records in parallel, or a new stream consumer appears.
- Source: 0008_chat_latency

## 2026-09-29: Tracer patches botocore only; the AppSync publish has its own subsegment

- Decision: `core.observability` builds `Tracer(patch_modules=["botocore"])`, and `chat-notifier` wraps the publish in `capture_method` instead of relying on the `httplib` patch.
- Alternatives rejected: Powertools' default `patch_all`, which imports `requests` and `sqlite3` only to patch them (43 to 225 ms of init locally); patching `httplib` for the one HTTP call the code makes.
- Reason: init only pays for what the handler path uses, and the publish still shows as a named subsegment.
- Debt created: none.
- Revisit when: a lambda calls another HTTP service it needs traced.
- Source: 0008_chat_latency

## 2026-10-03: the room holds a turn mark, and a stored reply ends a redelivery

- Decision: before a turn `chatbot` checks for the reply's key (the successor id) and, if it exists, re-emits `turn.completed` with no model call; otherwise it takes `turn_message_id` and `turn_started_at` on the room with a conditional update (absent, same message, or older than 5 minutes) and clears them in a `finally`; it reads only the 6 messages before the current one, newest first.
- Alternatives rejected: Powertools Idempotency (an eighth table); relying on the reply's conditional write alone (a redelivery would pay a second model run before failing the write); reading the whole room for the context.
- Reason: a redelivered record never pays for a second turn, a record sent to the DLQ never blocks the customer's next message for more than 5 minutes, and the read's cost does not grow with the room.
- Debt created: none.
- Revisit when: a second writer of Clara's messages appears (the watcher, B5).
- Source: 0019_open_mode_graph

## 2026-10-03: what Clara is checking travels as ephemeral status events, and its latest key on the turn mark

- Decision: per tool round `chatbot` sets `turn_status` on the room (only while it holds the mark) and then publishes one event to the room's channel with its own role, keyed by the round's first tool family, id `<message_id>#<round>`; the publish has a 0.5 s budget and no retries, and neither step can fail or delay the turn beyond it. `GET /messages/rooms/latest` returns the fresh mark as `turn`. The client shows the latest round's key, drops it when the reply arrives or 30 s pass without news, and ignores a status for any message but the latest customer one.
- Alternatives rejected: status as messages (stored and filtered forever); a client guess from the send time alone (B1's 30 s window, which a reload could not correct).
- Reason: the customer sees what Clara reads while she reads it, a reload shows the same, and nothing is left to clean up.
- Debt created: none.
- Revisit when: the turn streams its `say` (each round would then also carry text).
- Source: 0020_rich_parts

## 2026-10-03: one AppSync publisher in core

- Decision: `core.realtime.Publisher` signs with the caller's own credentials and takes a total timeout and retry policy; `chat-notifier` keeps 5 s with urllib3's retries, `chatbot` uses 0.5 s without. `chatbot` gains `realtime_publish` and the realtime env.
- Alternatives rejected: a second publisher in `chatbot`; publishing status through `chat-notifier` (it only sees stored messages).
- Reason: one signer and one wire shape for every event on a room's channel.
- Debt created: none.
- Revisit when: a third publisher appears.
- Source: 0020_rich_parts

## 2026-10-03: a tap is an ordinary message with a validated `input`

- Decision: `POST /messages` accepts `input` with exactly `ask_id` (UUIDv7) and `option` (1 to 80 characters), stores it on the message and never returns or publishes it; the API stays send and latest room only, and the turn decides whether the tap is still valid.
- Alternatives rejected: an endpoint per action; validating the ask in the API (it would read the room's history on every send).
- Reason: every input is a message, so the turn stays the only reader of asks and the transcript shows what the customer chose.
- Debt created: none.
- Revisit when: B4 adds confirmations that write.
- Source: 0020_rich_parts

## 2026-10-04: the chat catches up on return, network back and channel errors, with backoff

- Decision: the customer app resubscribes and re-reads `GET /messages/rooms/latest` when the tab returns to the foreground, the network comes back or the channel errors, showing "Reconectando…"; after a channel error it waits 1 s, doubling to 30 s, and resets on a good read.
- Alternatives rejected: a notice asking for a reload (the customer misses Clara's reply); retrying a failing channel at once (a channel that errors right after subscribing loops).
- Reason: a backgrounded phone drops the WebSocket, and Clara's reply must still appear without a reload.
- Debt created: none.
- Revisit when: the chat moves to TanStack Query.
- Source: 0022_story_actions

## 2026-10-04: `input` carries a note or the bank's charge entry, and a write reply carries public `effects`

- Decision: `input` is a tap (`ask_id`, `option`, an optional `note` of at most 140 characters) or a `topic` (`type charge` with the card and the charge), each validated by shape in `messages` and by ownership in the turn; a reply that wrote something carries `effects` (`card_blocked {product_id}`, `case_opened {complaint_id, case_type}`, `charge_answered {transaction_id}`) on its public shape.
- Alternatives rejected: the client inferring what changed from the views it receives (a view is not a write); room state with the open ask (Clara's latest message already holds it).
- Reason: the client invalidates exactly the keys a write changed, as every web does for its own writes.
- Debt created: none.
- Revisit when: a write happens outside a reply (the watcher).
- Source: 0022_story_actions
