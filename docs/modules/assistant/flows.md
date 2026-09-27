---
updated: 2026-09-27
source: setup
---

# assistant: flows

Status: designed, not built.
Full detail (the intent list, the policy table, the tool table) lives in `docs/tasks/_drafts/turn_flow.md` at the docs repo root; this page only carries the two diagrams that explain the shape of one turn.

## One turn

Runs once per customer message: it decides where the conversation stands, then whether to explain, ask, claim, protect or hand off.

```mermaid
stateDiagram-v2
  [*] --> Idle
  Idle --> Reading: read intent (products, transactions, complaints, case status)
  Reading --> Idle: answered

  Idle --> Locating: UNRECOGNIZED_CHARGE or NOT_ME
  Locating --> Clarifying: 0 or N candidate charges
  Clarifying --> Locating: customer provides a slot
  Locating --> Deciding: exactly 1 candidate

  Deciding --> Idle: EXPLAIN, customer recognizes the charge
  Deciding --> AwaitingConfirm: CLAIM or PROTECT

  AwaitingConfirm --> Writing: customer confirms
  AwaitingConfirm --> Deciding: customer declines
  Writing --> Idle: read-back confirms, reply sent
  Writing --> Handoff: read-back does not confirm

  Idle --> Handoff: HUMAN, 3rd contact, overdue promise, escalated or regulator case
```

Source: `docs/tasks/_drafts/turn_flow.md` (state machine), simplified to the states this module owns; every arrow is a rule, none is chosen by a model.

## Writing an action: confirm, then read back

Only `CLAIM` and `PROTECT` reach a write, and the customer never hears "done" before the write is read back.
Customer login is Cognito email and password; there is no OTP inside the chat, only explicit confirmation before the write.

```mermaid
sequenceDiagram
  participant U as Customer
  participant E as assistant
  participant TL as Tool (A1 block card / A2 create complaint)
  U->>E: confirms the proposed action
  E->>TL: call with an idempotency key
  TL-->>E: write result
  E->>TL: read back the affected row
  TL-->>E: current state
  alt read-back confirms
    E->>U: states only what was read back
  else read-back does not confirm
    E->>U: says the action failed, hands off to a human
  end
```

Source: `docs/product/02-technical-flows.md`, "Writes with confirmation and read-back"; `docs/tasks/_drafts/turn_flow.md`, step 10.
A retry with the same idempotency key never blocks a card or opens a case twice.
