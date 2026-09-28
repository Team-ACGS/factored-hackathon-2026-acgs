---
updated: 2026-09-27
source: 0003_walking_skeleton
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

- Decision: the customer app subscribes to `/rooms/<sub>/*`, waits for the subscription ack, then reads history; pushes, history and POST answers merge by `message_id`, and only the open room is shown.
- Alternatives rejected: reading history first (a reply written in between is lost); subscribing to the room channel (the room id is unknown until history answers, and a new room has none).
- Reason: nothing can fall between the history read and the live feed, and the order of arrival does not matter.
- Debt created: after the live connection drops the chat only shows a notice; it does not resubscribe and reread history on its own.
- Revisit when: customers report missing replies, or before the demo.
- Source: 0003_walking_skeleton

## 2026-09-27: no customer text in logs, traces or events

- Decision: handlers log ids only, Tracer never captures responses, `post_confirmation` logs the `sub` instead of the email, `turn.completed` carries ids and `trace_id`.
- Alternatives rejected: Powertools defaults, which put every handler response (the message text) in X-Ray metadata.
- Reason: text is customer data; it lives in `messages` under IAM isolation and nowhere else.
- Debt created: none.
- Revisit when: debugging needs text, which then goes through the table, not the logs.
- Source: 0003_walking_skeleton
