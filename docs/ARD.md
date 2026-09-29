---
updated: 2026-09-29
source: 0008_chat_latency
---

# Architecture and Debt Record

Global decisions, as a dated log, and the index of debt across modules.
Module-level decisions live in `modules/<module>/ard.md`.
The design sessions behind these entries are summarized in `docs/tasks/_drafts/architecture_and_layout.md` of the docs root.

## Decisions

## 2026-09-27: Serverless on Lambda, no containers, no VPC

- Decision: Python lambdas (`auth`, `crud`, `messages`, `chat_notifier`, `chatbot`) behind API Gateway or a DynamoDB stream, with a shared package `core` bundled into each zip; no lambda calls another lambda.
- Alternatives rejected: FastAPI on ECS Fargate (`docs/product/03-architecture.md`); an EC2 instance for own models; lambda-to-lambda calls from `chatbot` to `crud`.
- Reason: no always-on cost, no VPC or NAT gateway, one deploy shape for everything; a shared package avoids chained cold starts and cascading failures.
- Debt created: own-model serving is designed as a Lambda container image but not in `infra/` yet.
- Revisit when: a turn's latency budget cannot be met by lambdas.
- Source: setup

## 2026-09-27: Isolation enforced by IAM, not by code

- Decision: customer-owned tables are keyed by `customer_id`; each request assumes `role-customer` with a `customer_id` session tag (`dynamodb:LeadingKeys`), or `role-agent`, `role-officer`, `role-analyst` by Cognito group; lambdas cannot read tables with their own role.
- Alternatives rejected: a mock identity provider; a Cognito identity pool (requests go through lambdas, not the browser); checks in code only.
- Reason: a cross-customer read fails with AccessDenied from AWS, a proof no prompt or code bug can bypass.
- `customer_id` is the Cognito `sub`, so the token, the session tag, the table keys and the realtime channel all carry one value no one can choose (task 0004).
- Debt created: the lambda maps token to role; a bug there is not caught by AWS.
- Revisit when: a role needs row-level rules beyond the partition key.
- Source: setup

## 2026-09-27: Two Cognito pools, three webs

- Decision: pool `customers` (self sign-up, email and password, email verification code through SES) and pool `staff` (created by the team, email and password, groups `agents`, `officers`, `analysts`); one app client per web: factoredai., support., backoffice., and later analysts.
- Alternatives rejected: one pool with groups; passwordless email OTP; MFA for staff.
- Reason: open self sign-up must not reach staff webs; the separation comes from Cognito, not from our code.
- Debt created: a pre token generation trigger and every lambda must still check group against app client inside `staff`.
- Revisit when: staff need a second factor.
- Source: setup

## 2026-09-27: One language model, Claude Sonnet 5 on Bedrock

- Decision: Sonnet 5 at low effort extracts and composes on every turn, and labels and judges offline; prompt caching is mandatory.
- Alternatives rejected: Haiku, Sonnet and Opus by role; Titan embeddings and Grok in the turn; Fable 5.1 and Opus 5.5 for cost and latency.
- Reason: one model, one cache, the cheapest setup that holds quality; Clara decides with rules and the grounding check is deterministic, so no second model is needed in the turn.
- Debt created: Sonnet judging Sonnet risks self-preference; the judge must be validated against human labels.
- Revisit when: measured cost or latency per turn is too high (move extraction to Haiku 4.5).
- Source: setup

## 2026-09-27: Infra and delivery follow the auvral pattern

- Decision: Terraform owns infrastructure and configuration, GitHub Actions owns code; one environment `prd` in us-east-1; apply by a person, CI plans; code deploys on merge over OIDC; one IAM role per lambda from a capability map; everything tagged and fully destroyable.
- Alternatives rejected: CDK (`docs/product/03-architecture.md`); applying Terraform from CI; a dev environment.
- Reason: a proven pattern in `auvral/docs/modules/infra/trd.md`; a hackathon needs one environment and no leftover data after `terraform destroy`.
- Debt created: the state bucket is created by hand once; the GitHub OIDC provider is shared with the my-napkin Terraform, which owns it; the account is shared with other projects, so the admin users' region deny is a guardrail, not isolation.
- Revisit when: a second environment is needed.
- Source: setup

## 2026-09-27: Observability from day one, analysis later

