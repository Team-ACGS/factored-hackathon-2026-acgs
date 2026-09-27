---
updated: 2026-09-27
source: setup
---

# assistant: database

Status: designed, not built.
No schema exists yet; this describes what is agreed, not a live table definition.

## Tables owned

None.
The turn engine is a reader of customer-owned data and a writer through tool calls; no table in the agreed design is described as owned by this module.

## Tables referenced

| Table | Owner module | Relationship |
|---|---|---|
| `customers`, `products`, `transactions` (PK `customer_id`) | loaded by a separate seed process, owner not decided; `infra/` defines the tables and identity owns the IAM roles that gate them | Read only, through tools Q1-Q4, with credentials scoped to one `customer_id` |
| `complaints` (PK `customer_id`, GSI by area and priority) | cases | This table is the case record, historical and new; read through Q5, written only through the `A2 create complaint` and `A3 withdraw complaint` tools, which call the cases module's write code in the shared `lambdas/core` package (also used by `lambdas/crud`), never another lambda |
| `rooms` / `messages` | messaging | Only reached on `HANDOFF`, when the conversation moves to a human; only `lambdas/notifications` writes `messages`, including messages a human agent sends |

## Invariants kept in code

- No tool accepts `customer_id` as an argument; it always comes from the session's assumed-role credentials, never from client input (`docs/tasks/_drafts/turn_flow.md`).
- Q1 (customer info) never returns the document number to the model (`docs/tasks/_drafts/turn_flow.md`, tools table).
- Q5 (complaints) never returns `affected_product_id` or `claimed_amount` (`docs/tasks/_drafts/turn_flow.md`, tools table); `docs/problem-statement.md` 4.7 explains why: the affected product belongs to another customer in 100% of complaint rows in the source dataset, and the claimed amount matches no charge of the customer.
- Every write carries an idempotency key so a retry cannot block a card or open a case twice (`docs/product/02-technical-flows.md`, "Writes with confirmation and read-back").
- A card already `Blocked` is never blocked again; the engine opens a case and hands off instead (`hackathon/docs/domain/triage.md`).

## Migrations of note

- None; no table exists yet. [inferido]
