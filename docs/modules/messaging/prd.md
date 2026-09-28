---
updated: 2026-09-27
source: 0003_walking_skeleton
---

# Messaging: product

Status: built for customers talking to Clara (task 0003); agent handoff and rating are designed, not built.

## Purpose

A customer, Clara and, once a handoff happens, a human agent all speak in what looks like one continuous chat window (`docs/product/01-flows.md`, v1 2026-09-26, flow 2: "agent joins the same chat window").
This module is what makes that true: it holds the room's history and delivers each new message to whoever is watching, without the customer ever noticing that the transport changed from a bot's turn to a person typing.
It also solves a latency problem: Claude composing a reply can take longer than an API Gateway request should wait, so the reply is delivered asynchronously instead of held on the connection (module brief, confirmed architecture).

## User flows

### Customer sends a message, Clara replies

1. The customer types in the chat window and sends.
2. The reply does not come back on that same request; it arrives moments later in the same window, pushed to the browser.
3. The customer never sees a spinner tied to a timeout: the message shows a clock until the bank confirms it, then a check, and the reply appears on its own.
4. Reloading the chat shows the latest conversation in order.

Errors and empty states: a message that cannot be sent after automatic retries shows "not sent" with a retry; if the live connection drops, the chat says so and asks for a reload; there are no read receipts.

### Human agent joins the same window

1. The assistant hands a case off to a human (`docs/product/01-flows.md` flow 2).
2. The agent console (owned by cases) opens the prepared case and the agent joins the same chat window the customer has been in the whole time; nothing about the history resets.
3. From here the bot stays silent and the agent's messages reach the customer through the same window.

Source: `docs/product/01-flows.md` flow 2; `docs/product/02-technical-flows.md` black box A.
Errors and empty states: not designed yet [inferido].

### Customer rates the conversation

1. After a case is created, transferred or resolved, the customer receives an email with a rating link (`docs/product/02-technical-flows.md`, "Feedback email and rating").
2. The customer picks 1 to 5 and can leave a comment.
3. The rating and comment are stored on the room itself, not on a separate feedback record (setup decision, 2026-09-27).

Errors and empty states: not designed yet [inferido].

## Rules

- The customer-facing request that sends a message never waits for Clara's reply; it confirms the write, and the reply arrives over the room's realtime channel.
- The room the human agent joins is the same room the customer was already in; a handoff never starts a fresh conversation the customer has to repeat themselves into (`docs/product/01-flows.md` flow 2, and the measured goal "re-asks per handoff").
- Once a room is delegated to a human, "the bot goes silent" (`docs/product/01-flows.md` flow 2): the assistant reads `delegated_to_human` and does not answer; messaging still delivers everything.
- A human agent's message arrives for the customer exactly the way a bot's reply does; nothing about how a message shows up changes when a person takes over the same window (setup decision, 2026-09-27).
- The customer's rating (1 to 5, optional comment) lives on the room; there is no separate feedback record to keep in sync (setup decision, 2026-09-27).

## Out of scope

- Deciding what Clara says, or when a handoff happens: that is the assistant module.
- The case record, its status and its lifecycle: that is the cases module.
- Categorizing, ranking or assigning a case to an analyst: that is the inbox module.
- Who is authenticated and which group they belong to: that is identity; messaging only reads the result.

## Open questions

- Whether a room can exist before any complaint (case) does (a customer asking a question that resolves as `EXPLAIN`, no claim ever opened), or a room is only created once a claim or handoff happens; `docs/product/01-flows.md` flow 1 shows plain Q&A happening in the same chat, which suggests rooms predate complaints, but no source states it directly [inferido].
- Whether message content reaching this module has already passed the assistant's grounding check, or messaging is expected to do anything with it beyond store and forward; the reply is written as an ordinary message [inferido].
