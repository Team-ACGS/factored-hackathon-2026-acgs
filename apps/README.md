# Apps

pnpm workspace with the customer web and the package it shares.

| Path | What |
|---|---|
| `customer/` | The customer web at [factoredai.sdfles.com](https://factoredai.sdfles.com): sign-in, the bank app (cards, movements, help, cases) and Clara's chat widget. React, Vite, TanStack Router and Query, Amplify for Cognito. |
| `ui/` | Shared Tailwind theme, fonts, shadcn/ui components and Clara's animated entity. |

The app is client-side only: it talks to `api.factoredai.sdfles.com` and to AppSync Events, and is served from S3 behind CloudFront.

## Run

Needs Node 22.12 or newer and pnpm 10.

```bash
pnpm install --frozen-lockfile
cp customer/.env.example customer/.env.local
```

Fill `customer/.env.local` with the public build-time values of the deployed stack:

| Variable | Where it comes from |
|---|---|
| `VITE_API_URL` | `terraform output api_url` in `infra/environments/prd` |
| `VITE_USER_POOL_ID` | `terraform output customers_pool_id` |
| `VITE_USER_POOL_CLIENT_ID` | `terraform output client_ids`, the `customer` entry |
| `VITE_REALTIME_HTTP_URL` | `terraform output realtime_url` with `wss://` as `https://`, `appsync-realtime-api` as `appsync-api` and the path `/event` |
| `VITE_REALTIME_NAMESPACE` | `rooms` |

The same values are the variables of the `customer-prd` Actions environment.

```bash
pnpm --filter @clara/customer dev
```

The dev server answers on `http://localhost:5173`; `/sign-in` is the signed-out entry.
Signing in works against the deployed stack with an existing account; creating accounts on `prd` is not part of local work.

## Test

```bash
pnpm lint
pnpm typecheck
pnpm test
```

Each command runs the workspaces one at a time.

## Flows

- [Sign in and load the app](../docs/modules/assistant/flows.md#sign-in-and-load-the-app)
- [Chat with Clara in the app](../docs/modules/assistant/flows.md#chat-with-clara-in-the-app)
- [Catch up after a connection drop](../docs/modules/assistant/flows.md#catch-up-after-a-connection-drop)
- [Refresh the app after a reply](../docs/modules/assistant/flows.md#refresh-the-app-after-a-reply)
- [Open Clara from the bank app](../docs/modules/assistant/flows.md#open-clara-from-the-bank-app)
- [Customer app reads cases](../docs/modules/cases/flows.md#customer-app-reads-cases)
- [Sign up a customer](../docs/modules/identity/flows.md#sign-up-a-customer)
- [Sign in](../docs/modules/identity/flows.md#sign-in)
- [Sign out](../docs/modules/identity/flows.md#sign-out)
- [Open the chat](../docs/modules/messaging/flows.md#open-the-chat)
