---
updated: 2026-09-27
source: 0003_walking_skeleton
---

# Identity: technical

Status: built (tasks 0001 and 0003); the staff group against app client check waits for the support app.

## Structure

| Path | What |
|---|---|
| `lambdas/auth/` | Cognito triggers, deployed as `auth-post-confirmation` and `auth-pre-token-generation`: the first creates the `customers` row of a new sign-up and counts `SignUps`, the second logs and returns the event unchanged. |
| `core.access` in `lambdas/core` | Reads pool (from `iss`) and `cognito:groups` from verified claims and assumes the matching role; a customer session is tagged `customer_id` = `sub`, a staff token needs exactly one group. |
| `infra/stacks/backend/` | `cognito.tf` (pools, app clients, groups, triggers) and `access.tf` (the four roles and their trust); leaf module `infra/modules/aws/cognito_user_pool`. |

## Endpoints owned

None over API Gateway.
The two functions in `lambdas/auth/` are invoked by Cognito itself as Lambda triggers (`post_confirmation`, `pre_token_generation`), not through a route.
`post_confirmation` runs only on the `customers` pool; on a sign-up confirmation it creates the `customers` row (`customer_id` = the event's `sub`, `email`, `created_at`) through `core.customers`, only if absent, assuming `role-customer` tagged with that `sub`. Its own role can assume `role-customer` and touch no table; `role-customer` may create its own `customers` row, never update it. A password-reset confirmation only logs.

Emails: every code email (sign-up verification and password reset) and the staff invitation are one trilingual template per pool, English, Spanish and Brazilian Portuguese, in `infra/stacks/backend/emails/`.

Jobs, listeners or scheduled work: none.

Both triggers use AWS Lambda Powertools (Python) for structured JSON logging and X-Ray active tracing, the same as every other lambda in the project; `post_confirmation` writes one `customers` row with a conditional put, `pre_token_generation` writes nothing.

## Depends on

- SES: sends the sign-up verification code for the `customers` pool from `notifications.factoredai.sdfles.com`, never the apex; this is Cognito's standard email-verification message, not a passwordless sign-in flow.
- Route 53: DKIM records for that sending subdomain; the zone already exists.
- STS: the request lambdas (`crud`, `messages`), `chatbot` and `post_confirmation` call `AssumeRole` against the roles this module defines; identity owns the roles, not the calls.
- infra/ (a different leaf module than this one): defines the seven DynamoDB tables the roles below grant access to; identity does not own the tables, only who may act on them. A separate seed process, owner not decided, loads their data; it is neither this module nor the data module.

## Depended on by

- assistant, cases, inbox, messaging: each request-handling lambda reads `pool` and `cognito:groups` from the verified JWT and assumes `role-customer`, `role-agent`, `role-officer` or `role-analyst` before touching DynamoDB.
  None of them can read a table directly.
- apps/customer, apps/support, apps/backoffice: sign in against the app client for their own subdomain; a wrong-pool token is rejected before it reaches API Gateway.
  A fourth app client, for analysts.factoredai.sdfles.com, is reserved for the improvement console; not built.

## Configuration

- `CUSTOMERS_POOL_ID`, `STAFF_POOL_ID`, `CUSTOMER_CLIENT_ID`, `SUPPORT_CLIENT_ID`, `BACKOFFICE_CLIENT_ID`: the pools and their app clients, in every request lambda.
- `ROLE_CUSTOMER_ARN`, `ROLE_AGENT_ARN`, `ROLE_OFFICER_ARN`, `ROLE_ANALYST_ARN`: the roles a request lambda may assume, written by Terraform; `ROLE_ANALYST_ARN` is unused until the improvement console exists.
- `post_confirmation`: `TABLE_CUSTOMERS`, `ROLE_CUSTOMER_ARN`. The triggers get no pool variable: the pools read the triggers' ARNs, so the reverse would close a cycle.

## Testing

- `lambdas/tests/auth/`: a sign-up confirmation creates one row keyed by `sub` through a session tagged with it, a second one changes nothing, a password reset writes nothing, a failed write fails the confirmation, no email in the logs.
- `lambdas/tests/core/test_access.py`: pool and group mapping and the session tag, on moto.
- Planned with the support app: `pre_token_generation` rejects a `staff` user on the wrong app client.
