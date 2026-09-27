---
updated: 2026-09-27
source: setup
---

# inbox: technical

Status: designed, not built.
The design is black box B in `docs/product/02-technical-flows.md` (2026-09-26): categorize, priority score, ranked queue per area, eligible officers, round robin assignment.
Compute follows the agreed architecture (lambdas behind API Gateway, no ECS, no SSE); turn logic that feeds this module (the decision that creates a case) follows `docs/tasks/_drafts/turn_flow.md`.
This file does not restate either diagram.

## Structure

Planned, none of these paths exist yet.

| Path | What |
|---|---|
| `lambdas/` | Categorization, ranking and assignment logic, behind API Gateway; exact lambda name not decided by any source [inferido] |
| `apps/backoffice` | Officer console SPA at `backoffice.factoredai.sdfles.com` (formerly named "analyst"), part of the `apps/` pnpm workspace (React, Vite, TanStack Router) |

## Endpoints owned

Not yet specified.
The surface this module must cover, by evidence:

- Categorize a new case into disputes, fraud or follow-up, from the assistant's decision (`CLAIM` to disputes, `PROTECT` to fraud, `CASE_STATUS` with an issue to follow-up), per `docs/product/02-technical-flows.md` black box B.
- Compute the priority score on a case (amount in USD, risk signals, age, days left to the country's legal deadline, repeat complainer or third contact, regulator channel or escalated always top) and keep it versioned as weights change, per the same source.
- Serve the ranked queue per area to the backoffice console, via the `complaints` table's GSI by area and priority.
- Assign a case to an eligible officer (area matches, status Active, shift covers now, speaks the customer's language) by round robin, storing the next pointer per area; hold and flag the case with a supervisor notification when no one is eligible.

Jobs, listeners or scheduled work: none found; assignment appears to run synchronously on case creation or transfer, not on a schedule [inferido].

## Depends on

- cases: `complaints` is the shared case record (PK `customer_id`, GSI by area and priority for the staff queue); cases' lambda is the single writer for case content and officer resolutions, inbox writes only the ranking and assignment fields on the same item (Sebastian's decisions, round 2, 2026-09-27).
- assistant: the category comes from the engine's per-turn decision (`CLAIM`, `PROTECT`, `CASE_STATUS`); inbox does not re-derive intent, it consumes the decision already made.
- identity: Cognito staff pool, group `officers`, app client for `backoffice.`; the lambda reads the token's pool and `cognito:groups` and assumes `role-officer` to read and write case and roster data, it cannot access the tables directly (Sebastian's decisions, round 2).
- infra: defines the `complaints` table, its GSI by area and priority, and the `staff` table; inbox does not own the table definitions (Sebastian's decisions, round 2).
- `staff` table (DynamoDB, area/shift/language per officer) is the roster this module reads for eligibility (Sebastian's decisions, round 2, resolves the earlier open question about where the roster lives).
- a seed process, owner not decided, loads demo data into these tables; not this module (Sebastian's decisions, round 2).
- legal deadlines: `hackathon/docs/domain/legal-deadlines.md` is cited from memory and explicitly unverified as of 2026-09-26; the priority score's "days left to the legal deadline" term is wrong until that table is verified.
- Portuguese-speaking staff coverage: `docs/problem-statement.md` (v1 2026-09-26, section 4.6) measures 129 of 1,200 agents speak Portuguese and 0 of the 24 night-shift fraud agents do, so the eligibility filter can legitimately return zero officers for a Portuguese-speaking customer on the fraud area at night; this is the expected trigger for the "held in queue, flagged, supervisor notified" path, not a bug.

## Depended on by

- cases: the agent console (cases module) surfaces the area and assignment inbox wrote on the shared `complaints` item, though cases owns the item's content itself (boundary given in the brief).
- evaluation: aggregation by path, language and country over this module's assignment and ranking outcomes.

## Configuration

Not designed yet; no env vars are named in any source, but expect the `complaints` table name, its GSI name, `role-officer`'s ARN, and the `Clara/Backend` EMF namespace, same pattern as every other lambda. [inferido]

## Observability

CloudWatch Logs (structured JSON), X-Ray active tracing, and EMF metrics in namespace `Clara/Backend`, through AWS Lambda Powertools for Python (Logger, Metrics, Tracer); every lambda in the agreed architecture carries this, inbox included (Sebastian's decisions, round 2, 2026-09-27).

## Testing

Not built yet.
