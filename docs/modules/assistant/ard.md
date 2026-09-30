---
updated: 2026-09-29
source: 0009_client_data_cache
---

# assistant: architecture and debt

## 2026-09-26: split the turn into seven staged concerns

- Decision: the turn is staged as ingress, understand, retrieve, decide, act, compose, egress, each owning one concern (what the customer said, where the conversation is, what the system chooses).
- Alternatives rejected: an earlier sketch collapsed everything into ingress validation, a single agent step, and egress validation.
- Reason: the collapsed sketch let intent, dialogue state and the final decision live inside one opaque "agent" step; separating them lets the decision be a versioned, auditable rules table instead of a model's judgement call [inferido].
- Debt created: none.
- Revisit when: the turn flow moves from `docs/tasks/_drafts/turn_flow.md` into this module's TRD as the current design.
- Source: docs/tasks/_drafts/turn_flow.md

## 2026-09-26: verify before composing, not after

- Decision: writes are confirmed and read back, and tool output passes the injection detector, before the composer ever runs; the composer receives only the decision and already-verified facts.
- Alternatives rejected: the first sketch verified after the reply was composed.
- Reason: verifying after composing means a reply can already claim something that did not happen; verifying first makes that structurally impossible rather than caught after the fact.
- Debt created: none.
- Revisit when: never, this is treated as a hard invariant of the turn.
- Source: docs/tasks/_drafts/turn_flow.md ("What the first sketch was minimizing")

## 2026-09-26: injection detector runs on tool outputs, not only on the customer message

- Decision: the retrieve stage runs the injection detector a second time, on tool outputs such as `merchant_name` and case text.
- Alternatives rejected: checking only the inbound customer message, as in the first sketch and in `docs/product/02-technical-flows.md`'s black box A (superseded on this point).
- Reason: tool outputs come from the customer's own records but are still attacker-reachable text (a merchant name, a stored case note), so they carry the same risk class as the message.
- Debt created: no adversarial fixture for tool-output injection exists yet to validate this in practice. [inferido]
- Revisit when: the held-out adversarial set (`hackathon/docs/kickoff-compliance.md`, "Measured failures") is built.
- Source: docs/tasks/_drafts/turn_flow.md

## 2026-09-26: writes require confirmation and idempotency before a read-back-confirmed disclosure

- Decision: any write (block a card, open or withdraw a claim) needs explicit customer confirmation and an idempotency key, and the customer is only told it happened after a read-back confirms it. Customer login is Cognito email and password; there is no OTP step-up inside the chat, the email OTP exists only as the sign-up verification code.
- Alternatives rejected: the first sketch had no confirmation, idempotency or read-back step at all; an OTP step-up before each write was considered and dropped.
- Reason: without confirmation, idempotency and read-back, a retry can double-block or double-file, and a failed write can still be announced as successful. [inferido]
- Debt created: none.
- Revisit when: not specified.
- Source: docs/tasks/_drafts/turn_flow.md; docs/product/02-technical-flows.md ("Writes with confirmation and read-back")

## 2026-09-26: intent classes trimmed to keep intent, state and decision separate

- Decision: the intent list drops per-detail variants, dialogue-state labels and decision labels that an earlier fourteen-class list mixed in with true intents.
- Alternatives rejected: `*_DETAILS` as separate classes, `UNRECOGNIZED_TRANSACTION_CONFIRMED` and `UNRECOGNIZED_TREATMENT` as intents, `CREATE_COMPLAINT` and `BLOCK_PRODUCT` as intents.
- Reason: fourteen classes were too many for the available 600 labeled examples and mixed three different levels; a detail is a slot on the parent intent, a confirmation state belongs to the state machine, and an action belongs to the policy table, not to what the router predicts.
- Debt created: none; this reshapes the training set boundary between this module's understand stage and the models module, not yet reconciled in either module's docs. [inferido]
- Revisit when: the models module's trd.md is written and the router's exact class list is confirmed against this one.
- Source: docs/tasks/_drafts/turn_flow.md

## 2026-09-27: per-request STS AssumeRole with a session-tagged role, not a Cognito Identity Pool

