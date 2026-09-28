---
updated: 2026-09-27
source: 0003_walking_skeleton
---

# Messaging: technical

Status: built for customers (task 0003); agent sending comes with the support app.

## Structure

| Path | What |
|---|---|
| `lambdas/messages` | API lambda behind `/messages/*`. Accepts only `customers` pool tokens (403 otherwise) and assumes `role-customer` tagged with the token's `sub`. |
| `lambdas/chat_notifier` | Consumer of the `messages` stream (inserts): publishes each new message to its room's AppSync Events channel. It can read the stream and publish, nothing else. |
| `core.messaging` in `lambdas/core` | The only code that writes `messages` and `rooms`: validates ids and text, derives reply ids, conditional writes. |
| AppSync Events API `clara-prd` | Namespace `rooms`, one channel per room: `/rooms/{customer_id}/{room_id}`. Publishing is IAM only (SigV4 from `chat-notifier`). Subscribing takes a Cognito token; the namespace's `onSubscribe` handler (`infra/stacks/backend/handlers/rooms.js`) rejects a customer whose `sub` differs from the `customer_id` segment and lets staff tokens through; the customer app subscribes to `/rooms/{sub}/*`. |

## Endpoints owned

- `POST /messages`: send a message with a client-minted `room_id` and `message_id`; creates the room with the first message; 201 when stored, 200 with the stored message on a retry, 400 when the id is more than 2 minutes from server time or the text is empty or over 2000 characters.
- `GET /messages/rooms/latest`: the customer's latest room, its whole history in order, and `server_time` for the client clock.

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

## Testing

- `lambdas/tests/` on moto: `core/test_messaging.py`, `messages/`, `chat_notifier/`, and `test_round_trip.py`, which sends through the API, replays the stream into `chatbot` and `chat-notifier`, and checks retries, order and the absence of a loop.
- `apps/customer/src/chat/*.test.ts`: the conversation reducer (pending, sent, dedupe by `message_id`), the API retries and the clock.
- Commands: `docs/TRD.md`, Verification targets.
