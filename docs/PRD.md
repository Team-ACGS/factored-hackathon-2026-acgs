---
updated: 2026-09-27
source: setup
---

# Product Requirements Document

## Product

Clara is the customer service system of LATAM Bank for one situation: a customer sees a card charge they do not recognize.
Today that situation has one path (call, wait, explain, leave with an open claim), although it hides four different cases: a hold that releases on its own, a charge already reversed, the customer's own purchase they fail to identify, and a fraud that needs the card blocked now.
Clara tells them apart at first contact from verified facts in the customer's own records, and decides between explaining, claiming and protecting.
It executes only what the policy allows, with confirmation and verification, and hands a prepared case to a human when required.
It speaks Spanish (Mexico, Colombia, Argentina) and Brazilian Portuguese, and its decision must not change with the dialect.
Built for the Factored AI Data Hackathon 2026 on the LATAM Bank dataset (`docs/brief/`); the problem and its evidence are in `docs/problem-statement.md` of the docs root.

## Users

- Customer: resolve an unrecognized charge in one conversation, get the card protected fast when it is fraud, and never repeat the story.
- Agent (bank contact center): take over a conversation Clara hands off, with the facts, actions taken and open questions already prepared.
- Officer (bank back office): work a ranked queue of complaints within the legal deadline of each country.
- Analyst (improvement team): review how Clara performs and improve it; later, in a fourth web not built yet.

## Capabilities

### Talk to Clara about a charge

The customer signs in, sees their products and movements, and tells Clara about a charge.
Clara explains it when the records settle it, opens a claim when they do not, and blocks the card and escalates when the customer says it was not them.
Details: [modules/assistant/prd.md](modules/assistant/prd.md)

### Chat in real time

Customer, Clara and a human agent share one conversation that updates live, and the customer rates it at the end.
Details: [modules/messaging/prd.md](modules/messaging/prd.md)

### Hand off and follow a case

Every claim is a case with a lifecycle; when Clara hands off, the agent receives a structured package instead of a transcript and continues in the same chat.
Details: [modules/cases/prd.md](modules/cases/prd.md)

### Work the complaints queue

Officers see complaints categorized and ranked by urgency and legal deadline, and get cases assigned by area, shift and language.
Details: [modules/inbox/prd.md](modules/inbox/prd.md)

### Sign in with the right access

Customers register themselves; staff accounts are created by the bank; each person reaches only their own web and, for customers, only their own data.
Details: [modules/identity/prd.md](modules/identity/prd.md)

### Understand what the customer means

Own classifiers route each message to an intent and flag injection attempts, trained on labeled utterances with declared provenance.
Details: [modules/models/prd.md](modules/models/prd.md)

### Prove it works

A held-out set written by people outside the team, two baselines and the hypotheses' metrics show what Clara achieves and where it fails.
Details: [modules/evaluation/prd.md](modules/evaluation/prd.md)

### Reproduce every number

Every figure in a doc or a slide is regenerated from the raw dataset with one command.
Details: [modules/data/prd.md](modules/data/prd.md)

## Cross-cutting rules

- The rules decide; the language model only understands the message and writes the reply.
- Every figure Clara states exists in one of the customer's rows.
- Clara never moves money, never unblocks a card and never decides a refund; those stay human.
- Clara never reads another customer's data, enforced by AWS, not by the prompt.
- A write is announced only after it is read back.
- Legal deadlines per country come from a versioned table, pending verification against the current law (`docs/domain/legal-deadlines.md`).
- English, Spanish and Brazilian Portuguese everywhere a customer reads text, chosen by the browser locale; no customer-facing string is hardcoded.

## Not in the product

- Duplicate charges, credit products and accounts, and any channel without verified identity (problem statement, scope, in the docs root).
- Refund decisions.
- Voice and WhatsApp channels.
- Any model trained on the dataset's text columns, which carry no information (EDA findings, in the docs root).

## Open questions

- Share of cases Clara can resolve without a claim; the dataset suggests 5 to 8%, no target fixed. [inferido]
- Portuguese conversations are entirely team-generated; there are no Portuguese-speaking fraud agents at night to hand off to. [inferido]
