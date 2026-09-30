---
updated: 2026-09-29
source: 0009_client_data_cache
---

# Technical Requirements Document

Clara, the customer service system for LATAM Bank unrecognized card charges.
One repository, `Team-ACGS/factored-hackathon-2026-acgs`, base branch `main`.
Built: `data/`, `infra/`, `.github/workflows/`, and `lambdas/` and `apps/` as a walking skeleton (task 0003: every lambda, the `customer` app and `ui`; task 0006: `crud` for the customer's own data); `support`, `backoffice`, `training/` and `evaluation/` are designed and described here as agreed on 2026-09-27.

## Components

| Component | Kind | Path | Base branch | Stack |
|---|---|---|---|---|
| hackathon | repo | `./` | `main` | Python 3.12, TypeScript, Terraform |

### hackathon

- Layout:
  - `data/`: dataset pipeline (raw CSV to curated Parquet, contracts, figures). Built.
  - `lambdas/`: uv workspace of Python lambdas: `core` (shared package bundled into every zip), `auth` (Cognito triggers), `crud`, `messages`, `chat_notifier`, `chatbot`.
  - `apps/`: pnpm workspace of three client-side SPAs (React, Vite, TanStack Router, TanStack Query): `customer` (factoredai.sdfles.com), `support` (support.), `backoffice` (backoffice.), plus a shared `ui` package.
  - `training/`: training code for own models; artifacts versioned in S3, never in git.
  - `evaluation/`: held-out set, baselines and harness.
  - `infra/`: Terraform: `environments/core/` (account singletons: API Gateway logging role, admin users), `environments/prd/` (the root), `stacks/backend/` and `stacks/frontend/`, `modules/aws/*` (one leaf module per service), `modules/github/`; bootstrap, apply and destroy in `infra/docs/setup.md`.
  - `.github/workflows/`: CI and code delivery.
  - `docs/`: this documentation.
- Install: `uv sync` in `data/` and `lambdas/`; `pnpm install --frozen-lockfile` in `apps/`.
- Workspace files: `data/.env` from `data/.env.example`; `apps/customer/.env.local` from `apps/customer/.env.example` to run the app locally.
- API spec: none yet.
- Data: DynamoDB on demand, seven tables (`customers`, `products`, `transactions`, `complaints`, `staff`, `rooms`, `messages`), defined in `infra/`, no migrations; `crud` setup seeds each demo customer's cards and transactions (task 0006); a seed from the dataset is not built (owner not decided). Analytics on DuckDB over Parquet in `data/`.
- Keys: every table but `staff` has partition key `customer_id`; sort keys are `product_id`, `transaction_key` (`<product_id>#<transaction_date>#<transaction_id>`, so one card reads newest first), `complaint_id`, `room_id` and `message_key` (`<room_id>#<sent_at>#<message_id>`); `customers` has none; `staff` is keyed by `staff_id`; `complaints` has GSI `by-area-priority` (`area`, `priority_score` number).
- Delivery: see below.

## Runtime architecture

- Client SPAs on S3 behind CloudFront, one distribution per app, certificates from ACM, records in the existing Route 53 zone `sdfles.com`.
- API Gateway (REST) on `api.factoredai.sdfles.com` with a Cognito authorizer accepting both pools: `/crud/*` to `crud` (today the customer's profile and setup, cards and transactions; routes in `modules/assistant/trd.md`), `/messages/*` to `messages`.
- No lambda calls another lambda; shared behavior lives in `lambdas/core`.
- A message is written once: `messages` stores it (and the room when new) with a conditional write; the `messages` DynamoDB stream feeds `chat_notifier`, which pushes it to the room's AppSync Events channel, and `chatbot`, which only sees customer messages (`sender_type = customer`).
- A turn: `chatbot` understands, decides with the rules table, acts, composes with Claude Sonnet 5 on Bedrock, and writes the reply as an ordinary message, which reaches clients through the same notifier.
- Each stream consumer has 3 retries, bisect on error and its own SQS DLQ.
- Identity of a customer: `customer_id` is the Cognito `sub` of the `customers` pool, set by Cognito at sign-up and never chosen by a client or a lambda; `post_confirmation` creates the `customers` row with it. `staff_id` is the `sub` of the `staff` pool.
- Realtime: one AppSync Events channel per room, `/rooms/{customer_id}/{room_id}`; publishing is IAM only (`chat_notifier`); an `onSubscribe` handler lets a customer token subscribe only when the `customer_id` segment is its own `sub`, and lets staff tokens through.
- Isolation: the lambda reads pool and `cognito:groups` from the token and assumes `role-customer` (session tag `customer_id`, `dynamodb:LeadingKeys`), `role-agent`, `role-officer` or `role-analyst`; lambdas cannot read tables with their own role.
- Identity: pool `customers` (self sign-up, email and password, email verification code through SES) and pool `staff` (created by us, email and password, no MFA, groups `agents`, `officers`, `analysts`); triggers `post_confirmation`, `pre_token_generation` and `custom_message` (every email of both pools in the recipient's `locale`, English by default) in `lambdas/auth`.
- Email: SES from `notifications.factoredai.sdfles.com`.
- Own models: served later from a Lambda container image; not in `infra/` yet.
- No VPC.

## Observability

- Every lambda uses Powertools for AWS Lambda (Python): Logger (structured JSON with `xray_trace_id`), Metrics (EMF), Tracer (X-Ray).
- Writes are idempotent through conditional writes with deterministic ids ("only if absent"), not Powertools Idempotency, which would need an eighth table.
- CloudWatch Logs; custom metrics in namespaces `Clara/Backend` and `Clara/Assistant`, shown on dashboards `clara-prd-backend` and `clara-prd-assistant`.
- X-Ray active tracing on every lambda and the API Gateway stage, set in Terraform. The sampling rule `clara-prd-api` traces 100% of API requests, and `messages` inherits that decision. The stream consumers (`chatbot`, `chat_notifier`) keep Lambda's fixed sampling, 1 request per second plus 5%, which AWS does not let you change.
- A message yields three traces, not one: X-Ray does not link traces through DynamoDB Streams. `messages` stores its trace id on the item and both consumers annotate it as `origin_trace_id` (task 0008), so the filter `annotation.origin_trace_id = "<trace id>"` plus the API trace itself finds the three.
- A trace of `POST /messages` has API Gateway (`api.factoredai.sdfles.com`) as its entry point, with `messages` inside it; searching for traces that enter at `clara-prd-messages` finds nothing.
- Memory: 1024 MB for `messages`, `chatbot` and `chat_notifier` (the chat path), 512 MB for the rest; every function runs on x86_64.
- Turn events from day one: `chatbot` publishes to EventBridge bus `clara-prd` with source `clara.chatbot` at the end of each turn, a rule delivers to Data Firehose, Firehose writes gzip JSON lines to `turns/` in the events bucket; ids only, never message text, each with `trace_id`.
- Analysis of those events and the LLM judge are deferred (`docs/tasks/_drafts/turn_events_analysis.md` in the docs root).

## Environments and delivery

- One environment, `prd`, AWS us-east-1, deployed from `main`.
- Terraform owns infrastructure and configuration; GitHub Actions owns code.
- Terraform creates each lambda with a bootstrap bundle, its own role (from a capability map), log group and environment, and ignores `s3_key`; Actions uploads bundles keyed by commit SHA and calls `update-function-code` only when `CodeSha256` changes.
- `terraform apply` is run by a person; `.github/workflows/terraform.yml` runs `fmt`, `validate` and a `plan` of `core` and `prd` on every pull request that touches `infra/`, with the plan in the job summary.
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
| lambdas | `lambdas/` | `uv run ruff check . && uv run ruff format --check .` | `uv run mypy` | `uv run pytest` | `n/a` |
| apps | `apps/` | `pnpm lint` | `pnpm typecheck` | `pnpm test` | `n/a` |
| infra | `infra/` | `terraform fmt -check -recursive` | `terraform -chdir=environments/prd init -backend=false && terraform -chdir=environments/prd validate` | `n/a` | `n/a` |

Targets marked `unknown` are fixed by the task that scaffolds them.

## Modules

Modules belong to the application and may span folders.

| Module | Purpose | Folders | Docs |
|---|---|---|---|
| assistant | Clara's turn: triage explain, claim or protect; rules decide, the LLM extracts and writes | `lambdas/chatbot`, `lambdas/core`, `apps/customer` | [README](modules/assistant/README.md) |
| cases | Case record in `complaints`, lifecycle, handoff package, agent console | `lambdas/crud`, `lambdas/core`, `apps/support` | [README](modules/cases/README.md) |
| inbox | Categorize, rank and assign cases for officers | `lambdas/`, `apps/backoffice` | [README](modules/inbox/README.md) |
| messaging | Rooms, messages, the messages stream and AppSync Events, customer rating | `lambdas/messages`, `lambdas/chat_notifier`, `lambdas/core` | [README](modules/messaging/README.md) |
| identity | Cognito pools, triggers, IAM roles and per-customer isolation | `lambdas/auth`, `infra/` | [README](modules/identity/README.md) |
| models | Intent router and injection detector (e5 plus logistic regression) | `training/` | [README](modules/models/README.md) |
| evaluation | Held-out set, baselines, rubric metrics, improvement console (later) | `evaluation/` | [README](modules/evaluation/README.md) |
| data | Dataset pipeline, contracts and figures | `data/` | [README](modules/data/README.md) |

## Conventions

- One source for table shapes in the pipeline: `data/src/bankdata/pipeline/schemas.py`.
- Every figure cited in a doc is regenerated from a committed query: `data/sql/figures/`.
- Tests never touch the real dataset; they run on fixtures: `data/tests/fixtures/`.

### Server data in the webs

Every web (`customer`, `support`, `backoffice`, `analysts`) reads and writes server data through TanStack Query; no `useEffect` fetches.

- One key factory per resource family (`src/bank/queries.ts` in `customer`): keys name the resource and its ids, never the user, because the cache holds one signed-in user.
- Stale time per resource: slow data (profile, card list) minutes, lists that grow (a card's ledger, a transaction) seconds; `gcTime` of 60 minutes, so a screen visited in the session renders from cache.
- A write invalidates exactly the keys it changes, never a whole family; an optimistic write edits the cached pages, rolls back only its own change, and invalidates on settle only when no other write on the same key is in flight.
- Routes load with `ensureQueryData` / `ensureInfiniteQueryData` and components read with the suspense hooks; the router preloads on intent with `defaultPreloadStaleTime: 0`, leaving freshness to Query; the query client travels in router context.
- One retry layer: the HTTP client retries; Query uses `retry: false` for queries and mutations.
- The cache is cleared whenever a signed-out route is entered, which sign-out always passes through.
