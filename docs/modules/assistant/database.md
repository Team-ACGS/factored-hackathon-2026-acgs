---
updated: 2026-09-28
source: 0006_customer_data_onboarding
---

# assistant: database

Status: `customers`, `products` and `transactions` are written and read by `crud` (task 0006); the turn's tools are designed, not built.

## Tables owned

None.
The turn engine is a reader of customer-owned data and a writer through tool calls; no table in the agreed design is described as owned by this module.

## Tables referenced

| Table | Owner module | Relationship |
|---|---|---|
| `customers`, `products`, `transactions` (PK `customer_id`) | seeded per demo customer by `crud` setup (profile on `customers`, cards, transactions); `infra/` defines the tables and identity owns the IAM roles that gate them | `crud` writes them for the customer app; the turn will read them only through tools Q1-Q4 and the `core` read models, with credentials scoped to one `customer_id` |
| `complaints` (PK `customer_id`, GSI by area and priority) | cases | This table is the case record, historical and new; read through Q5, written only through the `A2 create complaint` and `A3 withdraw complaint` tools, which call the cases module's write code in the shared `lambdas/core` package (also used by `lambdas/crud`), never another lambda |
| `rooms` / `messages` | messaging | Triggered by new customer messages on the `messages` stream; reads the room to skip one delegated to a human; writes its reply through the messaging code in `lambdas/core`, the only writer of `messages` |

## Invariants kept in code

- No tool accepts `customer_id` as an argument; it always comes from the session's assumed-role credentials, never from client input (`docs/tasks/_drafts/turn_flow.md`); in `crud` it is the token's `sub`, never the body, path or cursor.
- Every read of `customers`, `products` or `transactions` goes through the allow-lists in `core.customers` and `core.accounts`, used both as projection and as mapping: `transactions.origin` (`setup`, `manual_normal`, `manual_suspicious`), `customers.setup_claimed_at` and `customers.suspicious_suffixes` never reach the app or a tool, so nothing reveals which charges were planted.
- `origin` is written only by `crud`.
- Setup completes once: a conditional claim on the `customers` row, the account derived only from that claim and written with idempotent overwrites, and a conditional completion last.
- A suspicious merchant suffix is unique per customer, reserved atomically in `customers.suspicious_suffixes` before the transaction is written.
- Q1 (customer info) never returns the document number to the model (`docs/tasks/_drafts/turn_flow.md`, tools table).
- Q5 (complaints) never returns `affected_product_id` or `claimed_amount` (`docs/tasks/_drafts/turn_flow.md`, tools table); `docs/problem-statement.md` 4.7 explains why: the affected product belongs to another customer in 100% of complaint rows in the source dataset, and the claimed amount matches no charge of the customer.
- Every write carries an idempotency key so a retry cannot block a card or open a case twice (`docs/product/02-technical-flows.md`, "Writes with confirmation and read-back").
- A card already `Blocked` is never blocked again; the engine opens a case and hands off instead (`hackathon/docs/domain/triage.md`).

## Migrations of note

- None; the setup profile and suffixes are new attributes on existing `customers` rows, no key changed.
