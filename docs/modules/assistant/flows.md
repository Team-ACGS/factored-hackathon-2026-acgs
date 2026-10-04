---
updated: 2026-10-04
source: 0022_story_actions
---

# assistant: flows

Status: the open-mode turn (tasks 0019, 0020) and the story path with its writes (task 0022) are built.
The full design is `docs/tasks/_drafts/chat_architecture.md` at the docs root.

## One turn

```mermaid
flowchart TD
    A[Customer message on the stream] --> R{Reply already stored?}
    R -- yes --> E[Re-emit turn.completed]
    R -- no --> TM{Turn mark free, own, or older than 5 min?}
    TM -- no --> RETRY[Record fails and retries]
    TM -- yes --> TAP{Tap of Clara's latest ask?}
    TAP -- answer to a story ask --> STORY[core.story: write, read back, next ask or receipt]
    TAP -- which_one pick --> READ[Run the option's stored read] --> CTX
    TAP -- no --> FL{Safety floor on raw text}
    FL -- not_me or lost_stolen --> PICK[Lists to pick: newest movements or cards] --> FIN
    FL -- nothing --> CTX[Context: name, locale, today, cards, memories, last 3 exchanges, choice, topic, story]
    STORY --> COMP[compose: a story sentence, or the handoff summary] --> FIN
    CTX --> SUP[supervisor: Sonnet 4.6]
    SUP -- tool calls within budget --> STATUS[status event and turn status per round]
    STATUS --> TOOLS[tools under the read-only session, five rows shown]
    TOOLS --> SUP
    SUP -- reply: say, view, ask --> TIDY[tidy the reply and each say, counted] --> CHK{facts_check with allowed_asks}
    CHK -- pass --> FIN[render says, views with readings, asks with labels]
    CHK -- first failure --> SUP
    CHK -- second failure --> FB[template from the last tool round]
    SUP -- budget out, model down or crash --> FB
    FB --> FIN
    FIN --> W[Write reply with its effects, clear the mark, turn.completed]
```

Only `supervisor` and `compose` call the model; every other box is code, and every value the customer reads comes from a tool's facts through `render`. A free text with a story ask open is answered by the graph and the same ask is shown again; the rules, not the model, attach the bank's question after a charge is pointed at.

## A flagged charge, to the handoff

```mermaid
sequenceDiagram
  participant U as Customer
  participant S as core.story
  participant P as products
  participant C as complaints
  U->>S: taps "No fui yo" on was_it_you
  S->>S: memory unrecognized_charge (keyed by ask_id)
  S-->>U: fixed consent, card view, block_card
  U->>S: taps "Sí, bloquéala"
  S->>P: UpdateItem Blocked, blocked_by = ask_id, if Active
  S->>P: read back (ConsistentRead)
  S->>C: put case if absent (complaint_id = ask_id), read back
  S->>S: package, summary (compose or template)
  S->>C: summary, once
  S-->>U: receipts only for what read back, case view, effects
```

A redelivered confirmation finds its own `blocked_by`, case and summary and answers the same; a second tap is no longer an answer to Clara's latest message and writes nothing.
