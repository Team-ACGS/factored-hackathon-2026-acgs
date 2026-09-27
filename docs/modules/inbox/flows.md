---
updated: 2026-09-27
source: setup
---

# Inbox: flows

Status: designed, not built.

## Categorize, rank, assign

Runs once per case, when the case arrives from the assistant or from an agent's transfer (`docs/product/02-technical-flows.md`, black box B).

```mermaid
flowchart TD
    N[New case] --> CAT[Categorize: CLAIM to disputes,<br/>PROTECT to fraud,<br/>CASE_STATUS with issue to follow-up]
    CAT --> SC[Priority score: amount, risk,<br/>age, days to legal deadline,<br/>repeat contact, regulator or escalated always top]
    SC --> RK[Ranked queue for the area]
    RK --> EL{Eligible officer?<br/>area, Active, on shift, speaks the language}
    EL -->|yes| ASG[Assign by round robin,<br/>advance the area's pointer]
    EL -->|no| HOLD[Held in queue, flagged,<br/>supervisor notified]
    ASG --> AN[Officer sees the case<br/>with its score and reasons]
```

## Assignment eligibility, as a sequence

```mermaid
sequenceDiagram
    participant Case as New case (from assistant or agent)
    participant Inbox as Inbox
    participant Roster as staff table
    participant Officer as Assigned officer

    Case->>Inbox: category + score
    Inbox->>Roster: eligible officers for this area, now, this language
    Roster-->>Inbox: list, or empty
    alt at least one eligible
        Inbox->>Inbox: pick next by round robin, advance pointer
        Inbox-->>Officer: case appears in the ranked queue
    else none eligible
        Inbox-->>Inbox: hold, flag
        Inbox-->>Roster: notify supervisor
    end
```
