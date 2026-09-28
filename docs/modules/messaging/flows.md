---
updated: 2026-09-27
source: 0003_walking_skeleton
---

# Messaging: flows

Status: built for customers (task 0003).

## Message round trip

The same path carries a customer's message, Clara's reply and, later, a human agent's message.
The request that sends a message only waits for the write; everything else reacts to the table's stream.
The client subscribes before it reads history or sends, so nothing falls between the two; it merges history, pushes and confirmations by `message_id`.

```mermaid
sequenceDiagram
    participant C as Customer or agent web
    participant GW as API Gateway
    participant M as lambdas/messages
    participant DDB as DynamoDB messages
    participant N as lambdas/chat_notifier
    participant Bot as lambdas/chatbot (assistant)
    participant Evt as AppSync Events

    C->>Evt: subscribe /rooms/<sub>/* (wait for the ack)
    C->>GW: GET /messages/rooms/latest
    GW-->>C: latest room, history, server_time
    C->>GW: POST /messages (pending clock)
    GW->>M: invoke (Cognito authorizer)
    M->>DDB: conditional write (room created if new)
    M-->>C: 201, or 200 on a retry (sent check)
    DDB-->>N: stream insert
    N->>Evt: publish to /rooms/{customer_id}/{room_id}
    Evt-->>C: push over the subscription
    DDB-->>Bot: stream insert, sender_type = customer only
    Bot->>Bot: skip if the room is delegated to a human
    Bot->>DDB: write the echo, id = successor of the answered id (sender_type = assistant)
    DDB-->>N: stream insert
    N->>Evt: publish the reply
```

Clara's reply never triggers Clara again: the chatbot mapping only passes `sender_type = customer`.
A record that fails three times goes to its consumer's DLQ, which unblocks the rest of that customer's messages.