- Decision: Powertools (Logger, Metrics, Tracer) in every lambda; CloudWatch Logs; metrics in `Clara/Backend` and `Clara/Assistant`; X-Ray active tracing; one turn event per turn to EventBridge, Firehose and S3 with ids only and the `trace_id`.
- Alternatives rejected: a third-party APM; events through a lambda; storing message text in events.
- Reason: turns not recorded can never be analyzed; events are also the bronze layer of a later ETL.
- Debt created: event analysis and the LLM judge are deferred (`docs/tasks/_drafts/turn_events_analysis.md`).
- Revisit when: the rubric metrics must be produced.
- Source: setup

## 2026-09-27: Idempotent writes through conditional writes

- Decision: every write uses a deterministic id and a condition ("only if absent") on the business table itself.
- Alternatives rejected: Powertools Idempotency, which needs an eighth table.
- Reason: the tables already hold the natural key; a retry that finds the item is a no-op.
- Debt created: none.
- Revisit when: a write has no natural deterministic id.
- Source: task 0001

## 2026-09-27: Product docs live in the code repo

- Decision: PRD, TRD, ARD, modules and domain docs live in `docs/` of this repo; task planning lives in a separate local docs root.
- Alternatives rejected: all docs in the docs root.
- Reason: the whole team reads and updates the product docs where the code is.
- Debt created: working notes cited here (problem statement, EDA findings, product flows) stay in the docs root, invisible to teammates.
- Revisit when: a teammate needs one of them.
- Source: setup

## 2026-09-27: each lambda bundle carries its locked dependencies

- Decision: `lambdas/build.py` writes one directory per deployed function with the `uv.lock` dependencies (boto3 included, manylinux wheels only), the workspace packages it uses and an entry file named after its handler; the deploy zips them with sorted entries and fixed mtimes.
- Alternatives rejected: relying on the runtime's boto3 (tests and production would run different versions); one shared layer (a second artifact to version).
- Reason: what the tests ran is what production runs, and identical code gives an identical `CodeSha256`, so unchanged functions are skipped.
- Debt created: each zip is about 18 MB, mostly botocore; no smoke test runs after a lambda deploy.
- Revisit when: cold starts matter, or a deploy breaks a function unnoticed.
- Source: 0003_walking_skeleton

## Debt index

Open debt only: an entry with `Resolved by` leaves the table.

| Module | Date | Debt | Revisit when |
|---|---|---|---|
| global | 2026-09-27 | Legal deadlines cited from memory, not verified (`docs/domain/legal-deadlines.md`) | before any deadline reaches a reply or a ranking |
| global | 2026-09-27 | Owner of a seed from the dataset not decided; demo customers are seeded by `crud` setup (0006) | before dataset rows must reach DynamoDB |
| global | 2026-09-27 | Lambda zips are about 18 MB each and no smoke test follows a lambda deploy | when cold starts matter or a deploy breaks unnoticed |
| assistant | 2026-09-27 | No adversarial fixture for tool-output injection | before the evaluation run |
| assistant | 2026-09-27 | `turn.completed` is at least once; duplicates reach S3 and must be deduped by `reply_message_id` | when turn events are analyzed |
| assistant | 2026-09-28 | Card balances are a setup snapshot; added transactions do not move them | when Clara reads balances or limits |
| assistant | 2026-09-28 | The planted fresh hold ages out of the 7-day window a few days after setup | when demo accounts must stay demo-ready for weeks |
| assistant | 2026-09-28 | `crud` and `messages` duplicate the claims and body parsing of their handlers | when a third API lambda appears |
| identity | 2026-09-27 | `role-analyst` and group `analysts` unused until the fourth web exists | when the improvement console is built |
| identity | 2026-09-27 | IAM changes a lambda needs must be applied by hand before the merge deploys that lambda | when Terraform applies from CI |
| identity | 2026-09-29 | The credentials cache of `core.access` and its resources are not thread safe | when a handler runs work on threads |
| messaging | 2026-09-27 | Room history is not paginated | when the support app reads other rooms or a room passes a few hundred messages |
| messaging | 2026-09-27 | The chat does not resubscribe and reread history after the live connection drops | when customers report missing replies, or before the demo |
| models | 2026-09-27 | Serving designed but not in `infra/` | when the first model artifact exists |
| evaluation | 2026-09-27 | No custodian, hash mechanism or recorded-response fixtures for the held-out | before the held-out is written |
| evaluation | 2026-09-27 | Held-out written from scenario cards the team designed; Portuguese entirely team-generated | state it in the presentation |
| data | 2026-09-27 | Contracts check structure, not content; known semantic defects pass | if curated data feeds a model |
