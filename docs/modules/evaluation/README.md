---
updated: 2026-09-27
source: setup
---

# evaluation

Status: designed, not built.

Held-out custody and baselines that turn Clara's five hypotheses (H1 safe automated resolution, H2 unsafe outcomes, H3 dialect flip rate, H4 re-asks per handoff, H5 cost and latency) into reported numbers, not demo impressions.
Also owns the improvement console: the review, diagnose, improve loop that turns traces, agent labels, ratings and judge scores into re-evaluated, promoted or rejected changes.
The console is the fourth web, `analysts.factoredai.sdfles.com`, group `analysts`, **not built now**; its offline judge and its analysis of real turn events are likewise deferred, not dropped (`docs/tasks/_drafts/turn_events_analysis.md`, 2026-09-27).

## Boundaries

- Owns: held-out set custody and its author/scenario split, the two system-level baselines (rules bot, naive LLM), computation of H1-H5, the five adversarial cases, and (deferred) the offline judge, the analysis of stored turn events, and the improvement console's review and promotion loop.
- Does not own: training the router and injection detector it measures (models), the assistant's own turn pipeline and its emission of turn events (assistant), case lifecycle and analyst work (cases, inbox), the live agent chat surface and the customer rating stored on the room (messaging), or verifying the legal deadline table's legal accuracy.
- Code: `evaluation/` (does not exist yet); a fourth `apps/` web for the console (not built now, folder name undecided).

## Documents

- [prd.md](prd.md): product behavior
- [trd.md](trd.md): structure and endpoints
- [ard.md](ard.md): decisions and debt
- [database.md](database.md): tables and invariants
