---
updated: 2026-09-27
source: 0003_walking_skeleton
---

# Identity

Status: pools, roles and triggers built (tasks 0001 and 0003); customers sign up and sign in; staff sign-in has no web yet.

Identity is Cognito, the two user pools and their app clients, the two sign-in triggers, and the IAM roles a request-handling lambda assumes to reach DynamoDB.
It is the gate every customer, agent and officer passes through, and the mechanism that keeps a customer's own data reachable only by that customer.
It owns no product feature of its own; every other module depends on it to know who is asking and what they may see.

## Boundaries

- Owns: the `customers` and `staff` Cognito user pools and their app clients, the `agents`/`officers`/`analysts` groups (`analysts` reserved, not built), the `post_confirmation` and `pre_token_generation` triggers, and the `role-customer`, `role-agent`, `role-officer`, `role-analyst` IAM roles that decide who may do what on the DynamoDB tables `infra/` defines.
- Does not own: API Gateway routes, the DynamoDB tables themselves, the seed process that loads them (owner not decided, not this module), or any business decision; it only says who is signed in and which role their request may assume.
- Code: `lambdas/auth/`, `core.access` in `lambdas/core`, `infra/stacks/backend/` (`cognito.tf`, `access.tf`).

## Documents

- [prd.md](prd.md): product behavior
- [trd.md](trd.md): structure and endpoints
- [ard.md](ard.md): decisions and debt
- [database.md](database.md): tables and invariants
- [flows.md](flows.md): diagrams
