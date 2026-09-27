---
updated: 2026-09-27
source: setup
---

# Inbox: database

Status: designed, not built.
DynamoDB has exactly 7 tables, defined in `infra/`: `customers`, `products`, `transactions`, `complaints`, `staff`, `rooms`, `messages` (Sebastian's decisions, round 2, 2026-09-27).
There is no separate `cases` table and no `users` table; `cases` is a module name only, and users are Cognito.

## Tables owned

- `staff`: one row per agent and officer (area, shift, languages, availability), keyed by the person's Cognito user id; inbox maintains it, `cases` only reads it. Login data stays in Cognito.

Inbox also writes ranking and assignment fields onto `complaints`, owned by cases, and its round-robin pointer per area lives within one of the 7 confirmed tables; exactly which one is not yet designed [inferido].

## Tables referenced

| Table | Owner module | Relationship |
|---|---|---|
| `complaints` | cases | The case record, historical and new, PK `customer_id`, with a GSI by area and priority for the staff queue; cases' lambda is the single writer of case content and officer resolutions, inbox writes only the ranking and assignment fields on the same item (Sebastian's decisions, round 2) |

## Invariants kept in code

- Inbox never writes case content or status on `complaints`; it writes only the ranking and assignment fields (priority score, assigned officer), through `role-officer` (Sebastian's decisions, round 2).
- The round-robin pointer for an area advances exactly once per assignment made, never on a read of the queue [inferido].

## Migrations of note

- None yet, nothing is built.
