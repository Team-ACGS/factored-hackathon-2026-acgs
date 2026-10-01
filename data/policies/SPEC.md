# Policy corpus spec

The contract for LATAM Bank's policy documents: what the writers produce, what `uv run build-policies` accepts, and what `search_policies` returns from.
LATAM Bank is fictional, and so is every value in its documents.
20 base documents, each written once in Spanish (`es`), Brazilian Portuguese (`pt-BR`) and US English (`en-US`): 60 sources.
The build renders each source once per country of its language, so the corpus is 120 editions of 2 to 3 pages each.

## Where documents live

- Sources live at `<doc_id>/<language>.md`: in the docs root's `docs/policies/`, built with `--sources`, or in the policies bucket in the same layout; only the sample under `data/policies/sample/sources/` is committed here.
- `doc_id` is the topic with hyphens (`dispute-lifecycle`), and `language` is `es`, `pt-BR` or `en-US`.
- Each source expands into one edition per country of its language: `es` into MX, CO, AR and PE, `pt-BR` into BR, `en-US` into US.
- An edition's `doc_id` is `<country lowercase>-<doc_id>` (`mx-dispute-lifecycle`), its language the country's (`es-MX`), and its figures the country's values.
- Every figure comes from `lambdas/core/src/core/policy_facts.toml`, the same file the rules read, so a document can never contradict a rule.
- An edition is the source's `version` plus its country's facts `version`: a new edition gets its own PDF at `<country>/<edition doc_id>-v<version>-f<facts_version>.pdf`, and older PDFs stay reachable.

## Frontmatter

Every source starts with this YAML frontmatter and nothing else above it:

```yaml
---
doc_id: dispute-lifecycle
title: Ciclo de una aclaración, de la apertura al cierre
language: es
topic: dispute_lifecycle
doc_type: procedure
version: 1
effective_date: 2026-10-01
---
```

| Field | Rule |
|---|---|
| `doc_id` | The topic with hyphens, matching the folder |
| `title` | In the source's language, at most 90 characters, no digit, no forbidden word, no literal name |
| `language` | `es`, `pt-BR` or `en-US`, matching the file name |
| `topic` | A topic slug from the taxonomy |
| `doc_type` | The taxonomy's `doc_type` for that topic |
| `version` | Integer from 1, raised on every change of the text, in the three files together |
| `effective_date` | ISO date |

There is no `country`: the build sets it when it expands the source.

## Taxonomy

Four groups, 20 topics, one base document per topic, written once in each of the three languages.
The folder of a document is its topic with hyphens: `dispute_lifecycle` lives in `dispute-lifecycle/`.
The group is not written in the frontmatter: the build derives it from the topic, and `search_policies` filters by it.

### `disputes`: unrecognized charges and disputes

| Topic | doc_type | What it covers |
|---|---|---|
| `unrecognized_charge_rights` | policy | Unrecognized charge: the customer's rights and the bank's commitments |
| `dispute_lifecycle` | procedure | A dispute from opening to closing, through the stages, with deadlines per step |
| `unrecognized_charge_guide` | guide | What to do when you do not recognize a charge |
| `dispute_deadlines` | policy | Response and resolution deadlines for disputes, the bank's and the norm's |
| `special_purchase_disputes` | guide | Disputes on online, foreign and recurring purchases |
| `unrecognized_charges_faq` | faq | Questions and answers on unrecognized charges |
| `disputes_glossary` | glossary | The terms of disputes |

### `card_security`: card security and blocking

| Topic | doc_type | What it covers |
|---|---|---|
| `lost_or_stolen_card` | guide | Lost or stolen card: the immediate steps |
| `card_blocking` | policy | Card blocking: the customer confirms every block, what a block means, and why unblocking needs a person |
| `card_replacement` | policy | Card replacement after a block: timelines and fees |
| `blocked_card_effects` | guide | What stops working when a card is blocked: subscriptions, installments, linked services |
| `transaction_alerts` | guide | Transaction alerts and the "was it you" confirmation |
| `unauthorized_use_liability` | policy | The customer's liability for unauthorized use and the zero liability conditions |

