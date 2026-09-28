---
updated: 2026-09-27
source: task 0002
---

# assistant: technical

Status: designed, not built.
The turn flow described here is the design in `docs/tasks/_drafts/turn_flow.md` (2026-09-27), which supersedes the black box A section of `docs/product/02-technical-flows.md` (2026-09-26) where they differ, in particular the tool names and the step count.
Both documents describe the same shape: ingress checks, intent understanding, tool retrieval, a rules-table decision, an act step for writes, an LLM composer, and an egress grounding check.
See `docs/tasks/_drafts/turn_flow.md` for the current diagram, the intent list, the state machine, the decision table and the tool table; this file does not restate them.

## Structure

Planned, none of these paths exist yet.

| Path | What |
|---|---|
| `lambdas/chatbot/` | Turn handler triggered by the `messages` stream (customer messages only): ingress, understand, retrieve, decide, act, compose, egress, then writes the reply as a message [inferido: exact file layout] |
| `lambdas/core/` | Shared package bundled into `chatbot` and other lambda zips: policy table, state machine, tool clients, grounding check, contact digest; per the "no lambda-to-lambda calls" decision in `docs/tasks/_drafts/architecture_and_layout.md` |
| `apps/customer/` | Chat SPA at `factoredai.sdfles.com`, part of the `apps/` pnpm workspace (React, Vite, TanStack Router) |

## Endpoints owned

None: a customer message enters through messaging's `POST /messages`.

Jobs and listeners: `chatbot` consumes the `messages` stream, only inserts with `sender_type = customer`, batch 1, 3 retries, bisect on error, DLQ `clara-prd-chatbot-dlq`; it skips rooms delegated to a human.

## Depends on

- identity: customer login is Cognito email and password; the sign-up email OTP is only a one-time verification code, never a chat step-up. Identity owns the IAM roles that decide who may do what on the DynamoDB tables; this module only assumes `role-customer`.
- DynamoDB tables `customers`, `products`, `transactions` (PK `customer_id`), read through `role-customer` via STS AssumeRole with a `customer_id` session tag; `infra/` defines the tables, a separate seed process loads them (owner not decided).
- DynamoDB table `complaints` (PK `customer_id`, GSI by area and priority): this table is the case record, historical and new; this module reads it through Q5 and writes to it only through the `A2 create complaint` and `A3 withdraw complaint` tools, which call the cases module's write code inside the shared `lambdas/core` package (the same code path `lambdas/crud` uses), never another lambda.
- models: the injection detector and intent router (multilingual e5 + logistic regression), loaded as versioned S3 artifacts; serving is not in `infra/` yet.
- Bedrock Claude Sonnet 5 (low effort) for slot extraction and for the composer; no Titan, Grok or Haiku unless a measured need is shown.
- messaging: the reply is written as an ordinary message (`sender_type = assistant`) through the messaging code in `lambdas/core`, assuming `role-customer` with the stream record's `customer_id`; `chat-notifier` pushes it. On handoff the room is marked delegated and Clara stays silent.
- Observability: every lambda uses AWS Lambda Powertools for Python (Logger, Metrics, Tracer); the block-card and create-complaint writes are idempotent through conditional writes on deterministic ids; CloudWatch Logs (structured JSON) and EMF metrics in namespaces `Clara/Backend` and `Clara/Assistant`; X-Ray active tracing.
- EventBridge bus `clara-prd`: `lambdas/chatbot` calls PutEvents once at the end of every turn with ids and a `trace_id` only, never message text; events flow through Firehose to S3. Analysis of these events and the offline LLM judge are deferred.
- legal deadlines: `hackathon/docs/domain/legal-deadlines.md` is cited from memory and explicitly unverified as of 2026-09-26; any due date the composer states depends on that table becoming verified before it reaches a real reply.

## Depended on by

- cases: consumes the structured handoff package (verified facts, actions with read-back, evidence, open questions, data warnings) produced on `HANDOFF`, `CLAIM` and `PROTECT`, and owns the `complaints` table this module reads and writes through tools.
- evaluation: the offline judge and the held-out harness run against this module's traces and outputs.

## Configuration

- EventBridge bus name `clara`: target of the end-of-turn PutEvents call.
- Metrics namespace `Clara/Assistant` (and the shared `Clara/Backend`) for EMF metrics.
- No other env vars are named in any source yet. [inferido]

## Testing

Not built yet.
`docs/problem-statement.md` (H1-H5) and `hackathon/docs/kickoff-compliance.md` name a baseline comparison (rules bot, naive LLM) and a held-out evaluation as required, owned operationally by `evaluation/`, exercising this module as a whole.
