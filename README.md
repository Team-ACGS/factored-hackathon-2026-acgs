# Clara

Clara is the customer service system of LATAM Bank for one situation: a customer sees a card charge they do not recognize.
She tells apart a hold that releases on its own, a charge already reversed, the customer's own purchase and a real fraud, from verified facts in the customer's own records.
She explains, opens a claim or blocks the card, always with the customer's confirmation, in Spanish or Brazilian Portuguese.
Built by Team ACGS for the Factored AI Data Hackathon 2026 on the LATAM Bank dataset.

## What is running

| Where | What |
|---|---|
| [factoredai.sdfles.com](https://factoredai.sdfles.com) | The customer web: a bank app with Clara in a chat widget. A new customer gets a demo account (three cards, three months of movements, three planted charges) to try her on. |
| `api.factoredai.sdfles.com` | The REST API behind the web: `/crud/*` for the customer's data and `/messages/*` for the chat. |
| `docs.factoredai.sdfles.com` | The bank's policy documents as PDFs, which Clara cites by page. |

AWS account `975050033628`, region us-east-1, one environment (`prd`) deployed from `main`.

## Repository layout

| Path | What | README |
|---|---|---|
| `apps/` | The customer web (React, Vite, TanStack) and the shared `ui` package | [apps/README.md](apps/README.md) |
| `lambdas/` | Python lambdas: `crud`, `messages`, `chat_notifier`, `chatbot`, `auth`, and the shared `core` package | [lambdas/README.md](lambdas/README.md) |
| `data/` | Dataset pipeline and the policy corpus build | [data/README.md](data/README.md) |
| `infra/` | Terraform for everything above | [infra/README.md](infra/README.md) |
| `docs/` | Product, technical and architecture docs, one folder per module | [docs/](docs/) |

## Run it

Each component is run and tested on its own, one command at a time; the details are in its README.

```bash
cd apps && pnpm install --frozen-lockfile        # Node >= 22.12 and pnpm 10
cd lambdas && uv sync && uv run pytest -q        # Python 3.12 and uv
cd data && uv sync && uv run pytest -q
cd infra/environments/prd && terraform init -backend=false && terraform validate   # Terraform >= 1.10
```

The customer web needs `apps/customer/.env.local`, see [apps/README.md](apps/README.md).

## Flows

Every flow of the product, with its numbered steps and a sequence diagram checked against the code.

### Assistant

- [Answer a customer message](docs/modules/assistant/flows.md#answer-a-customer-message): one reply per customer message, however often the stream record is retried.
- [Run the open mode graph](docs/modules/assistant/flows.md#run-the-open-mode-graph): free text answered by the model over read-only tools, checked by code.
- [Answer a charge question](docs/modules/assistant/flows.md#answer-a-charge-question): Clara asks about a charge and records the customer's answer.
- [Handle not me and lost or stolen](docs/modules/assistant/flows.md#handle-not-me-and-lost-or-stolen): the safety floor catches the phrase before any model call.
- [Block a card and hand off](docs/modules/assistant/flows.md#block-a-card-and-hand-off): consent, block, read-back, case and summary.
- [Open a claim or hand off to a person](docs/modules/assistant/flows.md#open-a-claim-or-hand-off-to-a-person): a case without blocking the card.
- [Compose a sentence with the model](docs/modules/assistant/flows.md#compose-a-sentence-with-the-model): the few sentences the model words from facts, with a template fallback.
- [Show turn progress](docs/modules/assistant/flows.md#show-turn-progress): status events while tools run.
- [Emit turn events](docs/modules/assistant/flows.md#emit-turn-events): one `turn.completed` event per turn to EventBridge, Firehose and S3.
- [Set up the demo account](docs/modules/assistant/flows.md#set-up-the-demo-account): a deterministic account for a new customer.
- [Add a transaction](docs/modules/assistant/flows.md#add-a-transaction): a normal or suspicious charge on demand.
- [Read the account](docs/modules/assistant/flows.md#read-the-account): profile, cards, ledger and answered charges.
- [Sign in and load the app](docs/modules/assistant/flows.md#sign-in-and-load-the-app): sign-in and the profile before any screen renders.
- [Chat with Clara in the app](docs/modules/assistant/flows.md#chat-with-clara-in-the-app): subscribe first, load the room second, merge by message id.
- [Catch up after a connection drop](docs/modules/assistant/flows.md#catch-up-after-a-connection-drop): reconnect and reload the room.
- [Refresh the app after a reply](docs/modules/assistant/flows.md#refresh-the-app-after-a-reply): the reply's effects invalidate exactly the stale queries.
- [Open Clara from the bank app](docs/modules/assistant/flows.md#open-clara-from-the-bank-app): the entry points and the topic that becomes the first message.

### Cases

- [Read the customer's cases](docs/modules/cases/flows.md#read-the-customers-cases): `GET /crud/cases` and the stage mapping.
- [Open a case](docs/modules/cases/flows.md#open-a-case): one conditional write keyed by the confirming ask.
- [Customer app reads cases](docs/modules/cases/flows.md#customer-app-reads-cases): the help page, case sheet, pills and chat card from one query.

### Identity

- [Sign up a customer](docs/modules/identity/flows.md#sign-up-a-customer): unconfirmed user and one-time code.
- [Email every code in the recipient's locale](docs/modules/identity/flows.md#email-every-code-in-the-recipients-locale): the `custom_message` trigger.
- [Confirm sign-up and create the customer row](docs/modules/identity/flows.md#confirm-sign-up-and-create-the-customer-row): the `post_confirmation` trigger.
- [Sign in](docs/modules/identity/flows.md#sign-in): email and password to Cognito tokens.
- [Authenticate an API request](docs/modules/identity/flows.md#authenticate-an-api-request): the Cognito authorizer in front of every route.
- [Assume role-customer for the customer's data](docs/modules/identity/flows.md#assume-role-customer-for-the-customers-data): per-customer isolation through a session tag.
- [Sign out](docs/modules/identity/flows.md#sign-out): session and cache cleared.

### Messaging

- [Open the chat](docs/modules/messaging/flows.md#open-the-chat): subscribe, then read the latest room.
- [Send a message](docs/modules/messaging/flows.md#send-a-message): one idempotent conditional write.
- [Retry a failed send](docs/modules/messaging/flows.md#retry-a-failed-send): the same message id is sent again.
- [Publish a stored message to the room](docs/modules/messaging/flows.md#publish-a-stored-message-to-the-room): stream to `chat_notifier` to AppSync Events.
- [Authorize a room subscription](docs/modules/messaging/flows.md#authorize-a-room-subscription): `onSubscribe` lets a customer into its own channel only.
- [Follow one message across lambdas](docs/modules/messaging/flows.md#follow-one-message-across-lambdas): `origin_trace_id` links the three traces.

### Data

- [Dataset pipeline](docs/modules/data/flows.md#dataset-pipeline): raw CSV to curated Parquet, contracts and figures.
- [Validate the policy sources](docs/modules/data/flows.md#validate-the-policy-sources): check the corpus sources without AWS.
- [Publish the policy corpus](docs/modules/data/flows.md#publish-the-policy-corpus): PDFs, embeddings and the vector index.
- [Tune the similarity cut](docs/modules/data/flows.md#tune-the-similarity-cut): one threshold per document language.
- [Search policies at runtime](docs/modules/data/flows.md#search-policies-at-runtime): cited excerpts for the assistant.
## More docs

- [docs/PRD.md](docs/PRD.md): what the product does and for whom.
- [docs/TRD.md](docs/TRD.md): stack, runtime architecture, commands and verification targets.
- [docs/ARD.md](docs/ARD.md): decisions and debt.
- `docs/modules/<module>/`: one folder per module with `prd.md`, `trd.md`, `ard.md`, `database.md` and `flows.md` where the module has code.
- [infra/docs/setup.md](infra/docs/setup.md): bootstrap, apply and destroy of the AWS stack.
