---
updated: 2026-09-27
source: setup
---

# Messaging: technical

Status: designed, not built.
Nothing under `lambdas/notifications` exists yet; this describes the agreed design, source `docs/tasks/_drafts/architecture_and_layout.md`, the module brief and the setup decisions of 2026-09-27.
Turn logic (intent, state, decision; 13 intents) follows `docs/tasks/_drafts/turn_flow.md`; compute stays lambdas, SQS and AppSync Events, not that draft's ECS/SSE shape (setup decision, 2026-09-27).

## Structure

| Path | What |
|---|---|
| `lambdas/notifications` | Python lambda, part of the `uv` workspace, bundles the shared `core` package; SQS-triggered consumer that writes the `rooms`/`messages` tables (2 of the 7 confirmed DynamoDB tables) and publishes to the room's AppSync Events channel; uses Lambda Powertools (Logger, Metrics, Tracer) and X-Ray tracing like every lambda (the setup decisions of 2026-09-27, points 1 and 7) [inferido: exact file layout] |
| SQS queue (name not decided) | Declared in Terraform, `infra/modules/aws/*`; `lambdas/chatbot` (assistant) publishes a bot's reply here, and a human agent's message reaches the same queue through some API Gateway route (setup decision, 2026-09-27); `lambdas/notifications` consumes it; per the "no lambda-to-lambda calls" decision no lambda calls another directly [architecture_and_layout.md] |
| AppSync Events API (name not decided) | One events API, one channel per room, per the confirmed architecture ("Realtime: AppSync Events API (pub/sub channels per room)"); `auvral/docs/modules/infra/trd.md` documents the same shape, one Events API per environment, as the style reference [inferido: whether this project needs more than one API or namespace] |

## Endpoints owned

None named yet.
setup decision, 2026-09-27 states a human agent's message travels API -> SQS -> notifications, which implies some API Gateway route publishes it to the queue; which lambda owns that route (a new one, or an existing one such as `lambdas/crud`) is not decided [inferido].

Jobs, listeners or scheduled work:
- `lambdas/notifications`, triggered by the SQS queue both `lambdas/chatbot` and the agent's message route publish to.

## Depends on

- assistant (`lambdas/chatbot`): publishes the finished, already-composed reply to SQS once a turn is decided; messaging only consumes, per the no-lambda-to-lambda-calls rule it never calls back into `chatbot` (`docs/tasks/_drafts/architecture_and_layout.md`).
- identity: owns the IAM roles that decide who may read or write `rooms`/`messages` (setup decision, 2026-09-27); the agent side is `role-agent`, scoped to the Cognito `agents` group on `support.factoredai.sdfles.com` (setup decision, 2026-09-27). The exact per-channel realtime authorization (a customer only their own room, an agent only an assigned room) is not designed yet [inferido].
- infra: declares the `rooms` and `messages` tables and the SQS queue; a separate seed process, owner not decided, loads them (setup decision, 2026-09-27).

## Depended on by

- assistant (`apps/customer`): the customer's chat SPA subscribes to its room's channel to receive Clara's replies without polling.
- cases (`apps/support`): the agent console joins the same room on handoff (`docs/product/01-flows.md` flow 2); `cases/trd.md` already names this dependency from its side.

## Configuration

Not designed yet.
By architecture pattern, expect the SQS queue URL, the AppSync Events API endpoint and the `rooms`/`messages` table names as environment variables set by Terraform, same as every other lambda [inferido].

## Testing

Not designed yet; no tests exist because no code exists.