### `transactions`: transactions and statements

| Topic | doc_type | What it covers |
|---|---|---|
| `transaction_statuses` | guide | Transaction statuses: pending, approved, declined, reversed |
| `pending_charges` | guide | Pending charges and preauthorizations: hotels, fuel, car rental |
| `reversals_and_duplicates` | policy | Reversals, merchant returns and duplicate charges: timelines by channel |
| `recurring_payments` | guide | Recurring payments and subscriptions management |

### `service`: customer service and the assistant

| Topic | doc_type | What it covers |
|---|---|---|
| `assistant_handoff` | procedure | Handoff from the virtual assistant to a person, escalation and the ombudsman |
| `assistant_scope` | policy | What the assistant can and cannot do, and the actions that need your confirmation |
| `deadlines_calendar` | policy | Every customer-facing deadline in one place, the bank's and the norm's |

## Sections

Every document is a sequence of `##` sections, with no text before the first one and no `#` heading (the title comes from the frontmatter).
Inside a section, use paragraphs, `-` lists, ordered lists, `###` subheadings and `**bold**`; never tables, links, images, HTML or code.
The build numbers sections in order (`s1`, `s2`, ...) and uses that number for the PDF anchor and the chunk id, so headings carry no number.
Each section becomes one chunk, so a section is self-contained: it names what it talks about instead of leaning on the section before it.

### policy, procedure, guide: fixed headings

The headings are exactly these, in this order, in the source's language.

| doc_type | es | pt-BR | en |
|---|---|---|---|
| policy | Propósito | Objetivo | Purpose |
| | Alcance | Abrangência | Scope |
| | Definiciones | Definições | Definitions |
| | Principios | Princípios | Principles |
| | Reglas | Regras | Rules |
| | Derechos del cliente | Direitos do cliente | Customer rights |
| | Obligaciones del banco | Obrigações do banco | Bank obligations |
| | Excepciones | Exceções | Exceptions |
| | Plazos | Prazos | Deadlines |
| | Marco regulatorio | Base regulatória | Regulatory basis |
| | Control de versiones | Controle de versões | Versioning (written by the build) |
| procedure | Propósito | Objetivo | Purpose |
| | Participantes | Participantes | Actors |
| | Condiciones previas | Pré-requisitos | Preconditions |
| | Pasos | Etapas | Steps |
| | Puntos de decisión | Pontos de decisão | Decision points |
| | Plazos por paso | Prazos por etapa | Deadlines per step |
| | Evidencia | Evidências | Evidence |
| | Resultados | Resultados | Outcomes |
| | Escalamiento | Escalonamento | Escalation |
| | Registros | Registros | Records |
| guide | Qué es | O que é | What this is |
| | Cuándo aplica | Quando se aplica | When it applies |
| | Qué hacer | O que fazer | What to do |
| | Qué sigue | O que acontece depois | What happens next |
| | Tiempos | Prazos | Timelines |
| | Qué se necesita | O que é necessário | What you will need |
| | Situaciones frecuentes | Situações comuns | Common situations |
| | Dónde pedir ayuda | Onde pedir ajuda | Where to get help |

A policy's source ends at Regulatory basis.
The build writes Versioning at render time from the frontmatter and the facts file (the document's version, its effective date, and the country's facts version), in the PDF only: it is not chunked or embedded, since every chunk already carries its version and effective date.

### Length

The bank template fits about 350 words per page, so a document of 2 to 3 pages, the cover not counted, has 600 to 1,050 words.
The validator enforces 60 to 250 words per section and 600 to 1,050 words per document, the same in the three languages.
Write the Spanish source at about 700 to 950 words, so the Portuguese and English versions fit too.

