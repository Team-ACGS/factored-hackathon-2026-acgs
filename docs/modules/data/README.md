---
updated: 2026-09-27
source: setup
---

# data

Status: built.

Turns the raw LATAM Bank CSV dataset into curated Parquet, guards it with contracts, and runs every query behind a figure in `docs/`.
Used by the team to prepare and verify the dataset; the runtime product does not import it (`hackathon/data/README.md`).

## Boundaries

- Owns: raw-to-curated ingestion, schema and volume contracts, the SQL behind every committed figure, `figures/` output.
- Does not own: serving any data to the running product; seeding the serving DynamoDB tables (customers, products, transactions, complaints, staff, rooms, messages) from curated Parquet, that seed is a separate process, not this module, and its owner is not yet decided; anything about the deferred turn-events analysis ETL, whose only relation to this module is that it will later reuse the same DuckDB-over-S3 approach.
- Code: `hackathon/data/`

## Documents

- [prd.md](prd.md): product behavior
- [trd.md](trd.md): structure and endpoints
- [ard.md](ard.md): decisions and debt
- [database.md](database.md): tables and invariants
