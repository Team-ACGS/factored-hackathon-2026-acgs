---
updated: 2026-09-27
source: task 0002
---

# Messaging: flows

Status: infrastructure built (task 0002), code not built.

## Message round trip

The same path carries a customer's message, Clara's reply and a human agent's message.
The request that sends a message only waits for the write; everything else reacts to the table's stream.

```mermaid
sequenceDiagram
    participant C as Customer or agent web
    participant GW as API Gateway
    participant M as lambdas/messages
    participant DDB as DynamoDB messages
    participant N as lambdas/chat_notifier
    participant Bot as lambdas/chatbot (assistant)
    participant Evt as AppSync Events

    C->>GW: POST /messages
    GW->>M: invoke (Cognito authorizer)
    M->>DDB: conditional write (room created if new)
    M-->>C: 2xx, message confirmed
    DDB-->>N: stream insert
    N->>Evt: publish to /rooms/<room_id>
    Evt-->>C: push over the subscription
    DDB-->>Bot: stream insert, sender_type = customer only
    Bot->>Bot: skip if the room is delegated to a human
    Bot->>DDB: write the reply as a message (sender_type = assistant)
    DDB-->>N: stream insert
    N->>Evt: publish the reply
```

Clara's reply never triggers Clara again: the chatbot mapping only passes `sender_type = customer`.
A record that fails three times goes to its consumer's DLQ, which unblocks the rest of that customer's messages.
