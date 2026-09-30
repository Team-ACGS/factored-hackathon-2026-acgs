---
updated: 2026-09-29
source: 0010_customer_redesign
---

# assistant: technical

Status: walking skeleton (task 0003) plus the customer's own data (task 0006); the turn below is designed, not built.
The turn flow described here is the design in `docs/tasks/_drafts/turn_flow.md` (2026-09-27), which supersedes the black box A section of `docs/product/02-technical-flows.md` (2026-09-26) where they differ, in particular the tool names and the step count.
Both documents describe the same shape: ingress checks, intent understanding, tool retrieval, a rules-table decision, an act step for writes, an LLM composer, and an egress grounding check.
See `docs/tasks/_drafts/turn_flow.md` for the current diagram, the intent list, the state machine, the decision table and the tool table; this file does not restate them.

## Structure

Built as a skeleton in task 0003; the turn steps are still planned.

| Path | What |
|---|---|
| `lambdas/chatbot/` | Stream consumer: skips non-customer messages and delegated rooms, writes the reply through `core.messaging`, emits `turn.completed`, reports failed records one by one. Today the reply is an echo; the turn (ingress, understand, retrieve, decide, act, compose, egress) replaces it. |
| `lambdas/crud/` | The customer's own data behind `/crud/*`: profile and one-time setup, cards, transactions; the generator (`catalog.py`, `generator.py`) builds a demo account deterministically from the setup claim. |
| `lambdas/core/` | Shared package bundled into every lambda zip: today the read models every reader of customer data must use (`core.accounts` for cards and transactions, `core.customers` for the profile, each an attribute allow-list); later the policy table, state machine, tool clients, grounding check and contact digest. |
| `apps/customer/` | SPA at `factoredai.sdfles.com` (React, Vite, TanStack Router, TanStack Query, Amplify v6): auth, setup, the bank shell in `src/bank` (home, card movements, help and claims, sheets; server data only through `src/bank/queries.ts`), Clara in `src/clara` (button, launcher, entry points, the session store in `sessionStorage` that the bank pages overlay, the seeded claim) and the chat in `src/clara/chat` (pure engine, triage, lexicon, bar and references, plus the page, panel and views). The chat consumes one contract with two implementations picked by `src/clara/switch.ts`: the mock engine, and `src/chat/live.ts`, today's text path (`/messages` plus AppSync) adapted to it. Text from typed catalogs in `src/i18n/`. |
| `apps/ui/` | Shared Tailwind theme, self-hosted fonts (`@fontsource`: Hanken Grotesk, Newsreader, IBM Plex Mono), shadcn/ui components, and Clara's entity: pure geometry in `src/lib/entity.ts` (palette, nine states, sampled outlines, faces, interpolation) and `ClaraEntity` / `ClaraGlyph` in `src/components/clara-entity.tsx`, morphed by one JS interpolation path in every browser. |

## Endpoints owned

A customer message enters through messaging's `POST /messages`.
`crud` serves the customer's own data, customer tokens only (staff get 403), every access under `role-customer` tagged with the token's `sub`; there is no generated API spec yet.

- `GET /crud/profile`: country, language and whether setup is done.
- `POST /crud/profile/setup`: create the demo account once (201 with the planted cases, 409 afterwards).
- `GET /crud/cards`: the customer's cards.
- `GET /crud/cards/{product_id}`: one card and a page of its transactions, newest first, with an opaque `next_cursor` and `server_time`.
- `GET /crud/cards/{product_id}/transactions/{transaction_id}`: one transaction.
- `POST /crud/cards/{product_id}/transactions`: add a normal or suspicious transaction with a client-minted UUIDv7, idempotent.

Jobs and listeners: `chatbot` consumes the `messages` stream, only inserts with `sender_type = customer`, batch 1, 3 retries, bisect on error, DLQ `clara-prd-chatbot-dlq`; it skips rooms delegated to a human.

## Depends on

