---
updated: 2026-09-27
source: setup
---

# Cases: architecture decisions and debt

Status: designed, not built; entries below record decisions and open risks from the design, not debt from running code.

## 2026-09-27: cases only ever writes the Open status

- Decision: this module creates a case at `Open` and reads every later status; it never writes `In Process`, `Escalated`, `Resolved`, `Rejected` or `Closed` itself.
- Alternatives rejected: letting cases drive the state machine end to end [inferido].
- Reason: every transition after `Open` is human work (analysis, chargeback, ruling), outside what an automated system should decide (`hackathon/docs/domain/dispute-process.md`).
- Debt created: none, this is a deliberate scope cut.
- Revisit when: the product decides to automate any post-intake transition.
- Source: setup

## 2026-09-27: the handoff package is authored by assistant, stored by cases

- Decision: cases stores and displays the handoff package (facts, actions with read-back, evidence, open questions, data warnings); it does not decide when a handoff happens or compose the package's content.
- Alternatives rejected: building the handoff logic inside the shared case-writing code itself [inferido].
- Reason: keeps the decision logic (rules table, grounding) in one place, the assistant module, and keeps cases a thin lifecycle owner (module boundary given for this setup; `docs/product/02-technical-flows.md`, black box A); assistant reaches cases by calling the shared `lambdas/core` package in-process, not by calling another lambda.
- Debt created: none.
- Revisit when: never, unless the module boundary itself is revisited.
- Source: setup

## 2026-09-27: the case is the `complaints` table, there is no separate `cases` table

- Decision: Sebastian confirmed DynamoDB has exactly seven tables (`customers`, `products`, `transactions`, `complaints`, `staff`, `rooms`, `messages`); `complaints` IS the case record, both historical rows and new ones Clara opens, keyed by `customer_id` with a GSI by area and priority for the staff queue. `cases` is a module name only, not a table.
- Alternatives rejected: a dedicated `cases` table keyed by `case_id`, as sketched in `docs/tasks/_drafts/turn_flow.md` before this decision.
- Reason: one case record shared with the bank's own historical complaints, instead of a parallel structure to keep in sync with it.
- Debt created: none, this supersedes the earlier draft outright; the draft's `case_id`-keyed, agent-role-readable sketch no longer applies.
- Revisit when: never, unless the seven-table decision itself is revisited.
- Source: setup

## 2026-09-27: staff reach case data through a GSI and an assumed role, never direct table access

- Decision: `lambdas/crud` reads `cognito:groups` from the staff token and calls the shared `lambdas/core` case code, which assumes `role-agent` or `role-officer` to query the `complaints` table through its GSI; no lambda reads the table directly, and there is no lambda-to-lambda call to get there. `infra/` defines the table; the identity module owns the IAM roles that decide who may do what on it.
- Alternatives rejected: a shared, unrestricted table role for all lambdas [inferido].
- Reason: same isolation pattern used for customer data (`LeadingKeys` by `customer_id`), applied to staff roles by group instead of by customer, one IAM role per capability (`docs/tasks/_drafts/architecture_and_layout.md`; staff naming and roles confirmed 2026-09-27).
- Debt created: none.
- Revisit when: a role needs finer scoping than "any agent" or "any officer" (e.g. area-scoped access).
- Source: setup

## 2026-09-27: apps/support is its own SPA, not a shared app with a role switch

- Decision: the agent console ships as its own static SPA, `apps/support`, at `support.factoredai.sdfles.com`, for the `agents` group (live chat) only. Officers (bank staff reviewing complaints from the ranked queue) get a separate app, `backoffice.factoredai.sdfles.com`, owned by inbox; a fourth app, `analysts.factoredai.sdfles.com`, is reserved for the improvement console and not built now.
- Alternatives rejected: one SPA with four views switching by role, proposed in `docs/product/01-flows.md` v1.
- Reason: arbitrated by Sebastian in favor of one SPA per role, one deploy unit and one Cognito app client each (`docs/tasks/_drafts/architecture_and_layout.md`; staff naming confirmed 2026-09-27).
- Debt created: none, this supersedes the earlier proposal outright.
- Revisit when: never, unless the per-role SPA split itself is revisited.
- Source: setup

## 2026-09-27: cases is the single writer of the case record, as shared code, not as one lambda

- Decision: the `complaints` row has exactly one writer: this module's code inside the shared `lambdas/core` package. That code is used, in-process, by both `lambdas/crud` (agent and officer reads and resolutions) and `lambdas/chatbot` (Clara opening a case); there is no lambda-to-lambda call between them, each bundles `lambdas/core` into its own zip. When an officer resolves a case from the backoffice queue (owned by inbox), that write still goes through this shared code via `lambdas/crud`. Inbox writes only the ranking and assignment fields on the same row.
- Alternatives rejected: letting inbox's backoffice app write case resolutions directly [inferido]; treating `lambdas/crud` alone as the single writer, which would leave `lambdas/chatbot`'s case creation as a second, undocumented write path (corrected 2026-09-27, after Sebastian's clarification).
- Reason: one piece of write code, shared by value (bundled into each zip) rather than called over the network, keeps the `Open`-only invariant and any future validation in one place without a lambda-to-lambda call.
- Debt created: none.
- Revisit when: never, unless the single-writer rule itself is revisited.
- Source: setup

## 2026-09-27: observability is Powertools plus CloudWatch and X-Ray, from day one

- Decision: every lambda that bundles `lambdas/core` (`lambdas/crud`, `lambdas/chatbot`) uses AWS Lambda Powertools for Python (Logger, Metrics, Tracer); `lambdas/core`'s case creation is idempotent through a conditional write; structured JSON logs to CloudWatch Logs, EMF metrics in namespace `Clara/Backend`, X-Ray active tracing on each lambda and the API Gateway stage.
- Alternatives rejected: none recorded.
- Reason: applies uniformly to every lambda in the system, decided 2026-09-27.
- Debt created: none.
- Revisit when: never, unless the observability stack itself changes.
- Source: setup

## 2026-09-27: risk, case status values are asserted by a domain doc, not verified against the data dictionary

- Decision: none yet, this is an open risk to carry into the build.
- Alternatives rejected: none.
- Reason: `hackathon/docs/domain/dispute-process.md` states the six status values and their mapping to `complaints.status` without citing the data dictionary; the actual column values in the dataset have not been cross-checked here [inferido].
- Debt created: the mapping table may not match reality once `lambdas/core`'s case code is built against real data [inferido].
- Revisit when: `lambdas/core` starts reading `complaints.status`; verify the value set then.
- Source: setup

## 2026-09-27: risk, the legal due date a case carries is unverified

- Decision: none yet, this is an open risk to carry into the build.
- Alternatives rejected: none.
- Reason: `hackathon/docs/legal-deadlines.md` is explicitly "cited from memory, NOT verified against the current legal texts" as of 2026-09-26.
- Debt created: any due date a case stores or displays is wrong until that table is verified and turned into `legal_deadlines.yaml` per that document's own day-1 task.
- Revisit when: before the due date reaches a customer or an agent in any built system.
- Source: setup
