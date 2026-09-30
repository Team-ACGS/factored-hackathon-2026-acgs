---
updated: 2026-09-30
source: 0011_customer_redesign_fidelity
---

# assistant: product

Status: the customer app is a bank app with Clara as its agent (task 0010): cards, movements, help and claims, a Clara button and launcher, and a chat whose turns are simulated on the client from the customer's real data (see ard.md, the mocked chat); the backend turn below is designed, not built.

## Purpose

A customer who sees a card charge they do not recognize gets, in the same chat, a decision grounded in their own account facts: the charge is explained, a claim is opened, or the card is protected, instead of the single path today's bank offers (call, wait, explain, leave with an open claim).
`docs/problem-statement.md` sections 2-3 frame why this matters: today one contact type is treated as one situation when it is four, and only 43.6% of complaints resolve on first contact against 91.5% for other inquiries (`docs/problem-statement.md` 4.1).
The module also protects the customer within one turn when the words say fraud, instead of waiting on a score that only catches 55% of it (`docs/problem-statement.md` 4.4).

## User flows

### First entry: a demo account to try Clara on

1. A new customer signs in and gets a setup dialog: country (Peru, Mexico, Colombia, Argentina, United States, Brazil) and language.
2. Setup creates two credit cards and one debit card with three months of purchases at the country's usual merchants, in its currency, with the dataset's mix of approved, declined, pending and reversed charges.
3. A one-time guide shows the three charges planted for Clara to explain (a recent hold, a refunded charge, an old pending charge) and what Clara should do with each; it is never shown again.
4. From the demo links in the footer, the customer adds a normal purchase or a suspicious one (an online merchant they never used, with the bank's score chosen from three options), which shows at once while the bank fills it in.
5. Clara appears in the bank only as her button and the bank's own entry points ("Talk to Clara" on a movement, "Ask Clara" on a claim, the Clara card in Help); each opens the chat with that topic already started.
6. The chat shows the conversation on the left and a panel on the right (a bottom sheet on phones) with cards, movements, the charge, confirmations, receipts and the person who takes over; every choice asks for confirmation, the confirmed choice steps aside while Clara works, and a block or claim made there shows in the bank pages for the session.

Errors and empty states: setup runs once; a second attempt is refused and a half-done one finishes with the same data.

### Unrecognized charge, explained

1. Customer sees a charge in the app and says they do not recognize it, or asks a free question.
2. The assistant looks at the customer's own transaction and product facts.
3. If the facts explain the charge (already reversed, never charged, a fresh hold, or a match with the customer's own merchant history), it says so and the conversation ends there.
4. If shown prior purchases at the same merchant, the customer can recognize the charge and close without a claim.

Source: `hackathon/docs/domain/triage.md`, decision table; `docs/product/01-flows.md` flow 1.

### Unrecognized charge, claimed

1. Facts do not explain the charge and nothing signals fraud.
2. The assistant asks the one clarifying question about the card, per `hackathon/docs/domain/triage.md`.
3. If the customer still does not recognize it, the assistant confirms before acting, opens a claim, and reads back the result.
4. The customer receives a case id; no due date or legal term is ever stated (Sebastian, 0010).

Errors and empty states: if the write cannot be confirmed on read-back, the customer is told it failed and the case is hand off to a human instead of a silent retry (`docs/tasks/_drafts/turn_flow.md`, step 10).

### Unrecognized charge, protected

1. The customer says the charge was not theirs, or the facts carry a fraud signal (bank score, unusual country or channel, several unrecognized charges).
2. The assistant offers to block the card, confirms, and only after the block is confirmed by reading back the card's status does it tell the customer the card is blocked.
3. The case is opened and handed to a human on the fraud team.

Errors and empty states: a card that is already blocked is never blocked again; the assistant opens the case and hands off without a second write (`hackathon/docs/domain/triage.md`).

### Handoff to a human

1. Certain situations stop automation entirely: a third contact about the same case, an overdue promise, an escalated or regulator case, or the customer asking for a person.
2. The assistant does not attempt to decide; it hands off with a package of verified facts, actions already taken, evidence and open questions.
3. The customer's next message is answered by a human agent, not the bot.

Source: `docs/product/01-flows.md` flow 2; `hackathon/docs/kickoff-compliance.md` section 1, "Hand off to a human when needed".

## Rules

- The assistant never states that a charge is or is not fraud; it says it will protect the card and hand off, per `hackathon/docs/domain/triage.md`.
- The assistant never decides about money: no provisional credit, no refund, that is always a human decision downstream (`hackathon/docs/dispute-process.md`).
- The assistant never unblocks a card; that needs stronger identity and a human.
- When facts and signals leave doubt between claim and protect, the assistant protects: an unnecessary block costs a card replacement, a missed one costs everything spent until someone acts.
- Any legal due date the assistant quotes must come from the country's verified deadline table; `hackathon/docs/domain/legal-deadlines.md` is explicitly unverified as of 2026-09-26 and must not reach a customer as-is until checked against the primary legal text.
- A write (block a card, open a claim) only happens after the customer confirms, and the assistant only tells the customer it happened after reading the result back, never on request alone.
- The customer only ever sees their own data, never another customer's, never an invented deadline, never a promise of a specific agent (`docs/product/01-flows.md` flow 1).
- A stale pending charge (older than 7 days) is never explained to the customer as "temporary" (`hackathon/docs/domain/triage.md`).
- Clara never answers her own messages, and says nothing in a room delegated to a human.
- The customer app speaks English, Spanish or Brazilian Portuguese: before sign-in the customer picks it (browser language by default), sign-up stores it as the Cognito `locale`, the setup confirms it into the profile, and the profile drives the app from then on; there is no other switcher.
- Nothing the customer sees or Clara reads reveals which charges were planted or added as suspicious.

## Out of scope

- Anything after a claim is opened: internal analysis, chargeback, the ruling, and any movement of money are human and network work the assistant only reads status from (`hackathon/docs/dispute-process.md`).
- Detecting fraud with a model: the bank's score already exists; this module acts on what the customer says in addition to it, it does not replace or improve the score (`docs/problem-statement.md` section 11).
- Officer-facing case work (categorizing, ranking, assigning, resolving): owned by the inbox and cases modules.
- The live human agent chat surface itself once a handoff happens: owned outside this module.

## Open questions

- What share of unrecognized-charge conversations actually resolve as EXPLAIN in practice is expected to be low, 4.5 to 8% by the dataset's own numbers (`docs/problem-statement.md` 4.5); the product should lead with zero unsafe outcomes and correct first-contact claims, not with a deflection rate, but no target number is fixed yet. [inferido]
- Whether the one clarifying question ("do you have the card and have you used it yourself") is asked in every ambiguous case or only after signals are checked is drawn from the triage flow diagram; the exact ordering against the state machine in `docs/tasks/_drafts/turn_flow.md` is a draft still being reconciled. [inferido]
- Portuguese support for this module is entirely team-generated test data; there is no real Portuguese text in the dataset and no Portuguese-speaking fraud agent on the night shift to hand off to (`docs/problem-statement.md` 4.6). [inferido]
