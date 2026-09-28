---
updated: 2026-09-27
source: task 0004
---

# Identity: technical

Status: designed, not built.
Nothing under `lambdas/auth/` or `infra/` exists yet; this describes the agreed design, source `docs/tasks/_drafts/architecture_and_layout.md` (2026-09-27), which wins over `docs/product/03-architecture.md` where they differ.

## Structure

| Path | What |
|---|---|
| `lambdas/auth/` [inferido, planned] | Cognito trigger handlers, one file per trigger: `post_confirmation`, `pre_token_generation`. Deploy unit like the other lambdas (uv workspace, shared `core` package bundled in). |
| `infra/modules/aws/cognito` [inferido, planned] | Leaf Terraform module for the two user pools, their app clients and groups. |
| `infra/environments/prd/` [inferido, planned] | Where the Cognito pools, `role-customer`, `role-agent`, `role-officer`, `role-analyst` IAM roles and the auth lambdas are wired into the single `prd` environment. |

## Endpoints owned

None over API Gateway.
The two functions in `lambdas/auth/` are invoked by Cognito itself as Lambda triggers (`post_confirmation`, `pre_token_generation`), not through a route.
`post_confirmation` runs only on the `customers` pool and creates the `customers` row keyed by the user's `sub` (env `TABLE_CUSTOMERS`, permission `PutItem` on that table only).

Emails: every code email (sign-up verification and password reset) and the staff invitation are one trilingual template per pool, English, Spanish and Brazilian Portuguese, in `infra/stacks/backend/emails/`.

Jobs, listeners or scheduled work: none.

Both triggers use AWS Lambda Powertools (Python) for structured JSON logging and X-Ray active tracing, the same as every other lambda in the project; `post_confirmation` writes one `customers` row with a conditional put, `pre_token_generation` writes nothing.

## Depends on

- SES: sends the sign-up verification code for the `customers` pool from `notifications.factoredai.sdfles.com`, never the apex; this is Cognito's standard email-verification message, not a passwordless sign-in flow.
- Route 53: DKIM records for that sending subdomain; the zone already exists.
- STS: the request lambdas (`crud`, `messages`) and `chatbot` call `AssumeRole` against the roles this module defines; identity owns the roles, not the calls.
- infra/ (a different leaf module than this one): defines the seven DynamoDB tables the roles below grant access to; identity does not own the tables, only who may act on them. A separate seed process, owner not decided, loads their data; it is neither this module nor the data module.

## Depended on by

- assistant, cases, inbox, messaging: each request-handling lambda reads `pool` and `cognito:groups` from the verified JWT and assumes `role-customer`, `role-agent`, `role-officer` or `role-analyst` before touching DynamoDB.
  None of them can read a table directly.
- apps/customer, apps/support, apps/backoffice: sign in against the app client for their own subdomain; a wrong-pool token is rejected before it reaches API Gateway.
  A fourth app client, for analysts.factoredai.sdfles.com, is reserved for the improvement console; not built.

## Configuration

- `CUSTOMERS_USER_POOL_ID`, `CUSTOMERS_APP_CLIENT_ID` [inferido, planned]: the `customers` pool and its `factoredai.` app client.
- `STAFF_USER_POOL_ID`, `STAFF_APP_CLIENT_ID_SUPPORT`, `STAFF_APP_CLIENT_ID_BACKOFFICE` [inferido, planned]: the `staff` pool, one app client per staff subdomain (`support.`, `backoffice.`); the fourth, `analysts.`, does not exist until that web is built.
- `ROLE_CUSTOMER_ARN`, `ROLE_AGENT_ARN`, `ROLE_OFFICER_ARN`, `ROLE_ANALYST_ARN` [inferido, planned]: the four roles a request-handling lambda assumes, written by Terraform per the auvral pattern (no ARN typed anywhere); `ROLE_ANALYST_ARN` is unused until the improvement console exists.

## Testing

- No tests exist yet.
- Planned: a `pre_token_generation` case that asserts a `staff` user in `agents` is rejected on the `backoffice.` app client, and the reverse [inferido].
