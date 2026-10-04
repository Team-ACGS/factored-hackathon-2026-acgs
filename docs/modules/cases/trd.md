---
updated: 2026-10-04
source: 0022_story_actions
---

# Cases: technical

Status: case opening is built in `core.cases` and called by the assistant's rules (task 0022); the customer reads cases through `GET /crud/cases`; the agent routes and `apps/support` are designed, not built.

## Structure

| Path | What |
|---|---|
| `lambdas/core` | `core.cases`: the read allow-list, the case code, `open` (put if absent keyed by the confirming `ask_id`, then a consistent read-back) and `write_summary` (once, only if absent); the single writer of `complaints`, called in-process by `lambdas/chatbot` and `lambdas/crud` |
| `lambdas/crud` | Python lambda behind API Gateway; the agent/officer entrypoint (reads and resolutions) that calls into `lambdas/core`'s case code |
| `apps/support` | Static React + Vite + TanStack Router SPA, `support.factoredai.sdfles.com`, S3 + CloudFront, client-side only; the agent console for the `agents` group (live chat) |

## Endpoints owned

- Create a case at `Open`: no route; the assistant's rules call `core.cases.open` from `lambdas/chatbot` on a confirming tap.
- `GET /crud/cases` (assistant's `crud`): the customer's cases with code, type, stage and the summary fields.

Designed, not built:

- Read a case and its handoff package, for the agent console: an API Gateway route on `lambdas/crud` (`docs/product/02-technical-flows.md`, black box A step 6, and `01-flows.md` flow 2: "agent console shows the prepared case").
- Resolve a case: an API Gateway route on `lambdas/crud`, the single write path (via `lambdas/core`) for both an agent's in-chat resolution and an officer's resolution from the backoffice queue.
- List or fetch cases assigned to the current agent, for the console: an API Gateway route on `lambdas/crud`.

Jobs, listeners or scheduled work: none found.

## Depends on

- identity module: owns the IAM roles `lambdas/core`'s case code assumes to read and write the `complaints` table: `role-customer` when called from `lambdas/chatbot` (Clara opening a case), `role-agent` or `role-officer` when called from `lambdas/crud` (agent/officer reads and resolutions); neither lambda reads or writes the table directly.
- Cognito staff pool, groups `agents` (support., live chat) and `officers` (backoffice., reviews complaints); app clients per app.
- assistant module (`lambdas/chatbot`): decides `HANDOFF`, or an immediate `CLAIM`/`PROTECT`, and calls `lambdas/core` in-process to create the case and attach the handoff package; cases does not decide when this happens, it only owns the code that writes it [boundary given in the brief].
- messaging module (`lambdas/messages`): agent messages in the live chat take the same path as every other message, `POST /messages`; the chat transport itself belongs to messaging, not cases.
- observability stack: AWS Lambda Powertools (Python), Logger/Metrics/Tracer in every lambda that calls into `lambdas/core`; case creation is idempotent through a conditional write; CloudWatch Logs (structured JSON), EMF metrics in namespace `Clara/Backend`, X-Ray active tracing.

## Depended on by

- inbox module: ranks and assigns cases on the same `complaints` row cases owns; it writes only the ranking and assignment fields, never the case's status or content.
- assistant module: `CASE_STATUS` turns read case status back to the customer, via `lambdas/core`, from within `lambdas/chatbot` (`docs/tasks/_drafts/turn_flow.md`, now the agreed turn logic).

## Configuration

Not designed yet beyond the observability stack above.
Expect the `complaints` table name and the `role-customer`/`role-agent`/`role-officer` ARNs as environment variables set by Terraform on every lambda that bundles `lambdas/core`, same as every other lambda [inferido].

## Testing

- `lambdas/tests/core/test_writers.py`: a case opens once per ask and reads back, a mismatching row is not confirmed, the summary is written once.
- `lambdas/tests/core/test_actions.py`: the fraud, claim and service cases of the story, redelivered and double-tapped.