- identity: customer login is Cognito email and password; the sign-up email OTP is only a one-time verification code, never a chat step-up. Identity owns the IAM roles that decide who may do what on the DynamoDB tables; this module only assumes `role-customer`.
- DynamoDB tables `customers`, `products`, `transactions` (PK `customer_id`), read and written through `role-customer` via STS AssumeRole with a `customer_id` session tag; `crud` setup seeds them per demo customer, a seed from the dataset is not built.
- DynamoDB table `complaints` (PK `customer_id`, GSI by area and priority): this table is the case record, historical and new; this module reads it through Q5 and writes to it only through the `A2 create complaint` and `A3 withdraw complaint` tools, which call the cases module's write code inside the shared `lambdas/core` package (the same code path `lambdas/crud` uses), never another lambda.
- models: the injection detector and intent router (multilingual e5 + logistic regression), loaded as versioned S3 artifacts; serving is not in `infra/` yet.
- Bedrock Claude Sonnet 5 (low effort) for slot extraction and for the composer; no Titan, Grok or Haiku unless a measured need is shown.
- messaging: the reply is written as an ordinary message (`sender_type = assistant`) through the messaging code in `lambdas/core`, assuming `role-customer` with the stream record's `customer_id`; `chat-notifier` pushes it. On handoff the room is marked delegated and Clara stays silent.
- Observability: every lambda uses AWS Lambda Powertools for Python (Logger, Metrics, Tracer); the block-card and create-complaint writes are idempotent through conditional writes on deterministic ids; CloudWatch Logs (structured JSON) and EMF metrics in namespaces `Clara/Backend` and `Clara/Assistant`; X-Ray active tracing, and `chatbot` annotates each record with the message's `origin_trace_id` (messaging `trd.md`, Latency and tracing).
- EventBridge bus `clara-prd`: `lambdas/chatbot` calls PutEvents once at the end of every turn with ids and a `trace_id` only, never message text; events flow through Firehose to S3. Analysis of these events and the offline LLM judge are deferred.
- legal deadlines: `hackathon/docs/domain/legal-deadlines.md` is cited from memory and explicitly unverified as of 2026-09-26; any due date the composer states depends on that table becoming verified before it reaches a real reply.

## Depended on by

- cases: consumes the structured handoff package (verified facts, actions with read-back, evidence, open questions, data warnings) produced on `HANDOFF`, `CLAIM` and `PROTECT`, and owns the `complaints` table this module reads and writes through tools.
- evaluation: the offline judge and the held-out harness run against this module's traces and outputs.

## Configuration

- `chatbot`: `EVENT_BUS_NAME` (`clara-prd`) and `EVENT_SOURCE` (`clara.chatbot`) for `turn.completed`, `ROLE_CUSTOMER_ARN`, the table names, `BEDROCK_MODEL_ID` (unused until the turn lands).
- `crud`: `ROLE_CUSTOMER_ARN`, the pool ids and the table names from Terraform's request environment.
- `apps/customer`: the `VITE_` variables of the `customer-prd` Actions environment, baked in at build time.
- Metrics namespace `Clara/Assistant` (and the shared `Clara/Backend`) for EMF metrics.

## Testing

- `lambdas/tests/chatbot/`: echo placement, delegated rooms, no loop, redelivery, `turn.completed` without text, partial batch failures.
- `lambdas/tests/crud/`: the generated account (counts, status mix, merchant minimums, planted cases, determinism per country), first, second, resumed and concurrent setup, paging and cursor tampering, cross-customer reads, adds and suffix uniqueness, staff 403, and no hidden attribute in any response; `lambdas/tests/core/` proves the read models drop them.
- `apps/customer`: `vitest` in node on `*.test.ts`: the locale store and catalogs (no "fraud" in Clara's text, no due date or legal term), the bank API client, money formatting and the bank queries against a real `QueryClient`; the Clara session, overlay, seeded claim and topics; the mock chat's triage precedence, typed answers, and engine flows (flagged charge to block and handoff, claim with the one question, lost card, confirmation before any action, a queue that never drops, references reopening with current state, gap cases, reload mid-write, reset). Screens have no tests; Sebastian validates the UI on the PR.
- `apps/ui`: `vitest` on the entity geometry (states, outlines, interpolation).
- Commands: `docs/TRD.md`, Verification targets.
`docs/problem-statement.md` (H1-H5) and `hackathon/docs/kickoff-compliance.md` name a baseline comparison (rules bot, naive LLM) and a held-out evaluation as required, owned operationally by `evaluation/`, exercising this module as a whole.
