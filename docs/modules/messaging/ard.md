---
updated: 2026-09-27
source: task 0002
---

# Messaging: architecture decisions and debt

Status: infrastructure built (task 0002), code not built.

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
