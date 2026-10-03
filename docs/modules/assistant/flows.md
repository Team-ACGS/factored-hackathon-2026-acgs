---
updated: 2026-10-03
source: 0020_rich_parts
---

# assistant: flows

Status: the open-mode turn is built (task 0019) with views, read-only asks and status events (task 0020); writing an action is the B4 design.
The full design is `docs/tasks/_drafts/chat_architecture.md` at the docs root.

## One turn (B1, B2)

```mermaid
flowchart TD
    A[Customer message on the stream] --> R{Reply already stored?}
    R -- yes --> E[Re-emit turn.completed]
    R -- no --> TM{Turn mark free, own, or older than 5 min?}
    TM -- no --> RETRY[Record fails and retries]
    TM -- yes --> TAP{Tap of Clara's latest ask?}
    TAP -- yes --> READ[Run the option's stored read] --> CTX
    TAP -- no --> FL{Safety floor on raw text}
    FL -- not_me or lost_stolen --> ST[Safety template: call the bank]
    FL -- nothing --> CTX[Context: name, locale, today, cards, last 3 exchanges, choice]
    CTX --> SUP[supervisor: Sonnet 4.6]
    SUP -- tool calls within budget --> STATUS[status event and turn status per round]
    STATUS --> TOOLS[tools under the read-only session, five rows shown]
    TOOLS --> SUP
    SUP -- reply: say, view, ask --> TIDY[tidy, counted] --> CHK{facts_check with allowed_asks}
    CHK -- pass --> FIN[render says, views with readings, asks with labels]
    CHK -- first failure --> SUP
    CHK -- second failure --> FB[template from what the tools read]
    SUP -- budget out, model down or crash --> FB
    FB --> FIN
    ST --> FIN
    FIN --> W[Write reply, clear the mark, turn.completed]
```

Only `supervisor` calls the model; every other box is code, and every value the customer reads comes from a tool's facts through `render`.

## Writing an action: confirm, then read back (B4)

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
