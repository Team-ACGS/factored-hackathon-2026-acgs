---
updated: 2026-09-27
source: task 0002
---

# Messaging: technical

Status: infrastructure built (task 0002), code not built.

## Structure

| Path | What |
|---|---|
| `lambdas/messages` | API lambda behind `/messages/*`: writes a message (and the room when it is new) through the messaging code in `core`, and reads a room's history. Assumes `role-customer` for a customer token and `role-agent` for an agent token. |
| `lambdas/chat_notifier` | Consumer of the `messages` stream (inserts): publishes each new message to its room's AppSync Events channel. It can read the stream and publish, nothing else. |
| messaging code in `lambdas/core` | The only code that writes `messages` and `rooms`, with conditional writes on deterministic ids. |
| AppSync Events API `clara-prd` | Namespace `rooms`, one channel per room: `/rooms/<room_id>`. Publishing is IAM only; subscribing takes a Cognito id token from either pool. |

## Endpoints owned

- `POST /messages`: send a message to a room, creating the room with the first message.
- `GET /messages/...`: a room's history in order (exact path set by the code).

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

- `messages`: the table names, `ROLE_CUSTOMER_ARN`, `ROLE_AGENT_ARN`, pool and client ids.
- `chat-notifier`: `REALTIME_HTTP_URL`, `REALTIME_NAMESPACE`.

## Testing

No code yet.
