---
updated: 2026-10-02
source: 0017_policy_publish
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
| `hackathon/data/sql/figures/eda/` | One query per figure of the dataset analysis (12 queries) |
| `hackathon/data/sql/figures/pitch/` | The pitch's figures, each beside its base rate over any other transaction, each cited by one line of `docs/analysis/findings.md` in the docs root |
| `hackathon/data/sql/scratch/` | Work-in-progress queries, git-ignored output |
| `hackathon/data/figures/` | Committed CSV output, always rewritten from `sql/figures/` |
| `hackathon/data/src/bankdata/policies/` | The policy corpus build: `document` (parse), `validate`, `sources` (expand each base file into its country editions), `render` (placeholders with `core.facts`' renderers, figure spans), `chunk` (one chunk per section), `dedupe`, `pdf` (Markdown to HTML, WeasyPrint with `template/`, page location with PyMuPDF), `build` (manifest, skip unchanged, vectors, uploads), `tune`, `store` (local folder or S3), `cli` |
| `hackathon/data/policies/` | `SPEC.md` (the document contract), `RUNBOOK.md`, `queries.toml` and `tuning.json` (the labeled questions and the measured threshold of the published corpus), and `sample/` (two documents in the three languages, valid under the production limits, and labeled queries), used by tests and as the worked example of the spec |
| `hackathon/data/tests/` | Unit tests on synthetic fixtures under `tests/fixtures/raw/` and the policy sample, never touch the real dataset |

## CLI commands (no HTTP endpoints; this module is a pipeline, not a service)

| Command | Purpose |
|---|---|
| `bankdata ingest [tables...]` | Raw CSV to curated Parquet, all tables or a subset |
| `bankdata check [tables...]` | Runs contracts, exit code 1 on any failure |
| `bankdata figures <group>` | Runs `sql/figures/<group>`, rewrites `figures/<group>/` |
| `bankdata scratch [names...]` | Runs `sql/scratch` queries, prints and writes `<name>.csv` |
| `build-policies publish [--sources <folder>] [--prune]` | Builds and publishes the policy corpus; exit 1 when any document fails |
| `build-policies validate --sources <folder>` | Every problem with file and line, no AWS; exit 1 on any |
| `build-policies render --sources <folder> --out <dir> [--country XX]` | Each edition's PDF and its page count, no AWS; renders drafts that fail only length, word or parity rules |
| `tune-policies --queries <toml>` | Recall@3 and the similarity threshold on the real index, written to `policies/tuning.json` with the corpus hash |

Jobs, listeners or scheduled work: none; every command is run by hand from a developer's machine (the corpus build with the `policies-builder` role, assumed from the `personal` profile).

## Depends on

- The dataset pipeline reads only the raw CSV dataset under `BANKDATA_ROOT` and writes only to `BANKDATA_ROOT`.
- The corpus build depends on `clara-core` by path (`lambdas/core`: the policy facts, the renderers and word lists of `core.facts`, the vector metadata layout and clients, so documents and Clara agree) and on AWS: the policies and documents buckets, Bedrock `cohere.embed-multilingual-v3`, the S3 Vectors index.

## Depended on by

- No other module imports this package today; `hackathon/data/README.md` states "The runtime service does not import this package."
- assistant: `search_policies` queries the vector index and opens the PDFs this module publishes.
- A future seed process will read this module's curated Parquet to populate the serving DynamoDB tables (customers, products, transactions, complaints, staff, rooms, messages); infra/ defines those tables and identity owns the IAM roles on them, but the seed itself is not part of this module and its owner is not yet decided.
- Not related, but worth naming to avoid confusion: a deferred, separately owned turn-events analysis ETL will read raw turn events from S3 (a different bucket, ids only, no message text) and may reuse this module's DuckDB-over-S3 approach once built; it shares no code or data with this module today.

## Configuration

- `BANKDATA_ROOT`: where `raw/` and `curated/` live, a local directory or `s3://bucket`; default `.cache`.
- `BANKDATA_MEMORY_LIMIT`: DuckDB memory cap, spills to disk beyond it; default `2GB`.
- `BANKDATA_THREADS`: DuckDB threads; default `4`.
- With an S3 root, AWS credentials come from the usual chain (environment, profile, instance role); `hackathon/data/src/bankdata/duck.py` installs `httpfs` and creates a `credential_chain` secret.

- Corpus build: `POLICIES_BUCKET`, `DOCUMENTS_BUCKET`, `POLICY_INDEX_ARN`, `POLICIES_BUILDER_ROLE_ARN`, `POLICY_EMBEDDING_MODEL_ID`, `POLICY_DOCS_DOMAIN` in `data/.env`; WeasyPrint needs Pango and HarfBuzz-Subset on the machine.

## Testing

- Tests live in `hackathon/data/tests/` (`test_pipeline.py`, `test_analysis.py`, `policies/`), fixtures in `hackathon/data/tests/fixtures/raw/` and `hackathon/data/policies/sample/`; the policy tests build the sample into the `clara-testing` doubles.
- Run: the data row of `docs/TRD.md`, Verification targets (ruff, mypy strict, pytest).
- `uv run bankdata check` is the contract gate; `uv sync` installs the workspace.
