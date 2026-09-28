---
updated: 2026-09-27
source: 0003_walking_skeleton
---

# Identity: database

Status: roles built (task 0001), assumed by the lambdas since task 0003.

Identity keeps no DynamoDB table of its own; its store is Cognito (the two user pools) plus the IAM roles Terraform will define.
The seven tables themselves are defined by a different `infra/` leaf module and loaded by a separate seed process whose owner is not decided; identity only owns who may act on them.
Pool attributes, app client settings and role policies will live in Terraform, not in this file.

## Tables owned

None.
Identity's persistent state is the two Cognito user pools and the four IAM roles (`role-customer`, `role-agent`, `role-officer`, `role-analyst`), not a DynamoDB table.

## Tables referenced

| Table | Owner module | Relationship |
|---|---|---|
| customers, products, transactions (keyed by `customer_id`) [inferido, planned] | assistant | Identity does not read them; it only issues the STS credentials, tagged with `customer_id`, that let another lambda read them under `LeadingKeys`. |
| complaints (PK `customer_id`, GSI by area and priority; these ARE the cases, Clara-opened and historical) [inferido, planned] | cases / inbox | Same relationship: identity grants `role-agent` or `role-officer` credentials another lambda uses to query it, directly or through the GSI. |
| staff (area, shift, language) | inbox | Read by a lambda holding `role-agent` or `role-officer`; identity does not read it either. |
| rooms, messages [inferido, planned] | messaging | Read and written under `role-customer`, `role-agent` or `role-officer`, depending on who is in the room. |

There is no `cases` table and no `users` table: `cases` is a module name only (complaints hold that lifecycle), and users are Cognito, not DynamoDB.

## Invariants kept in code

- A request-handling lambda never reads a table with its own execution role; it always assumes `role-customer`, `role-agent`, `role-officer` or `role-analyst` first.
- `customer_id` is the Cognito `sub` of the `customers` pool; `post_confirmation` writes the `customers` row with it, only if absent (its role can `PutItem` on `customers` and nothing else).
- The `customer_id` session tag passed to `AssumeRole` comes from the verified JWT's `sub` (`messages`) or from the stream record the table itself wrote (`chatbot`), never from a request parameter, so a lambda cannot be asked to tag a session with someone else's id.

## Migrations of note

None yet; nothing is built.