| doc_type | Sections | Target words per section | Target words per document |
|---|---|---|---|
| policy | 10 | 85 | 850 |
| procedure | 10 | 85 | 850 |
| guide | 8 | 105 | 850 |
| faq | 4 to 6 subtopics, 12 to 16 questions | 140 to 200 | 850 |
| glossary | 4 to 6 term groups | 140 to 200 | 850 |

`uv run build-policies render` prints each edition's page count.

### faq

- Four to six `##` sections, one per subtopic, with a heading the writer chooses (no digit, no forbidden word, no literal name).
- Each question is a `###` heading ending in a question mark (`¿...?` in Spanish), followed by its answer in one to three paragraphs.
- Twelve to sixteen questions in the document.

### glossary

- Four to six `##` sections, one per group of related terms, with a heading the writer chooses.
- As many terms as fit the document's length.
- Each term is a `###` heading followed by three paragraphs that start with these labels, in this order:

| es | pt-BR | en |
|---|---|---|
| `**Definición:**` | `**Definição:**` | `**Definition:**` |
| `**Ejemplo:**` | `**Exemplo:**` | `**Example:**` |
| `**Términos relacionados:**` | `**Termos relacionados:**` | `**Related terms:**` |

## Parity across languages

The three files of a document say the same thing.
The build compares `pt-BR` and `en-US` with `es` and fails the whole document, every edition of it, when:

- a language file is missing;
- `doc_id`, `topic`, `doc_type`, `version` or `effective_date` differ;
- the number of sections differs, compared by position;
- a section has a different set of placeholders than the same section in `es`.

Translate section by section and keep every placeholder in its section.

## Figures are placeholders

Every figure is a placeholder `{{policy.<group>.<key>}}`: a time, an amount, a fee, a percentage, a stage name, a phone, an email, an app path, a schedule, a URL or a name.
The country is never in the placeholder: the build renders it with each edition's country values.
Placeholders go in the text, never in headings, and are written exactly as below, without spaces inside the braces.

```
Cuando su caso queda {{policy.claims.stage_assigned}}, la revisión toma hasta {{policy.claims.review_time}}.
```

Rendered for MX: "Cuando su caso queda asignado, la revisión toma hasta 10 días hábiles."
A count renders with its noun ("10 días hábiles"), so the text never repeats the noun after it.
A stage renders as the label the app shows, which agrees with "caso" (masculine in Spanish and Portuguese), so write it next to "su caso", "seu caso" or "your case".

### Names

A `name` placeholder renders as plain text, without an article, and its gender changes from country to country (el Banco Central, la Comisión).
Introduce it after a generic noun, in parentheses or by apposition with commas, never after a colon in the middle of a sentence:

```
El banco sigue las reglas del regulador bancario ({{policy.authority.regulator}}).
Puede escribir a la defensoría del banco, {{policy.service.ombudsman_name}}, en {{policy.service.ombudsman}}.
```

### Keys

Every country has every key; the values are in `policy_facts.toml`.