- Decision: the module's DynamoDB access assumes `role-customer` per request via STS AssumeRole with a `customer_id` session tag and a `LeadingKeys` policy; the lambda itself never holds table-read permissions.
- Alternatives rejected: a Cognito Identity Pool mapping groups to IAM roles directly.
- Reason: keeps the isolation proof explicit and demonstrable (an AssumeRole call and a deny in the log), per `docs/tasks/_drafts/architecture_and_layout.md`, "Decided" section.
- Debt created: none noted.
- Revisit when: not specified.
- Source: docs/tasks/_drafts/architecture_and_layout.md

## 2026-09-27: Claude Sonnet 5 on Bedrock only, for extraction and composition

- Decision: this module calls Claude Sonnet 5 (low effort) for slot extraction and for the composer, and for nothing else; Haiku 4.5 only if a measured cost or latency problem requires it.
- Alternatives rejected: Titan and Grok in the runtime path (Manager's recommendations, before the 2026-09-27 decision); the mixed Haiku/Sonnet/Opus roster of the earlier, superseded `docs/product/03-architecture.md`.
- Reason: a single model reduces variance for the held-out evaluation and keeps cost and latency easy to reason about within the hackathon's budget. [inferido]
- Debt created: none.
- Revisit when: a measured cost or latency need appears.
- Source: docs/tasks/_drafts/architecture_and_layout.md

## 2026-09-26: legal due dates depend on an unverified deadline table

- Decision: the CLAIM outcome states a legal due date computed from a per-country deadline table.
- Alternatives rejected: none recorded; this is the only design.
- Reason: the bank must quote the correct country-specific deadline or none at all, since Mexico, Colombia and Argentina all give different windows.
- Debt created: `hackathon/docs/domain/legal-deadlines.md` is cited from memory as of 2026-09-26 and explicitly not verified against the primary legal texts; the doc itself names a "Day-1 task" to verify every row and build a `legal_deadlines.yaml` before this reaches a real reply.
- Revisit when: the deadline table is verified against primary sources, before this module composes a real customer-facing due date.
- Source: hackathon/docs/domain/legal-deadlines.md

## 2026-09-27: complaints table is the case record, no separate cases table

- Decision: DynamoDB has exactly the tables `customers`, `products`, `transactions`, `complaints` (PK `customer_id`, GSI by area and priority), `staff`, `rooms`, `messages`. `complaints` holds both historical rows and every case this module opens; there is no separate `cases` table and no `users` table. `cases` names the module that owns the write logic on `complaints`, not a table.
- Alternatives rejected: a dedicated `cases` table distinct from `complaints`.
- Reason: not recorded beyond the decision itself.
- Debt created: none.
- Revisit when: not specified.
- Source: setup, round 2

## 2026-09-27: observability from day one, analysis deferred

- Decision: every lambda uses AWS Lambda Powertools for Python (Logger, Metrics, Tracer), CloudWatch Logs in structured JSON, EMF metrics in namespaces `Clara/Backend` and `Clara/Assistant`, and X-Ray active tracing; the block-card and create-complaint writes are idempotent through conditional writes, not Powertools Idempotency; `lambdas/chatbot` also calls EventBridge PutEvents once per turn onto bus `clara-prd` with ids and a `trace_id`, never message text.
- Alternatives rejected: none recorded.
- Reason: not recorded beyond the decision itself.
- Debt created: analysis of the emitted turn events and the offline LLM judge are both deferred past this decision; see `docs/tasks/_drafts/turn_events_analysis.md`.
- Revisit when: turn event analysis and the offline judge are scoped.
- Source: setup, round 2

## 2026-09-27: module is design only, nothing built

- Decision: `lambdas/chatbot`, `lambdas/core` and `apps/customer` are the agreed code locations for this module, but none exist yet; only `hackathon/data/` is built in this repo.
- Alternatives rejected: none, this entry records status rather than a choice.
- Reason: confirmed by directory listing of the hackathon repo at setup time.
- Debt created: the whole module is design debt rather than implementation debt: reliability primitives (bounded retries, a fallback template, a tool-down fixture) are designed but unproven, and `hackathon/docs/kickoff-compliance.md` names reliability as the piece most likely to slip; the dataset also bounds explain-only resolution to 4.5-8% of cases, so the evaluation story should lead with zero unsafe outcomes rather than an automation rate; Portuguese coverage is entirely team-generated test data with no real examples and no Portuguese-speaking night-shift fraud agent to hand a PROTECT case to.
- Revisit when: the first implementation round for this module begins.
- Source: hackathon/docs/kickoff-compliance.md ("Where the proposal is weak"); docs/problem-statement.md sections 4.5-4.6

## 2026-09-27: turn.completed is emitted at least once

- Decision: `chatbot` emits `turn.completed` after the reply's conditional write, also when a redelivered record finds the reply already written; detail carries `customer_id`, `room_id`, `message_id`, `reply_message_id` and `trace_id`.
- Alternatives rejected: emitting only on the first write (a failure between write and PutEvents loses the event forever).
- Reason: losing a turn is worse than counting it twice, and `reply_message_id` is a natural dedupe key.
- Debt created: the event stream in S3 can hold duplicates; the analysis must dedupe by `reply_message_id`.
- Revisit when: turn events are analyzed.
- Source: 0003_walking_skeleton

## 2026-09-27: a customer message whose room does not exist fails the record

- Decision: `chatbot` raises when the room of a customer message is missing, so the record retries and lands in `clara-prd-chatbot-dlq`.
- Alternatives rejected: skipping the message silently.
- Reason: `core.messaging` writes the room before the message, so a missing room is a bug worth seeing in the DLQ, not a case to answer.
- Debt created: none.
- Revisit when: rooms can be deleted.
- Source: 0003_walking_skeleton

## 2026-09-27: customer app text from typed catalogs, not i18next

- Decision: `apps/customer/src/i18n/`: `en.ts` defines the keys, `es.ts` and `pt-BR.ts` must provide every one (checked by `tsc`), `{name}` placeholders; the locale comes from the browser once, English when nothing matches.
- Alternatives rejected: i18next with a language detector.
- Reason: three fixed languages and no plurals yet; the compiler already rejects a missing translation.
- Debt created: none.
- Revisit when: plurals, a language switcher or translated server text appear.
- Source: 0003_walking_skeleton

## 2026-09-27: web deploy replaces the site in place

- Decision: `deploy-customer.yml` builds with the Actions environment's `VITE_` variables, syncs hashed assets with `immutable` caching and `--delete`, uploads `index.html` with `no-cache` last, and waits for a `/*` invalidation; Vite splits Amplify and React into their own chunks.
- Alternatives rejected: keeping old assets forever; versioned prefixes per deploy.
- Reason: the plan asks for `s3 sync --delete`; hashed names make long caching safe and `index.html` always points at the new build.
- Debt created: none while every chunk loads with `index.html`; once routes are lazy-loaded, a tab on the previous build fails to load a deleted chunk until it reloads.
- Revisit when: the app lazy-loads routes.
- Source: 0003_walking_skeleton

## 2026-09-28: the customer chooses the language, the profile keeps it

- Decision: the signed-out screens offer a language picker (browser language by default, remembered in `localStorage` for signed-out screens only); sign-up stores it as the Cognito `locale`; the setup dialog defaults to that `locale` and switches the app live; after setup the profile's `language` drives the app through a runtime store (`src/i18n/store.ts`). This supersedes "the locale comes from the browser once" of 2026-09-27.
- Alternatives rejected: keeping the browser locale (a tester cannot try another language); a switcher on every screen.
- Reason: the language is the customer's choice, and the same value drives Cognito's emails, the app and later Clara's replies.
- Debt created: none.
- Revisit when: the customer needs to change language after setup.
- Source: 0006_customer_data_onboarding

## 2026-09-28: transaction ids are UUIDv7 and carry their date

- Decision: `product_id` and `transaction_id` are UUIDv7; `transaction_date` is the id's instant, so `transaction_key` is computed from `(product_id, transaction_id)`; the page cursor is the base64url of a transaction key and is accepted only if it equals the key recomputed for the requested card.
- Alternatives rejected: random ids with a stored date (the detail route would need the date or a scan); a signed cursor (the key is already confined to the caller's partition by IAM).
- Reason: one card reads newest first with a Query, the detail is a GetItem, and a forged or foreign cursor is a 400 by construction.
- Debt created: none.
- Revisit when: a transaction's date must differ from its creation instant, such as a dataset seed.
- Source: 0006_customer_data_onboarding

## 2026-09-28: the demo account follows the dataset, with fixed planted cases

- Decision: rows use the dataset's vocabulary (`Tarjeta Crédito`, `Approved`, `POS`, response codes `00` or `05/14/51/54`), ISO country codes, and Decimal money returned as strings; every card holds exactly 92 Approved, 5 Declined, 2 Pending and 1 Reversed; the fresh hold (fuel, 1 to 3 days), the reversed charge (retail) and the stale pending (delivery) sit on the three different cards; subscriptions get exactly the 4-charge minimum at a fixed amount; the account is derived from `sha256(customer_id | setup_claimed_at)` and a resumed setup keeps the first claim's country and language.
- Alternatives rejected: approximate proportions (tests could not pin the mix); all cases on one card.
- Reason: the tools and a future dataset seed share one vocabulary, the demo is reproducible, and each planted case is findable from the guide.
- Debt created: balances are a setup snapshot (credit: Approved and Pending of the last 30 days) that added transactions do not move; the fresh hold stops being fresh a few days after setup.
- Revisit when: Clara reads balances, or demo accounts must stay demo-ready for weeks.
- Source: 0006_customer_data_onboarding

## 2026-09-28: manual transactions are idempotent like messages

- Decision: the app mints the transaction's UUIDv7 with the clock it syncs from `server_time` (the same clock as the chat); the server rejects ids more than 2 minutes off and returns the stored row with 200 on a retry; a suspicious merchant's 4-digit suffix is reserved first with `ADD ... NOT contains` on `customers.suspicious_suffixes` (20 draws, then 503).
- Alternatives rejected: server-minted ids with a separate idempotency key (another attribute to look up); checking suffixes by querying the account (racy).
- Reason: one pattern for every client write, and uniqueness enforced by DynamoDB, not by a read before write.
- Debt created: none.
- Revisit when: an account nears the 9000 suffixes.
- Source: 0006_customer_data_onboarding

## 2026-09-28: read models are allow-lists in core, used as projection and mapping

- Decision: `core.accounts` (cards, transactions) and `core.customers` (profile) list the attributes any reader may see and use them both as `ProjectionExpression` and as the response mapping; `crud`'s endpoints and every future tool read through them; `crud` keeps a full read of `customers` only for its setup claim.
- Alternatives rejected: deny-lists (a new internal attribute would leak by default).
- Reason: `origin`, `setup_claimed_at` and `suspicious_suffixes` must never reveal to Clara or the customer which charges were planted.
- Debt created: `crud` and `messages` duplicate the claims and body parsing of their handlers.
- Revisit when: a third API lambda appears.
- Source: 0006_customer_data_onboarding

## 2026-09-29: an added transaction is a placeholder in the cached ledger until the server answers

- Decision: the add inserts a `PendingTransaction` (id and date from the minted UUIDv7) at the top of the first cached page; success swaps it by `transaction_id`, or prepends the row if a refetch already dropped it; error removes only that placeholder; the ledger is invalidated when the last add on that card settles; setup writes the returned profile into the cache and, on 409, reads the stored one before resolving.
- Alternatives rejected: placeholders from `useMutationState` outside the cache (two sources for one list); snapshot rollback (concurrent adds would erase each other); waiting on a profile refetch after setup (a failed refetch left the dialog stuck).
- Reason: the server picks merchant, amount and status, so only the id and date are known at once, and several adds may be in flight.
- Debt created: a focus refetch that starts while an add is in flight can hide its placeholder until the add succeeds; a failed cards refetch after setup leaves the list empty with no error.
- Revisit when: a customer reports a missing row or card.
- Source: 0009_client_data_cache
