---
updated: 2026-09-29
source: 0008_chat_latency
---

# Identity: technical

Status: built (tasks 0001 and 0003); the staff group against app client check waits for the support app.

## Structure

| Path | What |
|---|---|
| `lambdas/auth/` | Cognito triggers, deployed as `auth-post-confirmation`, `auth-pre-token-generation` and `auth-custom-message`: the first creates the `customers` row of a new sign-up and counts `SignUps`, the second logs and returns the event unchanged, the third writes every email of both pools. |
| `core.access` in `lambdas/core` | Reads pool (from `iss`) and `cognito:groups` from verified claims and assumes the matching role; a customer session is tagged `customer_id` = `sub`, a staff token needs exactly one group. |
| `infra/stacks/backend/` | `cognito.tf` (pools, app clients, groups, triggers) and `access.tf` (the four roles and their trust); leaf module `infra/modules/aws/cognito_user_pool`. |

## Endpoints owned

None over API Gateway.
The three functions in `lambdas/auth/` are invoked by Cognito itself as Lambda triggers (`post_confirmation`, `pre_token_generation`, `custom_message`), not through a route.
`post_confirmation` runs only on the `customers` pool; on a sign-up confirmation it creates the `customers` row (`customer_id` = the event's `sub`, `email`, `created_at`) through `core.customers`, only if absent, assuming `role-customer` tagged with that `sub`. Its own role can assume `role-customer` and touch no table. A password-reset confirmation only logs.

Emails: `custom_message` runs on both pools and writes every Cognito email in the user's `locale`: `en`, `es` or `pt-BR`, English when missing or unknown; one text per kind (a code for sign-up, resend and attribute verification, a password reset, and the staff invitation with `{username}` and the temporary password). It has no table permission. There is no fallback template: until its handler is deployed the bootstrap fails, and so does every email.
Writable attributes: every client writes only `email` and `locale`; Cognito requires `email` in the list because it is required, and it cannot change after creation (immutable in the pool schema).

Jobs, listeners or scheduled work: none.

Every trigger uses AWS Lambda Powertools (Python) for structured JSON logging and X-Ray active tracing, the same as every other lambda in the project; `post_confirmation` writes one `customers` row with a conditional put, `pre_token_generation` writes nothing.

## Depends on

- SES: sends the sign-up verification code for the `customers` pool from `notifications.factoredai.sdfles.com`, never the apex; this is Cognito's standard email-verification message, not a passwordless sign-in flow.
- Route 53: DKIM records for that sending subdomain; the zone already exists.
- STS: the request lambdas (`crud`, `messages`), `chatbot` and `post_confirmation` call `AssumeRole` against the roles this module defines through `core.access`, which caches the credentials per warm environment (`database.md`, invariants); identity owns the roles, not the calls.
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

- `lambdas/tests/auth/`: a sign-up confirmation creates one row keyed by `sub` through a session tagged with it, a second one changes nothing, a password reset writes nothing, a failed write fails the confirmation, no email in the logs; every custom message source in every language carries only that language, the invitation keeps both placeholders, and a missing or unknown `locale` gets English.
- `lambdas/tests/core/test_access.py`: pool and group mapping and the session tag, on moto.
- Planned with the support app: `pre_token_generation` rejects a `staff` user on the wrong app client.
