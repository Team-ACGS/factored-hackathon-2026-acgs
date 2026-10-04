---
updated: 2026-10-04
source: 0022_story_actions
---

# Cases: product

Status: Clara opens cases and the customer sees them with what the person already knows (task 0022); the agent console is designed, not built.

## Purpose

A case is what the customer gets when their charge cannot be explained on the spot: a claim (`CLAIM`) or a block-and-transfer (`PROTECT`).
This module gives the case a record, a lifecycle, and gives the human agent who inherits it a console that shows what the assistant already verified, so the agent never has to ask the customer something they already said (`docs/problem-statement.md`, v1 2026-09-26, hypothesis H4).

## User flows

### Clara opens a case

1. Only on the customer's confirming tap (or a bare typed yes): a fraud case after a card block (or when the card was already blocked and the customer wants a person), a claim after the one card question and the claim confirmation, a service case when they ask for a person, an unblock or money back.
2. The case is read back before Clara says its code; if it cannot be read back she gives the bank's phone instead of a code.
3. The customer sees the case with its stage and "what the person already knows" (the request, the charge, what the bank noticed, the block and its read-back, the open question); for a fraud or service case also "a person at the bank will contact you", declared, since no live agent exists yet.


### Agent receives a handoff

1. The assistant decides `HANDOFF` (or the customer's `CLAIM`/`PROTECT` needs a human immediately) and prepares the package: verified facts, actions already taken with their read-back, evidence, open questions, and data warnings (`docs/product/02-technical-flows.md`, v1 2026-09-26, black box A).
2. The agent console shows the prepared case (`docs/product/01-flows.md`, v1 2026-09-26, flow 2).
3. The agent joins the same chat window the customer is in; the bot goes silent and only suggests replies and shows facts on the side.
4. The agent decides: resolve in chat and close with a note, send the case to the area (inbox), or request stronger identity (step-up) before acting.
5. The agent labels the conversation: bot was right, bot was wrong, or bot should have escalated earlier.

Errors and empty states: not designed yet [inferido].

### Case status follow-up

1. A customer who already has an open case asks about it.
2. The console (or the assistant, reading through cases) shows the case's status and its legal due date.

This flow is read-only for cases; the status values themselves are set by human work outside this module (`docs/domain/dispute-process.md`: "our system only creates the Open state and reads the others, every transition after Open is human").

## Rules

- A case is created at `Open` only; cases never sets any other status by itself (`docs/domain/dispute-process.md`).
- Status moves from `Open` through `In Process`, optionally `Escalated`, to `Resolved` or `Rejected`, and finally `Closed`; every one of those moves is made by a human, not by this module (`docs/domain/dispute-process.md`).
- The case carries the country's legal due date; that date is unverified against the primary legal text as of 2026-09-26 and must be corrected before it reaches a customer or an agent (`hackathon/docs/domain/legal-deadlines.md`).
- The handoff package and its summary are written by the assistant, once, when the case opens; cases stores them on the case and shows them.
- The agent's label on a conversation is the product's measurement of the handoff's quality (re-asks per handoff, hypothesis H4); cases is where that label is captured, even though scoring it is not this module's job [inferido].
- A case has a single writer: this module's code in the shared `lambdas/core` package, used in-process by both `lambdas/crud` (agents, officers) and `lambdas/chatbot` (Clara opening a case), never by a lambda calling another lambda. When an officer resolves a case from the backoffice queue (the inbox module's ranked view), that resolution still goes through this same code; inbox itself only ranks and assigns.
- Staff comes in three groups: `agents` (this module's live-chat console, `support.`), `officers` (bank staff who review complaints from the ranked queue, `backoffice.`, owned by inbox), and `analysts` (a fourth web for the improvement console, reserved, not built now); cases serves `agents` directly and is the write path both `agents` and `officers` use.

## Out of scope

- Deciding when a handoff happens, or what goes in the package: that is the assistant module.
- Categorizing, ranking or assigning a case to a specific officer: that is the inbox module.
- Any decision about money, chargebacks, or a ruling on the dispute: always human, outside the system entirely (`docs/product/01-flows.md` flow 3: "every decision about money is made here, by a person").

## Open questions

- Whether the agent console also shows the customer's older, unrelated cases, or only the one being handed off [inferido].
- Whether the "resolved in chat" outcome ever changes case status, or only adds a note while the case stays open for the area to formally close [inferido].
