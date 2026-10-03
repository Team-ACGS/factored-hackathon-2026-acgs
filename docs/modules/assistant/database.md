---
updated: 2026-10-03
source: 0019_open_mode_graph
---

# assistant: database

Status: `customers`, `products` and `transactions` are written and read by `crud` (task 0006); the read tools in `core.tools` read them (task 0012), called by the `open_mode` graph (task 0019) only under the read-only session.

## Tables owned

| Table | Purpose |
|---|---|
| `memory` | What Clara learned about the customer across conversations: charges and merchants they recognized, with their own words as `note`. Keyed by `customer_id` and `memory_key` (`recognized_charge#<transaction_id>`, `recognized_merchant#<merchant>`). Read only by `recall` and `charge_facts`; the writes come with A2. |

## Tables referenced

| Table | Owner module | Relationship |
|---|---|---|
| `customers`, `products`, `transactions` (PK `customer_id`) | seeded per demo customer by `crud` setup (profile on `customers`, cards, transactions); `infra/` defines the tables and identity owns the IAM roles that gate them | `crud` writes them for the customer app; the tools read them only through the `core` read models, with credentials scoped to one `customer_id` |
| `complaints` (PK `customer_id`, GSI by area and priority) | cases | The case record; `case_status` reads it through `core.cases`; `crud` setup writes the seeded claim through the same module |
| S3 Vectors index `policies` (one vector per document excerpt) | data (`build-policies`) | `search_policies` queries it with the country as a filter; the excerpt's text, lineage and figures come back in the vector metadata, so no bucket is read |
| `rooms` / `messages` | messaging | Triggered by new customer messages on the `messages` stream; reads the room to skip one delegated to a human, takes and clears the room's turn mark, reads the 6 messages before the one it answers, and writes its reply (with `parts`, `facts`, `draft`, `source`) through the messaging code in `lambdas/core`, the only writer of `messages` |

## Invariants kept in code

- No tool accepts `customer_id` as an argument; it always comes from the session's assumed-role credentials, never from client input (`docs/tasks/_drafts/turn_flow.md`); in `crud` it is the token's `sub`, never the body, path or cursor.
- Every read of `customers`, `products` or `transactions` goes through the allow-lists in `core.customers` and `core.accounts`, used both as projection and as mapping: `transactions.origin` (`setup`, `manual_normal`, `manual_suspicious`), `customers.setup_claimed_at` and `customers.suspicious_suffixes` never reach the app or a tool, so nothing reveals which charges were planted.
- `origin` is written only by `crud`.
- A new transaction enters only through `core.ingestion.accept`: the row passes contract v`TRANSACTION_CONTRACT_VERSION` (undeclared fields refused, so no lineage fields) and is written in one TransactWriteItems with its card's balance move, so a `transaction_id` is written once, moves the balance once, and the balance never moves without its row.
- Only an Approved charge moves `products.current_balance`: credit adds the amount used and may not pass `credit_limit`, debit subtracts from the funds and may not go negative; each move stamps `balance_as_of`, and `card_status` shows a balance only with it.
- Setup writes its generated rows in bulk, checked against the contract but moving no balance: the generator seeds balances consistent with its own history and stamps `balance_as_of` with the setup claim.
- Setup completes once: a conditional claim on the `customers` row, the account derived only from that claim and written with idempotent overwrites, and a conditional completion last.
- A suspicious merchant suffix is unique per customer, reserved atomically in `customers.suspicious_suffixes` before the transaction is written.
- Every tool reads under `customer_session(..., read_only=True)`, whose session policy allows only GetItem, BatchGetItem and Query, so a tool cannot write even through a bug.
- Every tool projects only what its facts need: no tool returns `origin`, `is_fraud`, a raw `fraud_score` (only `charge_facts` reads it, and emits a band), a full `product_number` (only `last4`), `affected_product_id`, `claimed_amount`, compensation or SLA fields; `docs/problem-statement.md` 4.7 explains the complaint fields: the affected product belongs to another customer in every source row, and the claimed amount matches no charge.
- A ref the customer does not own is `not_found`, never an error that tells it exists.
- A tool returns facts only; a value the model may say is a renderable fact read from a table or the merchant lexicon, never a raw tool argument echoed back.
- Tools never read the clock: customer, country, language and now come from the caller's context.
- Every write carries an idempotency key so a retry cannot block a card or open a case twice (`docs/product/02-technical-flows.md`, "Writes with confirmation and read-back").
- A card already `Blocked` is never blocked again; the engine opens a case and hands off instead (`hackathon/docs/domain/triage.md`).

## Migrations of note

- None; the setup profile and suffixes are new attributes on existing `customers` rows, no key changed.
