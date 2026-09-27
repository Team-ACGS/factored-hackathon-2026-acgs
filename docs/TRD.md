---
updated: 2026-09-27
source: setup
---

# Technical Requirements Document

Clara, the customer service system for LATAM Bank unrecognized card charges.
One repository, `Team-ACGS/factored-hackathon-2026-acgs`, base branch `main`.
Only `data/` is built; every other folder is designed and described here as agreed on 2026-09-27.

## Components

| Component | Kind | Path | Base branch | Stack |
|---|---|---|---|---|
| hackathon | repo | `./` | `main` | Python 3.12, TypeScript, Terraform |

### hackathon

- Layout:
  - `data/`: dataset pipeline (raw CSV to curated Parquet, contracts, figures). Built.
  - `lambdas/`: uv workspace of Python lambdas: `core` (shared package bundled into every zip), `auth` (Cognito triggers), `crud`, `chatbot`, `notifications`.
  - `apps/`: pnpm workspace of three client-side SPAs (React, Vite, TanStack Router): `customer` (factoredai.sdfles.com), `support` (support.), `backoffice` (backoffice.), plus a shared `ui` package.
  - `training/`: training code for own models; artifacts versioned in S3, never in git.
  - `evaluation/`: held-out set, baselines and harness.
  - `infra/`: Terraform: `environments/core/` (account singletons: API Gateway logging role, admin users), `environments/prd/` (the root), `stacks/backend/` and `stacks/frontend/`, `modules/aws/*` (one leaf module per service), `modules/github/`; bootstrap, apply and destroy in `infra/docs/setup.md`.
  - `.github/workflows/`: CI and code delivery.
  - `docs/`: this documentation.
- Install: `uv sync` in `data/` and `lambdas/`; `pnpm install --frozen-lockfile` in `apps/` [inferido: lambdas and apps not scaffolded].
- Workspace files: `data/.env` from `data/.env.example`.
- API spec: none yet.
- Data: DynamoDB on demand, seven tables (`customers`, `products`, `transactions`, `complaints`, `staff`, `rooms`, `messages`), defined in `infra/`, no migrations; a separate seed process loads them (owner not decided). Analytics on DuckDB over Parquet in `data/`.
- Keys: every table but `staff` has partition key `customer_id`; sort keys are `product_id`, `transaction_key`, `complaint_id`, `room_id` and `message_key` (`<room_id>#<sent_at>#<message_id>`); `customers` has none; `staff` is keyed by `staff_id`; `complaints` has GSI `by-area-priority` (`area`, `priority_score` number).
- Delivery: see below.

## Runtime architecture

- Client SPAs on S3 behind CloudFront, one distribution per app, certificates from ACM, records in the existing Route 53 zone `sdfles.com`.
- API Gateway (REST) on `api.factoredai.sdfles.com` with a Cognito authorizer accepting both pools: `/crud/*` to `crud`, `/chat/*` to `chatbot`.
- No lambda calls another lambda; shared behavior lives in `lambdas/core`.
- A turn: `chatbot` understands, decides with the rules table, acts, composes with Claude Sonnet 5 on Bedrock, and publishes the reply to SQS; `notifications` writes `messages` and pushes it through an AppSync Events channel per room.
- Isolation: the lambda reads pool and `cognito:groups` from the token and assumes `role-customer` (session tag `customer_id`, `dynamodb:LeadingKeys`), `role-agent`, `role-officer` or `role-analyst`; lambdas cannot read tables with their own role.
- Identity: pool `customers` (self sign-up, email and password, email verification code through SES) and pool `staff` (created by us, email and password, no MFA, groups `agents`, `officers`, `analysts`); triggers `post_confirmation` and `pre_token_generation` in `lambdas/auth`.
- Email: SES from `notifications.factoredai.sdfles.com`.
- Own models: served later from a Lambda container image; not in `infra/` yet.
- No VPC.

## Observability

