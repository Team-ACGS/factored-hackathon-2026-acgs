---
updated: 2026-09-27
source: setup
---

# Messaging: flows

Status: designed, not built.

## Message round trip

Runs on every customer message, and again on every human agent message once a handoff has happened.
The reply never travels back on the request that sent the message; it arrives over the room's realtime channel instead, which is why `lambdas/chatbot` and `lambdas/notifications` never call each other directly (module brief; `docs/tasks/_drafts/architecture_and_layout.md`, "no lambda-to-lambda calls").

```mermaid
sequenceDiagram
    participant C as Customer (apps/customer)
    participant GW as API Gateway
    participant Bot as lambdas/chatbot (assistant)
    participant Q as SQS
    participant N as lambdas/notifications (messaging)
    participant DDB as DynamoDB rooms/messages
    participant Evt as AppSync Events

    C->>GW: send message
    GW->>Bot: invoke, request returns once accepted
    Bot->>Bot: understand, decide, compose (assistant module)
    Bot->>Q: publish finished reply
    Q->>N: deliver
    N->>DDB: write message to the room
    N->>Evt: publish to the room's channel
    Evt-->>C: push over WebSocket subscription
```

The same queue and the same consumer carry a human agent's message once the assistant hands the room off (`docs/product/01-flows.md` flow 2): API -> SQS -> notifications, confirmed for both bot and agent (setup decision, 2026-09-27).
Which lambda owns the API route an agent's message enters through before reaching SQS is not decided yet [inferido].
