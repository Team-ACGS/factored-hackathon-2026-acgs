---
updated: 2026-09-27
source: setup
---

# models

Status: designed, not built.

Trains and versions Clara's two learned components: the intent router with abstention and the injection detector, both multilingual e5 embeddings plus logistic regression.
Both are trained on team-generated utterances with declared provenance, because the dataset's own text columns carry no information (`docs/analysis/findings.md`, `docs/problem-statement.md` 4.7).

## Boundaries

- Owns: training code for the router and the injection detector, the label set and its provenance, the split and leakage story, model selection against baselines, and versioning trained artifacts to S3.
- Does not own: serving the models at runtime (deferred, not in `infra/` yet), the turn pipeline and policy table that call them (assistant), the product-wide held-out set, system-level baselines and offline judge (evaluation), or the fraud score (a planted rule in the dataset, not a trained model, `docs/problem-statement.md` section 11).
- Code: `training/` (does not exist yet).

## Documents

- [prd.md](prd.md): product behavior
- [trd.md](trd.md): structure and endpoints
- [ard.md](ard.md): decisions and debt
- [database.md](database.md): tables and invariants
- [flows.md](flows.md): the training and promotion loop, as a diagram
