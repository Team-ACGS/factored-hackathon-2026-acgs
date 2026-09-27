---
updated: 2026-09-27
source: setup
---

# data: technical

Status: built.
Python 3.12, `uv` workspace, package `bankdata` (`hackathon/data/pyproject.toml`).
DuckDB is the engine at every step; Parquet is the storage format, local or S3, same code for both.

## Structure

| Path | What |
|---|---|
| `hackathon/data/src/bankdata/settings.py` | Reads `BANKDATA_ROOT`, memory and thread limits from the environment |
| `hackathon/data/src/bankdata/duck.py` | `connect()`: one DuckDB connection with limits, S3 credentials when the root is a bucket, the `data_clock` variable, every curated table registered as a view |
| `hackathon/data/src/bankdata/cli.py` | The `bankdata` Typer command (`ingest`, `check`, `figures`, `scratch`) |
| `hackathon/data/src/bankdata/pipeline/schemas.py` | Declared schema of every table: columns, types, key, event date, partitioning; single source for contracts |
| `hackathon/data/src/bankdata/pipeline/ingest.py` | Raw CSV to curated Parquet, partitioned by year/month, idempotent per table |
| `hackathon/data/src/bankdata/pipeline/contracts.py` | Contract checks: non-empty, dictionary ratio, declared columns and types, unique non-null key, event date within the data clock |
| `hackathon/data/src/bankdata/analysis/figures.py` | Runs every SQL file of a group, rewrites that group's output |
| `hackathon/data/src/bankdata/analysis/scratch.py` | Runs scratch queries, writes each result next to its SQL |
| `hackathon/data/sql/figures/eda/` | One query per figure of the dataset analysis (14 queries) |
| `hackathon/data/sql/scratch/` | Work-in-progress queries, git-ignored output |
| `hackathon/data/figures/` | Committed CSV output, always rewritten from `sql/figures/` |
| `hackathon/data/tests/` | Unit tests on synthetic fixtures under `tests/fixtures/raw/`, never touch the real dataset |

## CLI commands (no HTTP endpoints; this module is a pipeline, not a service)

| Command | Purpose |
|---|---|
| `bankdata ingest [tables...]` | Raw CSV to curated Parquet, all tables or a subset |
| `bankdata check [tables...]` | Runs contracts, exit code 1 on any failure |
| `bankdata figures <group>` | Runs `sql/figures/<group>`, rewrites `figures/<group>/` |
| `bankdata scratch [names...]` | Runs `sql/scratch` queries, prints and writes `<name>.csv` |

Jobs, listeners or scheduled work: none; every command is run by hand from a developer's machine.

## Depends on

- None. This module reads only the raw CSV dataset under `BANKDATA_ROOT` and writes only to `BANKDATA_ROOT`; it does not call any other module or service.

## Depended on by

- No other module imports this package today; `hackathon/data/README.md` states "The runtime service does not import this package."
- A future seed process will read this module's curated Parquet to populate the serving DynamoDB tables (customers, products, transactions, complaints, staff, rooms, messages); infra/ defines those tables and identity owns the IAM roles on them, but the seed itself is not part of this module and its owner is not yet decided.
- Not related, but worth naming to avoid confusion: a deferred, separately owned turn-events analysis ETL will read raw turn events from S3 (a different bucket, ids only, no message text) and may reuse this module's DuckDB-over-S3 approach once built; it shares no code or data with this module today.

## Configuration

- `BANKDATA_ROOT`: where `raw/` and `curated/` live, a local directory or `s3://bucket`; default `.cache`.
- `BANKDATA_MEMORY_LIMIT`: DuckDB memory cap, spills to disk beyond it; default `2GB`.
- `BANKDATA_THREADS`: DuckDB threads; default `4`.
- With an S3 root, AWS credentials come from the usual chain (environment, profile, instance role); `hackathon/data/src/bankdata/duck.py` installs `httpfs` and creates a `credential_chain` secret.

## Testing

- Tests live in `hackathon/data/tests/` (`test_pipeline.py`, `test_analysis.py`), fixtures in `hackathon/data/tests/fixtures/raw/`.
- Run: `cd hackathon/data && uv run pytest`.
- `uv run bankdata check` is the contract gate; `uv sync` installs the workspace.
