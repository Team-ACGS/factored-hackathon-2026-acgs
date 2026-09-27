---
updated: 2026-09-27
source: setup
---

# Cases: database

Status: designed, not built.
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

## Invariants kept in code

- A case is only ever written at `Open`; no code path in this module sets any other status (`hackathon/docs/domain/dispute-process.md`).
- The `complaints` table has exactly one writer, this module's code in `lambdas/core`; the inbox module writes only ranking and assignment fields on the same row, never the case's own status or content.
- The handoff package attached to a case is written once, by the assistant module, at handoff time; cases does not mutate its content, only its visibility to an agent [inferido, boundary given for this module].
- How a single case is looked up (case id as a sort key, or another path) given the table's partition key is `customer_id`, is not designed yet [inferido].

## Migrations of note

- None yet, nothing is built.
