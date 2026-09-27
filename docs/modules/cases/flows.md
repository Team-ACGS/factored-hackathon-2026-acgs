---
updated: 2026-09-27
source: setup
---

# Cases: flows

Status: designed, not built.

## Case lifecycle

Cases creates the `Open` state only; every later transition is human, read but not written by this module (`hackathon/docs/domain/dispute-process.md`).

```mermaid
stateDiagram-v2
    [*] --> Open: intake, case id issued
    Open --> InProcess: officer assigned
    InProcess --> Resolved: ruling issued
    InProcess --> Rejected: denied
    InProcess --> Escalated: second instance or regulator
    Escalated --> Resolved: ruling issued
    Escalated --> Rejected: denied
    Resolved --> Closed: customer accepts
    Resolved --> Escalated: customer disagrees
    Rejected --> Escalated: customer disagrees
    Rejected --> Closed
    Closed --> [*]
```

## Handoff to the agent console

When the assistant decides `HANDOFF` (or an immediate `CLAIM`/`PROTECT` needs a human), it writes the case and the package through cases' own code, in-process, no lambda-to-lambda call; the agent console shows it and the agent takes over the same chat (`docs/product/01-flows.md` flow 2, `docs/product/02-technical-flows.md` black box A).

```mermaid
sequenceDiagram
    participant Chatbot as lambdas/chatbot (assistant + Cases' case code)
    participant Crud as lambdas/crud (agent/officer API, calls Cases' case code)
    participant Console as Agent console (apps/support)
    participant Agent as Agent

    Chatbot->>Chatbot: assistant decides HANDOFF, calls Cases' case-writing code in lambdas/core
    Note over Chatbot: creates the case at Open, attaches the handoff package (facts, actions, evidence, open questions, data warnings)
    Console->>Crud: fetch the prepared case
    Crud-->>Console: case + handoff package
    Console-->>Agent: shows the case
    Agent->>Agent: joins the same chat window, bot goes silent
    Agent->>Crud: resolve in chat, send to area, or request step-up
    Agent->>Crud: labels the conversation (bot right / wrong / should have escalated earlier)
```
