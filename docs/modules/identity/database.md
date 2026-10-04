---
updated: 2026-10-04
source: 0022_story_actions
---

# Identity: database

Status: roles built (task 0001), assumed by the lambdas since task 0003.

Identity keeps no DynamoDB table of its own; its store is Cognito (the two user pools) plus the IAM roles Terraform will define.
The seven tables themselves are defined by a different `infra/` leaf module; `crud` setup seeds each demo customer's rows; identity only owns who may act on them.
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
- `customer_id` is the Cognito `sub` of the `customers` pool; `post_confirmation` writes the `customers` row with it, only if absent, through `role-customer` tagged with that `sub`; the trigger's own role touches no table.
- `role-customer` reaches only items whose partition key is its `customer_id` tag (`dynamodb:LeadingKeys` on every statement):

| Table | Read | Write |
|---|---|---|
| `customers` | get, query | put (create, `post_confirmation`), update (setup profile and suspicious suffixes, `crud` only) |
| `transactions` | get, query | put, batch write (batch write can also delete) |
| `products`, `complaints`, `rooms`, `messages` | get, query | put, update |
| `memory` | get, query | put (create; the assistant's rules when an ask closes) |

"Only if absent" is the code's conditional write; IAM cannot force it, so any lambda holding `role-customer` could rewrite that customer's own row.
- The `customer_id` session tag passed to `AssumeRole` comes from the verified JWT's `sub` (`messages`), the stream record the table itself wrote (`chatbot`) or the Cognito trigger event (`post_confirmation`), never from a request parameter, so a lambda cannot be asked to tag a session with someone else's id.
- `customer_session(..., read_only=True)` adds an inline session policy allowing only GetItem, BatchGetItem and Query, so the effective rights are the intersection with the table above; every Clara read tool and every graph uses it, and only the assistant's rules write, under the normal session, on a confirming tap.
- `core.access` caches assumed credentials per warm environment under the whole `AssumeRole` request (role, session name, tags, session policy), at most 128, renewed 2 minutes before they expire; a cached session serves only that role and that `customer_id` tag, so the cache changes how often STS is called, never which role or tag a request gets.

## Migrations of note

None yet; nothing is built.
