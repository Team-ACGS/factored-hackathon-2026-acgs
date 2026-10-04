---
updated: 2026-10-04
source: 0021_open_mode_polish
---

# assistant: product

Status: the customer app is a bank app with Clara as its agent (task 0010); her chat talks to the live turn (task 0019), which answers free questions about the customer's own money with the bank's own screens of what she read and read-only choices (task 0020), and sends "not me" or "lost or stolen" to the bank's phone; the flagged-charge story with asks, claims, blocks and handoff (B4) is designed, not built.

## Purpose

A customer who sees a card charge they do not recognize gets, in the same chat, a decision grounded in their own account facts: the charge is explained, a claim is opened, or the card is protected, instead of the single path today's bank offers (call, wait, explain, leave with an open claim).
`docs/problem-statement.md` sections 2-3 frame why this matters: today one contact type is treated as one situation when it is four, and only 43.6% of complaints resolve on first contact against 91.5% for other inquiries (`docs/problem-statement.md` 4.1).
The module also protects the customer within one turn when the words say fraud, instead of waiting on a score that only catches 55% of it (`docs/problem-statement.md` 4.4).

## User flows

### First entry: a demo account to try Clara on

1. A new customer signs in and gets a setup dialog: country (Peru, Mexico, Colombia, Argentina, United States, Brazil) and language.
2. Setup creates two credit cards and one debit card with three months of purchases at the country's usual merchants, in its currency, with the dataset's mix of approved, declined, pending and reversed charges.
3. A one-time guide shows the three charges planted for Clara to explain (a recent hold, a refunded charge, an old pending charge) and what Clara should do with each; it is never shown again.
4. From the demo links in the footer, the customer adds a normal purchase or a suspicious one (an online merchant they never used, with the bank's score chosen from three options), which shows at once while the bank fills it in; an approved purchase moves the card's balance, and one the card cannot take is refused.
5. Clara appears in the bank only as her button and the bank's own entry points ("Talk to Clara" on a movement, "Ask Clara" on a claim, the Clara card in Help); each opens the chat with that topic already started.
6. The chat has two columns: the conversation on the left and Clara's panel on the right, where the bank's own screens of what she read appear (movements, cards, one card, one movement, a charge with her reading, a merchant history, a case) and where her choices are tapped. Her figure docks small when content appears. While she works the screen hides and she sits alone in the panel, with what she is checking ("Revisando tus movimientos") beside her and in the conversation, also after a reload; her look follows what she reads, and the screen returns with her answer. A screen that is not the latest answer's own is marked "de tu mensaje anterior". On a phone the panel is a drawer opened by the "Ver ..." link under an answer.
7. Inside a screen the customer moves without a new turn: a card to its movements, a movement to its detail, and back. A "Ver ..." link under an older answer reopens its screen.
8. Under an answer that used the bank's documents, "Cómo lo sé" opens, collapsed by default, with one chip per document and page (title and page, opening the PDF there); answers about the customer's own data show none.
9. Help lists the customer's open cases from the bank and the country's own phone.

Errors and empty states: setup runs once; a second attempt is refused and a half-done one finishes with the same data.

### A free question about my money (built, B1)

1. The customer writes anything, in their language: how much they spent at a merchant this month against last month, when their claim is resolved, what Clara knows about them.
2. If the text says the charge was not theirs or the card was lost or stolen ("no fui yo", "me robaron", "não fui eu", "perdi o cartão"), Clara answers at once, without the model, that the card is protected by calling the bank, with the country's phone, its hours and the number from abroad; she promises no callback.
3. Otherwise Clara reads what the question needs from the customer's own records and the bank's documents, and answers with the totals, dates, case codes and timeframes she read, each rendered by the bank's code in the customer's format; a sentence about the bank's process cites the document it comes from.
4. When she names movements, cards, a charge or a case, the panel shows them as the bank shows them; she says how many and names one or two, and the list is the screen's.
5. When the question matches a few charges or cards she cannot tell apart, she asks which one with buttons; a tap answers without a new search. "Hay una transacción que no reconozco" with no detail gets her five newest movements as buttons (merchant, amount, day), and the tap opens the charge with what the bank saw, its alert first. When more match than she can show, she asks for the date or the amount. She may offer, with one button, to show the rows behind a total.
6. Rankings, spending by category, statements and payments or due dates get a fixed answer that points to what Clara can do or to the bank's phone.
7. If Clara cannot check something (the model is down, slow or wrote a value it did not read), she answers from what she did read, or says she could not check it now; she never estimates.

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
- How the bank works (claim steps and times, blocks, replacements, holds, reversals, fees, contact channels) is answered only from the bank's own documents of the customer's country, each sentence citing the excerpt it uses, and the citation opens the document's PDF at that page; with no matching excerpt, Clara says she does not have it, never answers from the model's own knowledge.
- A cited sentence says only what its excerpt says; advice about what the customer can do, and what the bank does next, is said only with a citation. The customer's own words ("cancelar") reach the bank's documents through a glossary of the bank's terms ("bloquear").
- A policy figure (a time, a fee, a phone) is said only as a reference to the excerpt's figures, rendered from the same facts the rules read, so a document and a rule cannot disagree; a timeframe is the bank's process, never a promise.
- Legal deadlines are the bank's reading of each norm, flagged unverified (`policy_facts.toml`, `verified = false`), and must not reach a customer as-is until checked against the primary legal text.
- A write (block a card, open a claim) only happens after the customer confirms, and the assistant only tells the customer it happened after reading the result back, never on request alone.
- The customer only ever sees their own data, never another customer's, never an invented deadline, never a promise of a specific agent (`docs/product/01-flows.md` flow 1).
- A stale pending charge (older than 7 days) is never explained to the customer as "temporary" (`hackathon/docs/domain/triage.md`).
- Clara never answers her own messages, and says nothing in a room delegated to a human.
- Every value Clara says (an amount, a date, a count, a merchant, a card's last digits, a case code, a policy figure) is one she read this turn and the bank's code rendered; a reply with any other value is repaired once, then replaced by a template.
- Clara never promises a person will call or take over, and never says "fraud", that a charge is safe, or that money will come back, nor anything about what she can or cannot promise.
- Clara only offers to look things up and show them; until B4 her buttons never change the account.
- What the bank saw on a charge is said only as the bank's reasons, never as a risk level; Clara never says where things are on the screen.
- Clara never says anything about rows she was not shown, and never names a card brand: the bank's data has none, so cards are named by type and last digits.
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