| Placeholder | Type | Meaning |
|---|---|---|
| `claims.report_window` | count, days | How long after the statement the customer can report an unrecognized charge, under the bank's policy |
| `claims.assign_time` | count, business days | From a claim opened to a claim assigned to an analyst |
| `claims.review_time` | count, business days | Time a claim stays in review |
| `claims.resolution_time` | count, business days | The bank's commitment from opened to resolved |
| `claims.evidence_window` | count, business days | Time the customer has to send evidence the bank asks for |
| `claims.provisional_credit_time` | count, business days | When the bank may apply a provisional credit while a claim is in review, where the policy allows it |
| `claims.reopen_window` | count, days | How long after closing the customer can ask to reopen a claim |
| `claims.stage_opened` | stage | The stage name "opened" |
| `claims.stage_assigned` | stage | The stage name "assigned" |
| `claims.stage_in_review` | stage | The stage name "in review" |
| `claims.stage_resolved` | stage | The stage name "resolved" |
| `claims.stage_closed` | stage | The stage name "closed" |
| `legal.claim_response` | count, legal | The norm's maximum time for the bank to answer a claim, as the bank reads it |
| `legal.report_window` | count, legal | The norm's time for the customer to question a charge, as the bank reads it |
| `cards.replacement_time` | count, business days | Delivery of a replacement card after a permanent block |
| `cards.express_replacement_time` | count, business days | Express delivery of a replacement card, shorter than `cards.replacement_time` |
| `fees.replacement` | money | Fee for a replacement the customer asks for after loss or damage; a replacement after unauthorized use is free |
| `fees.express_delivery` | money | Fee for express delivery of a replacement card |
| `fees.foreign_transaction` | percent | Fee on purchases in another currency |
| `holds.fresh_hold` | count, days | A pending charge younger than this is a recent hold that can still change |
| `holds.preauth_general` | count, days | When an unused preauthorization is released, in general |
| `holds.preauth_fuel` | count, days | When a fuel station preauthorization is released |
| `holds.preauth_hotel` | count, days | When a hotel preauthorization is released after checkout |
| `holds.preauth_car_rental` | count, days | When a car rental preauthorization is released after return |
| `transactions.reversal_pos` | count, business days | When a merchant's reversal of an in-store purchase shows on the card |
| `transactions.reversal_online` | count, business days | When a merchant's reversal of an online purchase shows on the card |
| `transactions.duplicate_review` | count, business days | Review of a reported duplicate charge |
| `transactions.recurring_cancel_notice` | count, business days | Notice before the next charge for the bank to stop a recurring charge |
| `security.never_asks` | list | What the bank never asks for: full card number, security code, PIN, password, one-time code |
| `security.zero_liability_window` | count, days | Report within this time from noticing an unauthorized use to keep zero liability |
| `channels.phone` | phone | The national service line |
| `channels.phone_abroad` | phone | The line to call from abroad |
| `channels.phone_schedule` | schedule | When the phone line answers |
| `channels.email` | email | The service email |
| `channels.web_help` | URL | The help center |
| `channels.app_help` | app path | The app's help and claims screen |
| `channels.app_claims` | app path | Where to follow claims in the app |
| `channels.app_clara` | app path | Where to talk to Clara, the assistant, in the app; blocking a card and opening a claim happen there |
| `service.handoff_wait` | count, minutes | Usual wait to talk to a person after the assistant hands off, in service hours |
| `service.handoff_hours` | schedule | When people answer the chat |
| `service.ombudsman` | email | The email of the bank's ombudsman office |
| `service.ombudsman_name` | name | The name of the bank's ombudsman office (fictional, the bank's own) |
| `service.ombudsman_response` | count, business days | Time the ombudsman office takes to answer |
| `authority.regulator` | name | The banking regulator |
| `authority.consumer_agency` | name | The public agency that protects financial consumers |
| `authority.norm_name` | name | The norm on card claims, named in plain words, never by an article or a number |

### Legal deadlines

`legal.*` values are the bank's reading of each country's norm, unverified and flagged `verified = false`.
A section that uses a `legal.*` placeholder also contains the disclaimer of its language, word for word:

| es | pt-BR | en |
|---|---|---|
| según la lectura que hace el banco de la norma aplicable | conforme a leitura que o banco faz da norma aplicável | as the bank reads the applicable rule |

A document says what the norm asks in plain words, but never cites an article, a norm number or a court.

## No literal names

One text serves several countries, so it never names one.
Every name that varies by country is a `name` placeholder, and the text uses a generic noun otherwise: the banking regulator, the consumer protection agency, the bank's ombudsman office, the norm.
The build rejects, in any language and in any case:

