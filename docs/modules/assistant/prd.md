---
updated: 2026-10-04
source: 0023_open_mode_polish_2
---

# assistant: product

Status: the customer app is a bank app with Clara as its agent (task 0010); her chat talks to the live turn (task 0019), which answers free questions about the customer's own money with the bank's own screens of what she read and read-only choices (task 0020), remembers what the customer told her about a charge, and acts with consent: asks about a flagged charge, blocks the card with read-back, opens cases with a prepared package and abstains on unblock and money (task 0022); always answers in the account's language, never repeats a fixed answer, and every question she asks brings its own screen (task 0023); Clara writing first is the next task.

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
6. The chat has two columns: the conversation on the left and Clara's panel on the right, where the bank's own screens of what she read appear (movements, cards, one card, one movement, a charge with her reading, a merchant history, a case) and where her choices are tapped. Her figure docks small when content appears, and the panel shows only the latest answer's screen: an answer without one leaves Clara alone. While she works the screen hides and she sits alone in the panel, with what she is checking ("Revisando tus movimientos") beside her and in the conversation, also after a reload; her look follows what she reads, and the screen returns with her answer. On a phone the panel is a drawer opened by the "Ver ..." link under an answer.
7. Inside a screen the customer moves without a new turn: a card to its movements, a movement to its detail, and back. A "Ver ..." link under an older answer is the only way back to its screen.
8. Under an answer that used the bank's documents, "Cómo lo sé" opens, collapsed by default, with one chip per document and page (title and page, opening the PDF there); answers about the customer's own data show none.
9. Help lists the customer's open cases from the bank and the country's own phone.

Errors and empty states: setup runs once; a second attempt is refused and a half-done one finishes with the same data.

### A free question about my money (built, B1)

1. The customer writes anything, in any language: how much they spent at a merchant this month against last month, when their claim is resolved, their largest purchase, whether those purchases were all in one city, what Clara knows about them. Clara answers in the account's language. A bare "ok", "gracias" or "beleza" gets one closing line.
2. If the text says the charge was not theirs or the card was lost or stolen ("no fui yo", "me robaron", "não fui eu", "perdi o cartão"), Clara answers at once, without the model: for a lost card, the cards with a choice of which active one, even when there is one; for "not me" with no charge in view, the five newest movements to pick from; both go to the block confirmation (below).
3. If they ask for something only a person does (unblock a card, money back, a person), Clara answers what she can check, says a person at the bank does that, and offers a person with a button; a service case opens only on yes.
4. Otherwise Clara reads what the question needs from the customer's own records and the bank's documents, and answers with the totals, dates, case codes and timeframes she read, each rendered by the bank's code in the customer's format; a sentence about the bank's process cites the document it comes from.
5. When she names movements, cards, a charge or a case, the panel shows them as the bank shows them; she says how many and names one or two, and the list is the screen's.
6. When the question matches a few charges or cards she cannot tell apart, she asks which one with buttons; a tap answers without a new search. "Hay una transacción que no reconozco" with no detail gets her five newest movements as buttons (merchant, amount, day), and the tap opens the charge with what the bank saw, its alert first. When more match than she can show, she asks for the date or the amount. She may offer, with one button, to show the rows behind a total.
7. Rankings, spending by category, statements and payments or due dates get a fixed answer that points to what Clara can do or to the bank's phone; the single largest purchase is a lookup and is answered. A fixed answer is never given twice in a row, and personal data Clara does not have (documents, addresses) gets a composed "no tengo acceso a ...".
8. If Clara cannot check something (the model is down, slow or wrote a value it did not read), she answers from what she did read, quotes the bank's excerpt she was citing, or says she could not check it now; she never estimates.

### A charge, from the bank's button or the newest movements

1. The customer taps "¿No reconoces este cargo?" on a movement, or picks one of the five newest movements in the chat.
2. Clara explains it from the bank's records and their history at that merchant (the purchases before, the typical amount, what the bank noticed), never saying whether it is theirs and never judging the amount.
3. A charge the bank flagged asks "¿Fuiste tú?" (yes, no, and "why are you asking", which explains what the bank noticed in plain words and asks again); any other charge asks "¿Reconoces este cargo?". Both take an optional note, and a charge already answered is never asked again: Clara says what they told her, with the note.
4. "Yes, it was me" is remembered with the customer's words; after three recognized charges at one merchant, the merchant is remembered too, which never makes what the bank saw on a charge less important.

### Protected

