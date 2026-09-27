---
updated: 2026-09-27
source: setup
---

# inbox: architecture decisions and debt

Status: designed, not built; entries below record decisions and open risks from the design, not debt from running code.

## 2026-09-27: inbox is a separate module from cases, with its own backoffice app

- Decision: inbox owns categorization, ranking and assignment, plus its own static SPA `apps/backoffice` (formerly named "analyst"), used by the `officers` group; it is not part of the agent console cases owns (`apps/support`), nor the separate `analysts`-group improvement console (a fourth web, not built now).
- Alternatives rejected: one inbox/queue concern folded into the cases module, since both work the same case record [inferido].
- Reason: cases owns the record and its lifecycle read path; inbox owns the mechanics of who gets the case next and in what order, a distinct concern with its own UI and its own eligibility logic (boundary given for this setup; staff naming confirmed by Sebastian's decisions, round 2, 2026-09-27).
- Debt created: none.
- Revisit when: never, unless the module boundary itself is revisited.
- Source: setup

## 2026-09-27: the priority score is a versioned formula, not a model

- Decision: ranking a case within its area uses a deterministic, versioned-weights formula (amount in USD, risk signals, age, days left to the legal deadline, repeat complainer or third contact, regulator or escalated always top), not a learned ranker.
- Alternatives rejected: a learned ranking model over the same features [inferido].
- Reason: `docs/product/02-technical-flows.md` (black box B) states the score "is a formula, not a model: every case shows why it sits where it sits"; changing a weight is treated as a policy change, reviewed like any other rule.
- Debt created: none, this is a deliberate design choice for explainability.
- Revisit when: never, unless the product decides ranking quality requires a learned component.
- Source: setup

## 2026-09-27: category comes from the assistant's decision, inbox never re-derives intent

- Decision: `CLAIM` maps to disputes, `PROTECT` to fraud, `CASE_STATUS` with an unresolved issue to follow-up; inbox reads that decision, it does not re-classify the conversation itself.
- Alternatives rejected: inbox running its own classifier over the case text to double-check the area [inferido].
- Reason: keeps the one place that decides intent (assistant's policy engine) authoritative, and avoids two systems disagreeing about the same case's category (`docs/product/02-technical-flows.md`, black box B).
- Debt created: none.
- Revisit when: a case needs to change area after intake for a reason the assistant's original decision did not capture (not designed).
- Source: setup

## 2026-09-27: assignment is round robin with a stored pointer, hold-and-flag on no eligible officer

- Decision: an eligible officer (area, Active status, shift covers now, speaks the customer's language) is picked by round robin with a next-pointer stored per area; with nobody eligible, the case is held in the queue, flagged, and a supervisor is notified.
- Alternatives rejected: load-based or performance-based assignment [inferido].
- Reason: `docs/product/02-technical-flows.md` (black box B) specifies round robin explicitly; the roster genuinely produces zero eligible officers for some combinations (Portuguese, fraud, night shift), so a hold path is required, not optional (`docs/problem-statement.md`, v1 2026-09-26, section 4.6: 0 of 24 fraud night-shift agents speak Portuguese).
- Debt created: promising "a Portuguese-speaking agent" at night for fraud is a promise the roster cannot keep; the product must never phrase the hold-and-flag outcome as a callback promise (`docs/problem-statement.md` section 4.6).
- Revisit when: the officer roster changes, or the product decides how the customer is told about a held case.
- Source: setup

## 2026-09-27: risk, the legal due date driving the priority score is unverified

- Decision: none yet, this is an open risk to carry into the build.
- Alternatives rejected: none.
- Reason: `hackathon/docs/domain/legal-deadlines.md` is explicitly "cited from memory, NOT verified against the current legal texts" as of 2026-09-26; the priority score's "days left to the legal deadline" term inherits that risk, same as the case's stored due date in the cases module.
- Debt created: any ranking that weighs an unverified deadline may over- or under-prioritize a case until that table is verified and turned into `legal_deadlines.yaml` per that document's own day-1 task.
- Revisit when: before the priority score reaches a real ranked queue.
- Source: setup

## 2026-09-27: the case record is the `complaints` table, a single writer, inbox writes only ranking and assignment

- Decision: there is no separate `cases` DynamoDB table; `complaints` (PK `customer_id`) is the case record, historical and new, with a GSI by area and priority for the staff queue. Cases' lambda is its single writer, including officer resolutions; inbox writes only the ranking and assignment fields on the same item, through `role-officer`.
- Alternatives rejected: a dedicated `cases` table separate from `complaints`, as sketched in the pre-split `docs/tasks/_drafts/turn_flow.md` draft; an inbox-owned writer for its own fields on a table it does not otherwise own.
- Reason: Sebastian's decisions, round 2, 2026-09-27, settle both the table shape (confirming `turn_flow.md`'s GSI-by-area and priority-sort-key sketch, renamed from `cases` to `complaints`) and the single-writer rule (`cases` module's lambda owns all case content, `role-agent`/`role-officer`/`role-analyst` are the scoped IAM roles per staff group).
- Debt created: none, this replaces the prior open risk outright.
- Revisit when: never, unless the single-writer rule itself is revisited.
- Source: setup