- the six countries and their demonyms in Spanish, Portuguese and English (México, Brasil, Brazil, Estados Unidos, United States, mexicano, brasileiro, Brazilian, American, estadounidense, ...);
- the regulators, agencies, ombudsman offices and norms, spelled out (Comisión Nacional Bancaria y de Valores, Banco Central do Brasil, Consumer Financial Protection Bureau, Código de Defesa do Consumidor, Regulation Z, ...), and every `name` value of `policy_facts.toml`;
- their acronyms, matched with their case (CNBV, CONDUSEF, SFC, SIC, BCRA, SBS, INDECOPI, BACEN, CFPB, OCC, US, USA, U.S., EUA, EE. UU.), so the pronoun "us" passes.

Generic nouns pass (banco central, defensoría, ouvidoria, ombudsman, regulator), and so do "LATAM Bank" and "Clara".
The full lists are in `data/src/bankdata/policies/spec.py`.

## Tone

- The bank's voice: plain, calm, precise, in second person.
- The register: `usted` in Spanish, so one text reads naturally in the four Spanish-speaking countries; `você` in Portuguese; `you` in English.
  Clara's own replies keep each country's register; the documents do not.
- The app's words for a claim, so a document reads like the screen beside it: aclaración in Spanish, contestação in Portuguese, claim in English.
- The bank never blocks a card on its own: every block is confirmed by the customer, with a tap in the chat with Clara or on the phone line, and unblocking needs a person.
  Documents never describe a preventive, automatic or temporary block.
- The app has no screens for alerts settings or recurring charges: documents send the customer to Clara (`channels.app_clara`) or the phone line for those, never to a screen.
- No promise about money: the bank reviews, decides and informs; a provisional credit or a reversal is described as what may happen under the process, never as a certainty.
- No specific customer, name, case, merchant or date.
- Never the words "fraude" or "fraud" in any form (fraudulento, fraudulent): write "cargo no reconocido", "uso no autorizado", "cobrança não reconhecida", "uso não autorizado", "unrecognized charge", "unauthorized use".
- Out of scope: loans, accounts, investments, insurance, and any product other than cards.

## What the build rejects

The build validates every source once, and its placeholders against every country of its language, before rendering; it fails the source, naming the file and the line, on:

- frontmatter: a missing or extra field, a value outside its rule, or a mismatch with the path;
- structure: text before the first section, a `#` heading, a heading that is not the next one expected, a missing section, an faq or glossary outside its counts, a glossary term without its three labels;
- length: a section outside 60 to 250 words, a document outside 600 to 1,050 words, or a rendered section too long to embed with its title and heading (about 512 tokens);
- a raw figure outside a placeholder: any digit, a currency code or symbol, a phone, an email, a URL, a month or weekday name;
- a number word outside a placeholder: two to twenty and second to twentieth in Spanish, Portuguese and English (`uno`, `una`, `primero`, `primera`, `um`, `uma`, `one` and `first` are articles or plain words and pass);
- a placeholder that is malformed, or whose key is missing for any country of the source's language (the problem names the country);
- a `legal.*` placeholder in a section without its disclaimer;
- a forbidden word, in the title or the text;
- a literal name, in the title or the text;
- the informal register: `tú`, `tu`, `tus`, `ti`, `te`, `contigo` or `vos` in Spanish, `tu`, `teu`, `teus`, `tua`, `tuas`, `ti` or `contigo` in Portuguese;
- parity across the three languages.

Exempt, and only these:

- the ordered list markers at the start of a line (`1.`);
- `terceros`, `terceiros` and `third parties`, which read as ordinals but mean someone else;
- in English, `may` and `march`, which are also a verb;
- in Portuguese, `segundo` and `segunda` (with their plurals) right before an article, a possessive or a pronoun (`o`, `a`, `os`, `as`, `seu`, `sua`, `seus`, `suas`, `ele`, `ela`, `eles`, `elas`, `este`, `esta`, `esse`, `essa`), where they mean "according to".

Every other month name, weekday name and number word fails, wherever it appears.
In Brazilian Portuguese write "novo cartão" or "reemissão", never "segunda via", which reads as an ordinal.

## Working without AWS

Both commands read a local folder in the source layout, never load the AWS configuration, and exit 1 on any problem.

