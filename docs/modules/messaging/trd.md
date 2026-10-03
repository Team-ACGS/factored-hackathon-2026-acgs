---
updated: 2026-10-03
source: 0019_open_mode_graph
---

# Messaging: technical

Status: built for customers (task 0003); agent sending comes with the support app. The customer chat talks to it through `apps/customer/src/chat/live.ts` (task 0019); Clara's replies carry `parts`.

## Structure

| Path | What |
|---|---|
| `lambdas/messages` | API lambda behind `/messages/*`. Accepts only `customers` pool tokens (403 otherwise) and assumes `role-customer` tagged with the token's `sub`. |
| `lambdas/chat_notifier` | Consumer of the `messages` stream (inserts): publishes each new message to its room's AppSync Events channel. It can read the stream and publish, nothing else. |
| `core.messaging` in `lambdas/core` | The only code that writes `messages` and `rooms`: validates ids and text, derives reply ids, conditional writes, the room's turn mark, and the bounded read of the messages before a given one. |
| AppSync Events API `clara-prd` | Namespace `rooms`, one channel per room: `/rooms/{customer_id}/{room_id}`. Publishing is IAM only (SigV4 from `chat-notifier`). Subscribing takes a Cognito token; the namespace's `onSubscribe` handler (`infra/stacks/backend/handlers/rooms.js`) rejects a customer whose `sub` differs from the `customer_id` segment and lets staff tokens through; the customer app subscribes to `/rooms/{sub}/*`. |

## Endpoints owned

- `POST /messages`: send a message with a client-minted `room_id` and `message_id`; creates the room with the first message; 201 when stored, 200 with the stored message on a retry, 400 when the id is more than 2 minutes from server time or the text is empty or over 2000 characters.
- `GET /messages/rooms/latest`: the customer's latest room, its whole history in order, and `server_time` for the client clock.

A message's public shape adds `parts` when Clara wrote it (`say` parts with their citations); `facts`, `draft` and `source` stay on the item and are never returned or published.

No generated API spec yet.

Both sit behind the API's Cognito authorizer (both pools) on `api.factoredai.sdfles.com`.

Jobs and listeners:

- `chat-notifier` on the `messages` stream, inserts only, batch 10.
- `chatbot` (assistant) on the same stream, inserts whose `sender_type` is `customer` only, batch 1.
- Both mappings: parallelization 10 (order kept per `customer_id`), 3 retries, bisect on error, an SQS DLQ each (`clara-prd-chat-notifier-dlq`, `clara-prd-chatbot-dlq`).

## Depends on

- identity: `role-customer` and `role-agent` write `messages` and `rooms`; `role-customer` only for the caller's own `customer_id`.
- infra: the tables, the stream, the mappings and the DLQs are in `infra/stacks/backend/` (`dynamo.tf`, `streams.tf`).

## Depended on by

- assistant: `chatbot` is triggered by customer messages and writes its reply as an ordinary message through the same messaging code, assuming `role-customer` with the record's `customer_id`.
- `apps/customer` and `apps/support`: send through `/messages`, subscribe to the room's channel.

## Configuration

- `messages`: `TABLE_ROOMS`, `TABLE_MESSAGES`, `ROLE_CUSTOMER_ARN`, `CUSTOMERS_POOL_ID`, `STAFF_POOL_ID`.
- `chat-notifier`: `REALTIME_HTTP_URL`, `REALTIME_NAMESPACE`.

## Latency and tracing

Measured on `prd` on 2026-09-29, before the credentials cache of task 0008, with the three chat functions at 1024 MB x86_64 (probe and queries in the docs root, `docs/tasks/0008_chat_latency/`).
Warm p50 from send to Clara's echo on screen: 1728 ms; cold: 4995 ms.
Handlers warm: `messages` 332 ms, `chatbot` 366 ms, `chat-notifier` 255 ms; cold init about 1 s each.
Outside the code: each stream hop waits 140 to 310 ms warm and up to 1 s cold (DynamoDB Streams polling), and the browser's edges (network, API Gateway with its authorizer, AppSync delivery) add about 400 ms.
Targets: delivery (a message stored to it on screen, without the turn) under 1 s warm and 3 s cold; a Clara reply to an open question p50 under 5 s and p95 under 9 s from send, within the turn's 12 s cap.
The real turn's cold and warm latency on `prd` are measured after task 0019 merges; locally against the model a turn took 4.7 s to 7.2 s (assistant/trd.md).

A message yields three traces, because X-Ray does not follow DynamoDB Streams.
`messages` stores its trace root as `origin_trace_id` on the item and annotates it; `chatbot` and `chat-notifier` annotate each record's subsegment with the same value, and the reply carries it to its own notifier trace.
One filter expression returns them all: `annotation.origin_trace_id = "<root>"`.
Only the id travels, never text.

## Testing

- `lambdas/tests/` on moto: `core/test_messaging.py`, `messages/`, `chat_notifier/`, and `test_round_trip.py`, which sends through the API, replays the stream into `chatbot` and `chat-notifier`, and checks retries, order and the absence of a loop.
- `apps/customer/src/chat/*.test.ts`: the conversation reducer (pending, sent, dedupe by `message_id`), the API retries and the clock.
- Commands: `docs/TRD.md`, Verification targets.