1. "It wasn't me", a typed "not me", or "I don't recognize it" on a charge with a warning sign (abroad, an unusual channel, declined, the bank's alert) leads to the fixed confirmation "¿Quieres que proteja tu tarjeta?" with the card on screen.
2. "Sí, bloquéala" blocks the card; Clara says it is blocked only after reading the card back, and the bank's pages show it at once.
3. A fraud case opens with what the person already knows (the request, the charge, what the bank noticed, the block and its read-back, the open question), and "a person at the bank will contact you", declared, since there is no live agent yet.

Errors and empty states: a card already blocked is never blocked again; Clara offers a person, whose yes opens the fraud case. A block or a case that does not read back is never announced: Clara says so, and gives the bank's phone when the case itself is not confirmed. "Ahora no" changes nothing.

### Claimed

1. "I don't recognize it" on a charge with no warning sign asks the one card question: do they have the card and have they used it these days.
2. No leads to the block confirmation; yes to the fixed claim confirmation and, on its yes, a claim case read back with its code. Clara stays in the conversation.
3. No due date or legal term is ever stated (Sebastian, 0010).

## Rules

- The assistant never states that a charge is or is not fraud; it says it will protect the card and hand off, per `hackathon/docs/domain/triage.md`.
- The assistant never decides about money: no provisional credit, no refund, that is always a human decision downstream (`hackathon/docs/dispute-process.md`).
- The assistant never unblocks a card; that needs stronger identity and a human.
- When facts and signals leave doubt between claim and protect, the assistant protects: an unnecessary block costs a card replacement, a missed one costs everything spent until someone acts.
- How the bank works (claim steps and times, blocks, replacements, holds, reversals, fees, contact channels) is answered only from the bank's own documents of the customer's country, each sentence citing the excerpt it uses, and the citation opens the document's PDF at that page; with no matching excerpt, Clara says she does not have it, never answers from the model's own knowledge.
- A cited sentence says only what its excerpt says; advice about what the customer can do, and what the bank does next, is said only with a citation. The customer's own words ("cancelar") reach the bank's documents through a glossary of the bank's terms ("bloquear").
- A policy figure (a time, a fee, a phone) is said only as a reference to the excerpt's figures, rendered from the same facts the rules read, so a document and a rule cannot disagree; a timeframe is the bank's process, never a promise.
- Legal deadlines are the bank's reading of each norm, flagged unverified (`policy_facts.toml`, `verified = false`), and must not reach a customer as-is until checked against the primary legal text.
- A block, a case or a handoff to a person happens only on the customer's tap or a bare typed yes to that very question; a yes with anything after it, or a yes read by the model, shows the question again. Clara says it happened only after reading the result back.
- "¿Reconoces este cargo?" and "¿Fuiste tú?" also close on a short yes or no at the start of a typed message, and the rest of it is kept as the customer's note. "¿Reconoces este cargo?" also closes on a clear written answer read by the model: a yes is remembered with the message as the note, a no leads to the block confirmation; nothing is written to the account without a tap. With that question open Clara never answers by repeating the charge.
- The customer only ever sees their own data, never another customer's, never an invented deadline, never a promise of a specific agent (`docs/product/01-flows.md` flow 1).
- A stale pending charge (older than 7 days) is never explained to the customer as "temporary" (`hackathon/docs/domain/triage.md`).
- Clara never answers her own messages, and says nothing in a room delegated to a human.
- Every value Clara says (an amount, a date, a count, a merchant, a card's last digits, a case code, a policy figure) is one she read this turn and the bank's code rendered; a reply with any other value is repaired once, then replaced by a template.
- Clara never says "fraud", that a charge is safe, or that money will come back, nor anything about what she can or cannot promise. Only the fixed receipt of a fraud or service case says that a person at the bank will contact the customer; nothing she composes promises a person, a call or a takeover.
- Clara's own words only look things up and show them; what the bank allows (block, claim, a person) is offered only by the bank's buttons, with fixed consent and receipts identical for every customer.
- What the bank saw on a charge is said only as the bank's reasons, never as a risk level; Clara never says where things are on the screen.
- Clara never says anything about rows she was not shown, and never names a card brand: the bank's data has none, so cards are named by type and last digits. A card's expiry date is a secret like its CVV: no screen of Clara's, no answer and no card face shows it.
- Clara never guesses the customer's gender and never offers anything in her own words (a transfer, a person, a lookup "si quieres"); the bank's buttons offer what the bank allows. A question with buttons always brings its own screen; asking for a person shows what that person will receive, about the customer in the third person.
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
