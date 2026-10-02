---
updated: 2026-10-02
source: 0017_policy_publish
---

# data

Status: built; the policy corpus build added by task 0013 and first published to prd by task 0017 (120 editions, threshold tuned).

Turns the raw LATAM Bank CSV dataset into curated Parquet, guards it with contracts, and runs every query behind a figure in `docs/`.
Also builds the bank's policy corpus: validates, renders, chunks, embeds and publishes the generated documents that `search_policies` cites.
Used by the team to prepare and verify the dataset and to publish the corpus; the runtime product does not import it (`hackathon/data/README.md`).

## Boundaries

- Owns: raw-to-curated ingestion, schema and volume contracts, the SQL behind every committed figure, `figures/` output; the policy corpus spec (`data/policies/SPEC.md`), its build and tuning, and what they publish (the policies and documents buckets, the vector index).
- Does not own: serving any data to the running product; seeding the serving DynamoDB tables (customers, products, transactions, complaints, staff, rooms, messages) from curated Parquet, that seed is a separate process, not this module, and its owner is not yet decided; anything about the deferred turn-events analysis ETL, whose only relation to this module is that it will later reuse the same DuckDB-over-S3 approach.
- Code: `hackathon/data/`

## Documents

- [prd.md](prd.md): product behavior
- [trd.md](trd.md): structure and endpoints
- [ard.md](ard.md): decisions and debt
- [database.md](database.md): tables and invariants
