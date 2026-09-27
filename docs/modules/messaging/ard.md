---
updated: 2026-09-27
source: setup
---

# Messaging: architecture decisions and debt

Status: designed, not built; entries below record decisions and open risks from the design, not debt from running code.

## 2026-09-27: the chatbot publishes to SQS instead of replying inline

- Decision: `lambdas/chatbot` (assistant) publishes the finished reply to an SQS queue rather than returning it in the API Gateway response; `lambdas/notifications` (this module) is the sole consumer.
- Alternatives rejected: a synchronous request/response held open until Claude composes the reply [inferido, the module brief frames the SQS hop as the fix for exactly this]; long-polling or a direct WebSocket connection from `lambdas/chatbot` itself [inferido].
- Reason: decouples LLM latency from the API Gateway timeout (module brief); a slow Bedrock call no longer risks failing the customer's turn on a gateway timeout.
- Debt created: none, deliberate.
- Revisit when: never, unless API Gateway's timeout budget or the LLM's latency profile changes enough to make a synchronous reply viable again.
- Source: setup

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

- Decision: `docs/tasks/_drafts/turn_flow.md` (intent, state, decision, 13 intents) governs the assistant's turn logic that produces the message this module carries; it does not govern messaging's transport. Compute stays lambdas, SQS and AppSync Events, not that document's ECS/SSE draft.
- Alternatives rejected: building messaging's delivery path around `turn_flow.md`'s ECS/SSE session model.
- Reason: settled explicitly (setup decision, 2026-09-27).
- Debt created: none.
- Revisit when: never, unless the compute shape is revisited.
- Source: setup

## 2026-09-27: a human agent's message takes the same write path as the bot's

- Decision: `lambdas/notifications` stays messaging's only writer; a human agent's message reaches it the same way a bot reply does, API -> SQS -> notifications.
- Alternatives rejected: `apps/support` writing directly to the `messages` table.
- Reason: settled explicitly (setup decision, 2026-09-27); one writer keeps ordering and any future idempotency in one place.
- Debt created: none.
- Revisit when: never, unless a second writer is deliberately introduced.
- Source: setup

## 2026-09-27: the customer's rating and comment are stored on the room

- Decision: the post-conversation rating (1 to 5, optional comment) is stored on the room, not on a separate feedback table.
- Alternatives rejected: a dedicated feedback table, the shape `docs/product/02-technical-flows.md` sketches ("Stored as feedback row linked to the conversation trace").
- Reason: settled explicitly (setup decision, 2026-09-27).
- Debt created: none.
- Revisit when: never, unless a rating needs to outlive or span rooms.
- Source: setup
