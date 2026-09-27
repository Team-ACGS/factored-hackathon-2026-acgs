---
updated: 2026-09-27
source: setup
---

# evaluation: database

Status: designed, not built.
No schema exists yet; this describes what is agreed, not a live table definition.

## Tables owned

None of the 7 DynamoDB tables (`customers`, `products`, `transactions`, `complaints`, `staff`, `rooms`, `messages`; `infra/` defines them, Sebastian's decisions, 2026-09-27).
There is no `cases` table and no `users` table: `complaints` is the case table (historical complaints and every new one Clara opens), and users are Cognito, not a row.
The held-out set and its custody protocol are described as material kept by a custodian, not a database table (`docs/kickoff-compliance.md`, "Leakage prevention"); this module is a reader of other modules' tables and of turn events, and a producer of reports and reviewer decisions, not an owner of serving data. [inferido: whether held-out cases and judge scores end up in a table at all, versus files under custodian control, is not decided anywhere]

## Tables referenced

| Table | Owner module | Relationship |
|---|---|---|
| Turn events (ids only, never message text, each with `trace_id`; JSON gzip, raw, as a bronze layer) | assistant emits them (`lambdas/chatbot` `PutEvents` to EventBridge bus `clara` -> Firehose -> S3); ownership of the event contract and of the analysis is proposed for this module in `docs/tasks/_drafts/turn_events_analysis.md` but that whole document is deferred, so treat the ownership line as a proposal, not a decision [inferido] | Meant to be read to compute rubric metrics, dialect flip rate and cost per case from real conversations, and to feed an LLM judge; deferred, not dropped (Sebastian's decisions, 2026-09-27, item 7; `docs/tasks/_drafts/turn_events_analysis.md`) |
| `complaints` (the case table; GSI by area and priority for the staff queue) | cases (single writer for case content; `inbox` writes only ranking and assignment fields) | Read to compute H1 (claim outcomes) and H2 (unsafe outcomes on writes) |
| `rooms` (customer rating 1-5 and optional comment stored on the room) | messaging | Read as a weak signal into the improvement console's aggregation; the console itself is not built now |
| `messages` | messaging | Read where a handoff conversation is needed to grade H4 (re-asks per handoff) against the structured package |

## Invariants kept in code

- A change proposed in the improvement console is never promoted to the live assistant without a fresh run on the frozen held-out plus the adversarial set that shows it is better and no less safe (`docs/product/01-flows.md` flow 4).
- The held-out set's hash is committed by the custodian before the team touches any prompt, so no run against it can be back-fit after the fact (`docs/kickoff-compliance.md`, "Leakage prevention").
- Every H1-H5 number is computed for the two baselines as well as for Clara, on the same material, so no number about Clara is reported without its comparison (`docs/problem-statement.md` section 9).

## Migrations of note

- None; no table exists yet. [inferido]