- Every lambda uses Powertools for AWS Lambda (Python): Logger (structured JSON with `xray_trace_id`), Metrics (EMF), Tracer (X-Ray).
- Writes are idempotent through conditional writes with deterministic ids ("only if absent"), not Powertools Idempotency, which would need an eighth table.
- CloudWatch Logs; custom metrics in namespaces `Clara/Backend` and `Clara/Assistant`, shown on dashboards `clara-prd-backend` and `clara-prd-assistant`.
- X-Ray active tracing on every lambda and the API Gateway stage, set in Terraform.
- Turn events from day one: `chatbot` publishes to EventBridge bus `clara-prd` with source `clara.chatbot` at the end of each turn, a rule delivers to Data Firehose, Firehose writes gzip JSON lines to `turns/` in the events bucket; ids only, never message text, each with `trace_id`.
- Analysis of those events and the LLM judge are deferred (`docs/tasks/_drafts/turn_events_analysis.md` in the docs root).

## Environments and delivery

- One environment, `prd`, AWS us-east-1, deployed from `main`.
- Terraform owns infrastructure and configuration; GitHub Actions owns code.
- Terraform creates each lambda with a bootstrap bundle, its own role (from a capability map), log group and environment, and ignores `s3_key`; Actions uploads bundles keyed by commit SHA and calls `update-function-code` only when `CodeSha256` changes.
- `terraform apply` is run by a person; CI runs `fmt`, `validate` and `plan` on pull requests.
- On merge to `main`, Actions deploys lambdas and apps (`s3 sync` plus CloudFront invalidation) over GitHub OIDC; Terraform writes the Actions environments and their variables, so workflows hold no ARN, URL or key (contract in `infra/docs/setup.md`).
- The account's GitHub OIDC provider belongs to the my-napkin Terraform; Clara only reads it.
- Names come from `${project}-${env}`; buckets append the account id.
- Every resource carries `default_tags` (project, environment, managed-by) activated as cost allocation tags.
- Fully destroyable: `terraform destroy` removes every resource and its data; only the state bucket, the Route 53 zone and the shared OIDC provider survive.
- Pattern taken from the auvral infra (`auvral/docs/modules/infra/trd.md`).

## Verification targets

`verify-task` reads this table literally. Commands run one at a time.

| Target | Path | lint | typecheck | unit | e2e |
|---|---|---|---|---|---|
| data | `data/` | `unknown` | `unknown` | `uv run pytest` | `n/a` |
| lambdas | `lambdas/` | `unknown` | `unknown` | `unknown` | `unknown` |
| apps | `apps/` | `unknown` | `unknown` | `unknown` | `unknown` |
| infra | `infra/` | `terraform fmt -check -recursive` | `terraform -chdir=environments/prd init -backend=false && terraform -chdir=environments/prd validate` | `n/a` | `n/a` |

Targets marked `unknown` are fixed by the task that scaffolds them.

## Modules

Modules belong to the application and may span folders.

| Module | Purpose | Folders | Docs |
|---|---|---|---|
| assistant | Clara's turn: triage explain, claim or protect; rules decide, the LLM extracts and writes | `lambdas/chatbot`, `lambdas/core`, `apps/customer` | [README](modules/assistant/README.md) |
| cases | Case record in `complaints`, lifecycle, handoff package, agent console | `lambdas/crud`, `lambdas/core`, `apps/support` | [README](modules/cases/README.md) |
| inbox | Categorize, rank and assign cases for officers | `lambdas/`, `apps/backoffice` | [README](modules/inbox/README.md) |
| messaging | Rooms, messages, SQS and AppSync Events, customer rating | `lambdas/notifications` | [README](modules/messaging/README.md) |
| identity | Cognito pools, triggers, IAM roles and per-customer isolation | `lambdas/auth`, `infra/` | [README](modules/identity/README.md) |
| models | Intent router and injection detector (e5 plus logistic regression) | `training/` | [README](modules/models/README.md) |
| evaluation | Held-out set, baselines, rubric metrics, improvement console (later) | `evaluation/` | [README](modules/evaluation/README.md) |
| data | Dataset pipeline, contracts and figures | `data/` | [README](modules/data/README.md) |

## Conventions

- One source for table shapes in the pipeline: `data/src/bankdata/pipeline/schemas.py`.
- Every figure cited in a doc is regenerated from a committed query: `data/sql/figures/`.
- Tests never touch the real dataset; they run on fixtures: `data/tests/fixtures/`.
