---
updated: 2026-10-01
source: 0015_policy_base_layout
---

# data: database

Not a database; a set of curated Parquet tables under `<BANKDATA_ROOT>/curated/<table>/`, each queried as a DuckDB view of the same name.
Columns and types live in `hackathon/data/src/bankdata/pipeline/schemas.py` (`TABLES`), the single source for both ingestion and contracts.

## Tables owned

| Table | Purpose |
|---|---|
| `customers` | Customer master: identity, country, segment, registration |
| `products` | Cards and accounts per customer with status and balances; a snapshot without history |
| `branches` | Branch dimension |
| `service_agents` | Contact center agents with language and accent |
| `marketing_campaigns` | Campaign dimension |
| `daily_exchange_rates` | Daily FX rates per currency |
| `complaints` | Formal complaints and claims, including unrecognized charges, with the case lifecycle |
| `call_center_interactions` | Every contact across channels with reason, resolution and duration |
| `call_transcripts` | Transcripts of a subset of calls; templated text, no real content (`docs/analysis/findings.md`) |
| `satisfaction_surveys` | CSAT and NPS answers linked to interactions |
| `transactions` | Card and account movements with status, fraud flag and score |
| `campaign_sends` | Marketing sends, opens and clicks |
| `digital_events` | App and web clickstream; the largest table |

## Tables referenced

None. This module reads only its own raw CSV input; no other module's data is read here.

## Stores of the policy corpus

| Store | Purpose |
|---|---|
| Policies bucket (versioned) | Sources at `<doc_id>/<language>.md` (one base file per language, expanded to its countries' editions), rendered editions at `rendered/<country>/<edition>.md`, and `manifest.json` (documents, versions, hashes, vector keys, PDF URLs, corpus hash; no timestamps) |
| Documents bucket, behind `docs.factoredai.sdfles.com` | One PDF per edition at `<country>/<doc_id>-v<version>-f<facts_version>.pdf`, immutable and cached for a year |
| S3 Vectors index `policies` | One vector per excerpt, keyed by its chunk id; metadata layout in `core.retrieval.ChunkRecord` |

## Invariants kept in code

- Every table's declared columns and types (`pipeline/schemas.py`) must be present in the curated Parquet, checked by `bankdata check`, not by Parquet itself.
- `key` columns (e.g. `customer_id`, `complaint_id`) must be unique and non-null; enforced only by the contract check, not by any storage-level constraint.
- Event-dated tables (`complaints`, `transactions`, and others with an `event_date`) must not contain rows past the data clock (`2026-06-18`, plus one day tolerance); enforced only by the contract check.
- Fact tables are partitioned by `year`/`month` (and carry a `day` column from the source partition); dimension tables are not.
- Row counts must sit within 0.5x to 2x of the dataset's advertised dictionary count (`contracts.DICTIONARY_RATIO`); a documented tolerance, not a hard equality, because the real delivered counts run 0.84x to 1.56x of the dictionary (`docs/analysis/findings.md`).

- An edition is immutable: the build refuses a changed source with the same `version` and a changed facts value with the same country facts `version`.
- The manifest lists exactly the vectors of each document; a new edition deletes the previous keys, and only a bucket build (or `--prune`) removes a document missing from the sources; PDFs are never deleted.
- The manifest is rewritten after each published document, so a crash loses at most the document in flight.

## Migrations of note

- No migration tooling; `hackathon/data/src/bankdata/pipeline/schemas.py` is the schema, and `bankdata ingest` rewrites the curated Parquet from raw CSV on every run (`ingest._reset` deletes and recreates each table's target folder locally; S3 targets are not reset, per `ingest._reset`).
- 2026-09-27: initial pipeline and all 13 tables added in one commit (`17fb935`); no schema history yet.
