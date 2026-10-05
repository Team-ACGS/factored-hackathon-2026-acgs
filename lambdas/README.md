# Lambdas

uv workspace of the Python 3.12 lambdas behind Clara, plus the shared package every one of them bundles.

| Path | What |
|---|---|
| `core/` | Shared package: access and role assumption, read models, messaging, the turn (router, rules, story, handoff), the open mode graph, tools, policy search, facts and checks |
| `crud/` | `/crud/*`: the customer's profile, demo setup, cards, transactions, cases and answered charges |
| `messages/` | `/messages/*`: sending a message, reading the latest room |
| `chat_notifier/` | Stream consumer that publishes each stored message to the room's AppSync Events channel |
| `chatbot/` | Stream consumer that answers each customer message: safety floor, open mode graph on Bedrock, story path, events |
| `auth/` | Cognito triggers: `custom_message`, `post_confirmation`, `pre_token_generation` |
| `testing/` | Dev-only Bedrock, S3 Vectors and Converse test doubles; never bundled |
| `tests/` | One folder per package, run on moto and the test doubles; no AWS account needed |

No lambda calls another lambda; shared behavior lives in `core`.

## Run

Needs Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
uv run mypy
```

The tests take a few minutes.
Run one command at a time: the suite is memory-hungry.

Build the zips that CI deploys:

```bash
uv run python build.py            # every function into dist/
uv run python build.py crud       # one
```

Terraform creates each function on a bootstrap bundle; `.github/workflows/deploy-lambdas.yml` uploads the real zips on every merge to `main`.

## Flows

- [Answer a customer message](../docs/modules/assistant/flows.md#answer-a-customer-message)
- [Run the open mode graph](../docs/modules/assistant/flows.md#run-the-open-mode-graph)
- [Block a card and hand off](../docs/modules/assistant/flows.md#block-a-card-and-hand-off)
- [Set up the demo account](../docs/modules/assistant/flows.md#set-up-the-demo-account)
- [Add a transaction](../docs/modules/assistant/flows.md#add-a-transaction)
- [Read the account](../docs/modules/assistant/flows.md#read-the-account)
- [Read the customer's cases](../docs/modules/cases/flows.md#read-the-customers-cases)
- [Open a case](../docs/modules/cases/flows.md#open-a-case)
- [Send a message](../docs/modules/messaging/flows.md#send-a-message)
- [Publish a stored message to the room](../docs/modules/messaging/flows.md#publish-a-stored-message-to-the-room)
- [Email every code in the recipient's locale](../docs/modules/identity/flows.md#email-every-code-in-the-recipients-locale)
- [Confirm sign-up and create the customer row](../docs/modules/identity/flows.md#confirm-sign-up-and-create-the-customer-row)
- [Assume role-customer for the customer's data](../docs/modules/identity/flows.md#assume-role-customer-for-the-customers-data)
- [Search policies at runtime](../docs/modules/data/flows.md#search-policies-at-runtime)
