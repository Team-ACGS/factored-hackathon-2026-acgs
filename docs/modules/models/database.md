---
updated: 2026-09-27
source: setup
---

# models: database

Not a database.
This module has no tables; its state is trained artifacts (encoder weights or an ONNX export, the logistic head, and metadata: data hash, split, validation metrics, threshold) versioned in S3, never in git and never in DynamoDB.
No bucket name, key scheme or metadata schema is fixed in any source read. [inferido]

## Tables owned

None.

## Tables referenced

None.
This module does not read the DynamoDB serving tables or the curated Parquet the `data` module produces; its input is the team-written, labeled utterance set, not the bank dataset.

## Invariants kept in code

- A trained artifact is only promoted to serve if it beats the current version on the frozen held-out plus the adversarial set, without raising unsafe outcomes; enforced by the evaluation step, not by any storage constraint (`docs/product/02-technical-flows.md`, "Black box C").
- The held-out set's hash is committed before prompts or training code change, so it cannot be silently swapped after the fact (`hackathon/docs/kickoff-compliance.md`, "Leakage prevention").
- The split keeps every author and every scenario card on one side only, train or held-out, never both; enforced by the split procedure, not by any schema.

## Migrations of note

None; nothing is built yet.
