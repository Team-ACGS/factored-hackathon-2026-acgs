---
updated: 2026-10-04
source: 0022_story_actions
---

# Cases: database

Status: `core.cases` reads the contract below (task 0012); `crud` setup writes the seeded claim; Clara opens fraud, claim and service cases (task 0022).
The schema itself lives in `infra/` (Terraform); this file says what cases owns and must keep true, not columns or types.

## Tables owned

| Table | Purpose |
|---|---|
| `complaints` | The case record; complaints ARE the cases, both historical rows from the bank dataset and new ones Clara opens. Keyed by `customer_id`, with a GSI by area and priority for the staff queue. |

`infra/` defines this table; the identity module owns the IAM roles that decide who may read or write it; a separate seed process (owner not decided) loads the historical rows.
Cases is the table's single writer, through this module's code in the shared `lambdas/core` package, called in-process by both `lambdas/crud` (agent/officer resolutions) and `lambdas/chatbot` (Clara opening a case); inbox never writes it directly.

## Tables referenced

| Table | Owner module | Relationship |
|---|---|---|
| `staff` | inbox | Area, shift and language per agent/officer; read to check eligibility and identity, not owned by cases |

## The complaints contract

`core.cases` reads only an allow-list: the dataset's `status`, `creation_date`, `assignment_date`, `first_response_date` (the in-review instant), `resolution_date`, `closing_date`; `area`; the disputed charge's `transaction_id` and `product_id`; and the handoff summary (`summary`, `summary_points`, `summary_language`, `summary_generated_at`, `summary_source` = `compose` or `template`), written later by the rules.

- Type from `area`: `fraud` to fraud, `claims` to claim, `service` to service, any other area to claim.
- Stage from `status`: Open is opened, or assigned once `assignment_date` is set; In Process and Escalated are in review; Resolved and Rejected are resolved (the outcome is never stated); Closed is closed.
- Display code: `case_code(complaint_id, opened_at)`, the same FNV-1a hash and `CLR-YYYY-NNNNNN` shape as the app's `claimId`.

## Invariants kept in code

- A case is only ever written at `Open`; no code path in this module sets any other status (`hackathon/docs/domain/dispute-process.md`). The one exception is the demo's seeded claim, written by setup already `In Process` with its stage dates.
- The seeded claim's `complaint_id` is the disputed `transaction_id`, written only if absent, so its code equals the app's `claimId` for the same charge and a resumed setup writes it once.
- No read returns the agent, `affected_product_id`, `claimed_amount`, compensation, resolution amounts or SLA fields.
- The `complaints` table has exactly one writer, this module's code in `lambdas/core`; the inbox module writes only ranking and assignment fields on the same row, never the case's own status or content.
- A case Clara opens has `complaint_id` equal to the `ask_id` the customer confirmed, `reception_channel clara`, `case_type` from its area, and is written only if absent, so a redelivered or double-tapped confirmation finds the same case.
- `evidence` (room, ask and message ids, the charge) is on the row for the agent and outside the read allow-list, so no customer read returns it.
- The summary fields are written once, only while `summary` is absent; cases does not mutate them.
- A single case is looked up by its sort key `complaint_id` under the customer's partition.

## Migrations of note

- None; the seeded claim is a new row, and accounts set up before task 0012 have none.
