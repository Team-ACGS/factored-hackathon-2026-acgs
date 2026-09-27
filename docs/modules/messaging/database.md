---
updated: 2026-09-27
source: setup
---

# Messaging: database

Status: designed, not built; no table exists yet, no schema is decided.
When it is, the schema lives in Terraform under `infra/modules/aws/*`, not here.

## Tables owned

| Table | Purpose |
|---|---|
| `rooms` | One row per conversation between a customer, Clara and, once a handoff happens, a human agent; also holds the customer's post-conversation rating (1 to 5) and optional comment; one of the 7 confirmed DynamoDB tables, keyed shape not yet designed [inferido: keys and columns] (the setup decisions of 2026-09-27, points 1 and 8) |
| `messages` | Every message in a room, written only by `lambdas/notifications`; a human agent's message reaches it through the same path as a bot's reply, API -> SQS -> notifications; ordering and retention not yet designed [inferido: keys and columns] (setup decision, 2026-09-27) |

## Tables referenced

None found.
Messaging does not read `complaints` (the table the cases module treats as the case record), `staff`, or the customer tables; the module boundary keeps chat transport separate from what is said about a case (module brief; setup decision, 2026-09-27).

## Invariants kept in code

- `messages` is written only by `lambdas/notifications`; a human agent's message takes the same path as a bot's reply, API -> SQS -> notifications, never a direct write from `apps/support` (setup decision, 2026-09-27).
- Table definitions live in `infra/`, not in any module's code; identity owns the IAM roles that decide who may read or write `rooms`/`messages`, and a separate seed process (owner not decided) loads them (setup decision, 2026-09-27).
- A room outlives any single case: the room a human agent joins on handoff is the same one the customer was already in, never a new one (`docs/product/01-flows.md` flow 2, "agent joins the same chat window") [inferido].

## Migrations of note

- None yet, nothing is built.