- `uv run build-policies validate --sources <folder>` prints every problem with file and line.
- `uv run build-policies render --sources <folder> --out <dir> [--country XX]` writes each edition to `<dir>/<country>/<edition>.pdf` with the bank template and prints its page count, the cover not counted.
  A draft that fails only length, word or parity rules still renders, so a writer can check its pages before the other languages exist.

`uv run build-policies publish` builds and publishes; see `RUNBOOK.md`.

## Generation prompt

Each source is generated section by section with Claude Sonnet 5, so each call stays within a section's length and sees the sections before it: first the Spanish source, then the Portuguese and English versions from it, section by section.
The script that drives it writes the frontmatter itself, calls the model once per section with this prompt, and joins the sections.
Slots in single braces (`{language}`) are filled by the script; placeholders keep their double braces.
`{target_words}` comes from the length table, and the generated sections exclude Versioning.
`{placeholder_table}` lists every key of the table above, one per line, as `{{policy.<group>.<key>}}: <meaning>`.
`{source_section}` is the same section of the Spanish source when writing the Portuguese or English version, and empty otherwise.

```text
You are writing one section of a customer document of LATAM Bank, a fictional bank that serves
several countries. One text serves every country of its language, so it never names a country.

Language: {language}. Register: {register}.
The app's word for a claim: {claim_word}.
Document: "{title}", a {doc_type} on the topic {topic}: {topic_scope}.
Sections of this document, in order: {headings}.
Write section {n}: "{heading}". Sections already written, one line each: {previous_summaries}.
{source_section}

Length: about {target_words} words, never under 60 or over 250. The section is read on its own,
so name what it talks about instead of referring to other sections.
Format: start with "## {heading}" and write only this section. Use paragraphs, "-" lists, ordered lists,
"###" subheadings and **bold**. No tables, links, images, HTML, or other "#" or "##" headings.
{doc_type_rules}

Figures: never write a number in digits or in words, an amount, a currency, a percentage, a time,
a phone, an email, a URL, an app path, a schedule, a month or a weekday. Write each figure as one of
these placeholders, exactly as shown, where its value belongs in the sentence:
{placeholder_table}
A count placeholder already includes its noun ("{{policy.claims.review_time}}" reads "10 business days").
If a sentence needs a figure that is not in the list, rewrite the sentence without it.
When you use a {{policy.legal.*}} placeholder, include in the same section the words:
"{legal_disclaimer}".
When translating, keep every placeholder of the source section, and no other.

Names: never write a country, a nationality, a regulator, an agency, an ombudsman office or a norm.
Use the generic noun (the banking regulator, the consumer protection agency, the bank's ombudsman
office, the norm), and where the name matters, add its placeholder after the noun, in parentheses
or between commas: "the banking regulator ({{policy.authority.regulator}})". LATAM Bank and Clara
may be named.

Never write: fraude, fraud, or any word built on them; write {unauthorized_words} instead.
Never write "segunda via" (pt-BR); write "novo cartão" or "reemissão".

Tone: plain, calm and precise, the bank speaking to its customer. Never promise money: say what the
process does and what may happen. The bank never blocks a card on its own: the customer confirms every
block, with Clara in the app or on the phone line, and unblocking needs a person. The app has no alert
or recurring charge settings: send the customer to Clara or the phone line instead. No specific
customer, case, merchant or date. No article or norm numbers, no courts. Nothing about loans,
accounts, investments or insurance.
```

Where `{doc_type_rules}` is, for faq: "This section is one subtopic: {k} questions as ### headings ending in a question mark, each answered in one to three paragraphs"; for glossary: "This section is one group of terms: each term is a ### heading followed by the paragraphs {definition_label}, {example_label} and {related_label}"; and empty for the other types.

The frontmatter the script writes, the same in the three files but `title` and `language`:

```yaml
---
doc_id: {doc_id}
title: {title}
language: {language}
topic: {topic}
doc_type: {doc_type}
version: {version}
effective_date: {effective_date}
---
```
