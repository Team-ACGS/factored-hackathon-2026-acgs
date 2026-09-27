---
updated: 2026-09-27
source: setup
---

# inbox: product

Status: designed, not built.

## Purpose

An officer who never sees an unranked, uncategorized pile of cases: inbox sorts every incoming case into the right area, orders it by what actually matters (money, risk, age, the legal clock, whether the customer has already been here before), and puts it in front of an officer who is on shift and speaks the customer's language.
The backoffice app is where that officer opens the case and does the human work: review evidence, start a chargeback, decide (`docs/product/01-flows.md`, v1 2026-09-26, flow 3).

## User flows

### A case arrives in the inbox

1. The assistant decides `CLAIM` or `PROTECT`, or an agent files or escalates a case from a live chat (`docs/product/01-flows.md` flow 2).
2. Inbox categorizes it: `CLAIM` to the disputes inbox, `PROTECT` to the fraud inbox, `CASE_STATUS` with an unresolved issue to the follow-up inbox (`docs/product/02-technical-flows.md`, black box B).
3. Inbox computes a priority score from amount, risk signals, age, days left to the country's legal deadline, repeat complainer or third contact; a regulator-channel or escalated case always sits at the top regardless of score.
4. Inbox assigns the case to the next eligible officer by round robin: area matches, status Active, shift covers now, and the officer speaks the customer's language.
5. If nobody is eligible, the case is held in the queue, flagged, and a supervisor is notified.

Errors and empty states: an empty queue shows nothing to work; a held case shows why it could not be assigned (no eligible officer).
Nothing beyond this is designed yet [inferido].

### Officer works the queue

1. The officer logs into the backoffice app and sees the ranked queue for their area, each case showing its score and the reason for each point.
2. The officer opens an assigned case and reviews the evidence already gathered.
3. The officer starts a chargeback if needed, and decides: upheld, denied, or needs more information from the customer.
4. The decision is written through the cases module, the case's single writer; the decision triggers the customer email: summary, outcome, case id, legal due date, and a rating link (`docs/product/01-flows.md` flow 3).

Errors and empty states: not designed yet [inferido].

## Rules

- The category comes only from the decision already made upstream (`CLAIM`, `PROTECT`, `CASE_STATUS` with an issue); inbox never re-derives intent from the conversation.
- The priority score is a formula with versioned weights, not a model: every case shows why it sits where it sits, and changing the weights is a policy change reviewed like any other (`docs/product/02-technical-flows.md`, black box B).
- A regulator-channel or escalated case is never outranked by score; it is always top of its queue.
- Eligibility requires area, Active status, current shift, and the customer's language; the roster genuinely has zero Portuguese-speaking officers on the fraud night shift, so the hold-and-flag path is an expected outcome for that combination, not a defect (`docs/problem-statement.md`, v1 2026-09-26, section 4.6: 129 of 1,200 agents speak Portuguese, 0 of 24 on the fraud night shift).
- Every decision about money stays with the officer, a person; inbox and the assistant never make it (`docs/product/01-flows.md` flow 3: "every decision about money is made here, by a person").
- The officer's resolution is written by cases' lambda, the case's single writer; inbox writes only the ranking and assignment fields on the same record (Sebastian's decisions, round 2, 2026-09-27).

## Out of scope

- Deciding when a case is created, or what decision (`CLAIM`, `PROTECT`, `HANDOFF`) produced it: assistant.
- The case record itself and every status transition (`Open`, `In Process`, `Escalated`, `Resolved`, `Rejected`, `Closed`), including the officer's resolution: cases.
- The agent console for a live-chat handoff, and labeling that conversation: cases (`apps/support`).
- The improvement console for the separate `analysts` Cognito group: a fourth web, not built now (Sebastian's decisions, round 2).
- Any decision about money: always the officer, never automated.

## Open questions

- Whether the ranked queue in the backoffice app updates in real time or only on refresh [inferido].
- Whether a held, unassigned case can be reassigned manually by a supervisor from this app, or is only flagged for action outside the system [inferido].
