---
updated: 2026-10-03
source: 0019_open_mode_graph
---

# assistant: technical

Status: the open-mode turn is built (task 0019): router and safety floor, the `open_mode` graph, facts by reference, the reply with parts.
The story path (asks, rules, writes, handoff) is the B4 design in `docs/tasks/_drafts/chat_architecture.md` at the docs root, which supersedes `turn_flow.md`.

## Structure

| Path | What |
|---|---|
| `lambdas/chatbot/` | Stream consumer: skips non-customer messages and delegated rooms; replays a stored reply instead of a second turn; takes the room's turn mark; runs `core.turn` over the 6 messages before the current one; writes the reply with its parts; emits `turn.completed` with timings, tool names and outcomes, tokens and the check result, never text. |
| `lambdas/crud/` | The customer's own data behind `/crud/*`: profile and one-time setup, cards, transactions; the generator (`catalog.py`, `generator.py`) builds a demo account deterministically from the setup claim. |
| `lambdas/core/` | Shared package bundled into every lambda zip: `core.turn` (profile, route, the cards read into the ledger, the context by manifest), `core.router` (the safety floor phrase list on folded text with word boundaries), `core.graphs` (`open_mode`, the prompt in `system.md`, the Bedrock client bound to the turn's deadline; LangGraph and `langchain-aws` are the `graph` extra, only in the `chatbot` zip), `core.answers` (safety template and `say_key` answers rendered by code), `core.replies` (render, citation objects, referenced facts); the read models every reader of customer data must use (`core.accounts`, `core.customers`, `core.cases`, `core.memory`, each an attribute allow-list); `core.tools`, Clara's nine read tools as plain functions with a Pydantic input each and a registry (`TOOLS`, `call`), callable without LangGraph or Bedrock; `core.ingestion`, the one door for a new transaction (a versioned contract and one write that stores the row and moves the card's balance); `core.facts`, the turn's ledger of typed facts (`fN` from data tools, `pN` from policy excerpts), their rendering in es, pt-BR and en, the deterministic check (including the citation rule) and the template fallback, with no AWS import; `core.tools.policies` (`search_policies`) over `core.retrieval` (the `Retriever` interface, `VectorRetriever`, the vector metadata layout) and `core.vectors` (Bedrock embedder, S3 Vectors index, turn and build timeouts); `core.policies` and `policy_facts.toml`, the bank's figures per country, read by the documents' build and later by the rules. Spec of each tool: `docs/tasks/0013_policy_search/design/tools.md` in the docs root. |
| `lambdas/testing/` | `clara-testing`, a dev-only workspace member never bundled: Bedrock, S3 Vectors and Converse test doubles; `FakeConverse` validates every request against the botocore Converse shape and replays recorded responses, `Recorder` records real ones. |
| `apps/customer/` | SPA at `factoredai.sdfles.com` (React, Vite, TanStack Router, TanStack Query, Amplify v6): auth, setup, the bank shell in `src/bank` (home, card movements, help and claims, sheets; server data only through `src/bank/queries.ts`), Clara in `src/clara` (button, launcher, entry points, the session store in `sessionStorage` with only the seeded claim and the pending topic) and the chat in `src/clara/chat` over `src/chat/live.ts` (`/messages` plus AppSync): `say` parts with source chips, and the thinking state. Text from typed catalogs in `src/i18n/`. |
`apps/ui/` | Shared Tailwind theme, self-hosted fonts (`@fontsource`: Hanken Grotesk, Newsreader, IBM Plex Mono), shadcn/ui components, and Clara's entity: pure geometry in `src/lib/entity.ts` (palette, nine states, sampled outlines, faces, interpolation) and `ClaraEntity` / `ClaraGlyph` in `src/components/clara-entity.tsx`, morphed by one JS interpolation path in every browser. |

## The turn: budgets, latency and packaging

- Budgets of `open_mode`: 4 supervisor steps (the last one must call `reply`), 8 tool calls, 12 s per turn with every Bedrock call bounded by the time left, and 40,000 cumulative input tokens; a check failure gets one repair, then the template from what the tools read; any exception inside the graph ends in that template too.
- Models: rows of `core/graphs/profiles.toml`, selected by `BEDROCK_MODEL_ID`; prompt `prompts/system.v2.md`.
- Measured locally on 2026-10-03 (four demo turns, es and pt-BR, moto accounts, `system.v2`): Sonnet 4.6, 4.9 s to 9.1 s per turn, $0.014 to $0.023, 7.4k of about 10k input tokens read from the cache, every answer composed on the first try; Haiku 4.5, 3.5 s to 5.1 s, $0.012 to $0.018, nothing cached (prefix under its 4,096 minimum), one repair (a month name), weaker wording ("dentro 10 días hábiles").
- `chatbot` bundle: 187 MB unzipped, 59 MB zipped (deployed through S3), built for Amazon Linux 2023 wheels with precompiled bytecode; the graph's imports add 0.6 s to 0.7 s of init locally; 2048 MB.
- Cold and warm latency of the real turn on `prd`: measured after the merge (task notes).

## Endpoints owned

A customer message enters through messaging's `POST /messages`.
`crud` serves the customer's own data, customer tokens only (staff get 403), every access under `role-customer` tagged with the token's `sub`; there is no generated API spec yet.

- `GET /crud/profile`: country, language, whether setup is done, and the given name when the customer has one.
- `POST /crud/profile/setup`: create the demo account once (201 with the planted cases, 409 afterwards).
- `GET /crud/cards`: the customer's cards.
- `GET /crud/cards/{product_id}`: one card and a page of its transactions, newest first, with an opaque `next_cursor` and `server_time`.
- `GET /crud/cards/{product_id}/transactions/{transaction_id}`: one transaction.
- `POST /crud/cards/{product_id}/transactions`: add a normal or suspicious transaction (`type`) with a client-minted UUIDv7 through `core.ingestion`, idempotent; a row that breaks the contract or a charge the card cannot take is a 400 naming the fields.

Jobs and listeners: `chatbot` consumes the `messages` stream, only inserts with `sender_type = customer`, batch 1, 3 retries, bisect on error, DLQ `clara-prd-chatbot-dlq`; it skips rooms delegated to a human.

## Depends on

- identity: customer login is Cognito email and password; the sign-up email OTP is only a one-time verification code, never a chat step-up. Identity owns the IAM roles that decide who may do what on the DynamoDB tables; this module only assumes `role-customer`.
- DynamoDB tables `customers`, `products`, `transactions` (PK `customer_id`), read and written through `role-customer` via STS AssumeRole with a `customer_id` session tag; `crud` setup seeds them per demo customer, a seed from the dataset is not built.
- DynamoDB table `complaints` (PK `customer_id`, GSI by area and priority): this table is the case record, historical and new; this module reads it through Q5 and writes to it only through the `A2 create complaint` and `A3 withdraw complaint` tools, which call the cases module's write code inside the shared `lambdas/core` package (the same code path `lambdas/crud` uses), never another lambda.
- models: the injection detector and intent router (multilingual e5 + logistic regression), loaded as versioned S3 artifacts; serving is not in `infra/` yet.
- Bedrock Claude Sonnet 4.6 (`us.anthropic.claude-sonnet-4-6`, the default profile row) or another row of `profiles.toml`, Converse through `langchain-aws`, as the graph's supervisor, and Cohere Embed v4 (`cohere.embed-v4:0`, 1024 dimensions) only to embed `search_policies` queries; no Titan, Grok or Haiku unless a measured need is shown.
- messaging: the reply is written as an ordinary message (`sender_type = assistant`) through the messaging code in `lambdas/core`, assuming `role-customer` with the stream record's `customer_id`; `chat-notifier` pushes it. On handoff the room is marked delegated and Clara stays silent.
- Observability: every lambda uses AWS Lambda Powertools for Python (Logger, Metrics, Tracer); the block-card and create-complaint writes are idempotent through conditional writes on deterministic ids; CloudWatch Logs (structured JSON) and EMF metrics in namespaces `Clara/Backend` and `Clara/Assistant`; X-Ray active tracing, and `chatbot` annotates each record with the message's `origin_trace_id` (messaging `trd.md`, Latency and tracing).
- EventBridge bus `clara-prd`: `lambdas/chatbot` calls PutEvents once at the end of every turn with ids and a `trace_id` only, never message text; events flow through Firehose to S3. Analysis of these events and the offline LLM judge are deferred.
- `search_policies`: reads no customer data, so it runs under `chatbot`'s own role, which may only call `s3vectors:QueryVectors` and `GetVectors` on the policy index and `bedrock:InvokeModel` on `cohere.embed-v4:0`; it returns excerpts distinct in content, from a pool of 30; the index is built by the data module's `build-policies`.
- legal deadlines: the `legal.*` keys of `policy_facts.toml` are the bank's reading of each norm, flagged `verified = false`; any due date the composer states depends on them being verified before it reaches a real reply.

## Depended on by

- cases: consumes the structured handoff package (verified facts, actions with read-back, evidence, open questions, data warnings) produced on `HANDOFF`, `CLAIM` and `PROTECT`, and owns the `complaints` table this module reads and writes through tools.
- evaluation: the offline judge and the held-out harness run against this module's traces and outputs.

## Configuration

- `chatbot`: `EVENT_BUS_NAME` (`clara-prd`) and `EVENT_SOURCE` (`clara.chatbot`) for `turn.completed`, `ROLE_CUSTOMER_ARN`, the table names, `BEDROCK_MODEL_ID` (the inference profile id; it must have a row in `profiles.toml`), and for `search_policies` `POLICY_INDEX_ARN`, `POLICY_EMBEDDING_MODEL_ID`, `POLICY_DOCS_DOMAIN` and `POLICY_MIN_SIMILARITY`, a JSON map of one cut per document language (`es`, `pt`, `en`), validated by Terraform and by the code (set in `infra/environments/prd/locals.tf`, tuned by `tune-policies`).
- `crud`: `ROLE_CUSTOMER_ARN`, the pool ids and the table names from Terraform's request environment.
- `apps/customer`: the `VITE_` variables of the `customer-prd` Actions environment, baked in at build time.
- Metrics namespace `Clara/Assistant` (and the shared `Clara/Backend`) for EMF metrics.

## Testing

- `lambdas/tests/chatbot/`: reply placement and parts, `turn.completed` without text, delegated rooms, redelivery replayed without a model call, the turn mark (held, expired, cleared on failure), a crashing graph still replies.
- `lambdas/tests/core/test_open_mode.py`: the graph with scripted Converse responses (answers by reference, repair, fallback, each budget passing and exhausted, crash, read-only credentials, nothing volatile before the cache point, the context manifest, citations); `test_open_mode_replay.py` replays the four recorded demo turns of the real model and asserts the same answers and byte-identical requests; `test_open_mode_live.py` calls the real model only with `CLARA_LIVE_BEDROCK=1` (`CLARA_RECORD=1` rewrites the recordings); `test_router.py` and `test_turn.py`: the floor and the safety template per country.
- `lambdas/tests/core/test_policy_search.py`: `search_policies` over an in-memory index (country only, typed figures, URL at the page, filters, `no_match`, `unavailable` on failures and unreadable answers, the turn's time budget, the cut of the country's document language, distinct excerpts, the request of each embedding model); `test_policy_facts.py`: the facts file (same keys in every country, renders, claim times inside the norm, the hold window equal to triage's).
- `lambdas/tests/core/test_tools.py` and `test_facts.py`: every tool on moto fixtures (limits, truncation, `not_found` for refs of another customer, hidden attributes absent, the read-only policy on every AssumeRole), and every render and check rule per locale with a passing and a failing case.
- `lambdas/tests/crud/`: the generated account (counts, status mix, merchant minimums, monthly subscriptions, the seeded claim, planted cases, determinism per country), first, second, resumed and concurrent setup, paging and cursor tampering, cross-customer reads, adds and suffix uniqueness, staff 403, and no hidden attribute in any response; `lambdas/tests/core/` proves the read models drop them, and `test_ingestion.py` proves the contract, the single balance move per `transaction_id` and the refused charges.
- `apps/customer`: `vitest` in node on `*.test.ts`: the locale store and catalogs (no "fraud" in Clara's text, no due date or legal term), the bank API client, money formatting and the bank queries against a real `QueryClient`; the Clara session, overlay, seeded claim and topics; the conversation reducer, `say` parts and citations, and the thinking window. Screens have no tests; Sebastian validates the UI on the PR.
- `apps/ui`: `vitest` on the entity geometry (states, outlines, interpolation).
- Commands: `docs/TRD.md`, Verification targets.
`docs/problem-statement.md` (H1-H5) and `hackathon/docs/kickoff-compliance.md` name a baseline comparison (rules bot, naive LLM) and a held-out evaluation as required, owned operationally by `evaluation/`, exercising this module as a whole.
