# Data

The pipeline that turns the raw dataset into curated Parquet, the contracts that guard it, every query behind a figure in `docs/`, and the build of the policy corpus that Clara cites.
The lambdas do not import this package; they only read the policy index that its build publishes.
It exists so that any number in a doc or a slide can be regenerated with one command.

## Flow

```
raw CSV  --ingest-->  curated Parquet  --figures-->  figures/<group>/*.csv
                            |
                        --check-->  contracts: exit code 1 on any failure
```

DuckDB is the engine at every step.
Parquet is the storage format at every step, local or in S3, and the same code reads both.

## Layout

| Path | Purpose |
| --- | --- |
| `src/bankdata/settings.py` | Reads `BANKDATA_ROOT`, memory and thread limits from the environment; the only place that knows where data lives |
| `src/bankdata/duck.py` | `connect()`: one DuckDB connection with limits, S3 credentials when the root is a bucket, the `data_clock` variable, and every curated table registered as a view |
| `src/bankdata/cli.py` | The `bankdata` command |
| `src/bankdata/pipeline/schemas.py` | The declared schema of every table: columns, types, key, event date, partitioning; the single source for contracts and, later, Glue and Postgres DDL |
| `src/bankdata/pipeline/ingest.py` | Raw CSV to curated Parquet, partitioned by year and month, idempotent per table |
| `src/bankdata/pipeline/contracts.py` | Checks that block: rows present, declared columns and types, unique non-null keys, event dates within the data clock |
| `src/bankdata/analysis/figures.py` | Runs every SQL file of a group and rewrites that group's output, one CSV per file |
| `src/bankdata/analysis/scratch.py` | Runs scratch queries and writes each result next to its SQL |
| `src/bankdata/policies/` | The policy corpus: `build-policies` (validate, publish) and `tune-policies` |
| `policies/` | The spec of the corpus documents, the runbook, the labeled queries, the tuned thresholds and a sample corpus for tests |
| `sql/figures/eda/` | One query per figure of the dataset analysis |
| `sql/scratch/` | Work-in-progress queries; `bankdata scratch` writes `<name>.csv` next to each, ignored by git |
| `figures/` | Committed output, one CSV per query; always rewritten from `sql/figures/`, git keeps the history |
| `tests/` | Unit tests on synthetic fixtures; never touch the real dataset |
| `.cache/` | Local data, ignored by git: `raw/` and `curated/` |

## Datasets

Every table lives under `<root>/curated/<table>/` and is queried as a view with the same name.
Fact tables carry `year`, `month` and `day` columns taken from the source partition.

| Table | Rows | Purpose |
| --- | --- | --- |
| customers | 150,000 | Customer master: identity, country, segment, registration |
| products | 400,000 | Cards and accounts per customer with status and balances; a snapshot without history |
| branches | 350 | Branch dimension |
| service_agents | 1,200 | Contact center agents with language and accent |
| marketing_campaigns | 200 | Campaign dimension |
| daily_exchange_rates | 13,164 | Daily FX rates per currency |
| complaints | 67,095 | Formal complaints and claims, including unrecognized charges, with the case lifecycle |
| call_center_interactions | 686,296 | Every contact across channels with reason, resolution and duration |
| call_transcripts | 171,321 | Transcripts of a subset of calls; templated text |
| satisfaction_surveys | 212,759 | CSAT and NPS answers linked to interactions |
| transactions | 4,425,008 | Card and account movements with status, fraud flag and score |
| campaign_sends | 1,746,801 | Marketing sends, opens and clicks |
| digital_events | 15,620,994 | App and web clickstream; the largest table |

## Setup

Install [uv](https://docs.astral.sh/uv/), then from this directory:

```bash
uv sync
cp .env.example .env
```

`uv sync` creates `.venv/` with every dependency pinned by `uv.lock`, including Jupyter and pytest.

## Environment

| Variable | Default | Meaning |
| --- | --- | --- |
| `BANKDATA_ROOT` | `.cache` | Where `raw/` and `curated/` live: a local directory or `s3://bucket` |
| `BANKDATA_MEMORY_LIMIT` | `2GB` | DuckDB memory cap; it spills to disk beyond this instead of dying |
| `BANKDATA_THREADS` | `4` | DuckDB threads |

With an S3 root the AWS credentials come from the usual chain (environment, profile, instance role).
Lower the memory limit on a small machine; `1GB` and 2 threads ingest the full dataset on 7 GB of RAM.

## Commands

```bash
uv run bankdata ingest                     # every table, raw -> curated
uv run bankdata ingest transactions        # one table
uv run bankdata check                      # contracts; exit code 1 on any failure
uv run bankdata figures eda                # runs sql/figures/eda, rewrites figures/eda/
uv run bankdata scratch                    # every query in sql/scratch, writes <name>.csv next to each
uv run bankdata scratch test               # only sql/scratch/test.sql
```

## Working with the data

```python
from bankdata.duck import connect

con = connect()
con.sql("SHOW TABLES").show()
con.sql("SUMMARIZE complaints").show()
df = con.sql("SELECT category, count(*) AS n FROM complaints GROUP BY 1").to_df()
```

Every query is standard SQL.
`SUMMARIZE` gives nulls, distinct counts and ranges per column in one call.
Filtering on `year` or `month` reads only those partitions; any other filter still skips row groups by min and max.

## From scratch to figure

Write exploratory queries in `sql/scratch/` and run them with `bankdata scratch`; the terminal shows the first rows and `<name>.csv` holds the full result.
When a query produces a number that goes into a doc, move it to `sql/figures/<group>/<name>.sql`, run `bankdata figures`, and cite `figures/<group>/<name>.csv` from the doc.
Queries with `USING SAMPLE` stay in scratch: figures must be reproducible.

## Tests

```bash
uv run pytest
```

Fixtures under `tests/fixtures/raw/` are a few rows per table in the source layout.
The tests ingest them into a temporary root, run the contracts, plant a duplicate key and a future row to prove the contracts catch them, and execute every SQL file under `sql/figures/` so a broken query fails in CI, not on the day of the presentation.

## Policy corpus

The bank's policy documents become PDFs at `docs.factoredai.sdfles.com` and vectors in an S3 Vectors index that Clara's `search_policies` tool queries.
It needs the deployed stack, Bedrock access to Cohere Embed v4 and the AWS profile `personal`; `policies/RUNBOOK.md` has the one-time setup and every step, `policies/SPEC.md` the format of a document.
`uv run build-policies validate --sources <folder>` needs no AWS.
WeasyPrint needs the system libraries `libpango-1.0-0`, `libpangoft2-1.0-0` and `libharfbuzz-subset0` (Debian and Ubuntu) or `pango` (macOS).

```bash
uv run build-policies validate --sources policies/sample/sources
uv run build-policies publish --sources <folder>
uv run tune-policies --queries policies/queries.toml
```

## Flows

- [Dataset pipeline](../docs/modules/data/flows.md#dataset-pipeline)
- [Validate the policy sources](../docs/modules/data/flows.md#validate-the-policy-sources)
- [Publish the policy corpus](../docs/modules/data/flows.md#publish-the-policy-corpus)
- [Tune the similarity cut](../docs/modules/data/flows.md#tune-the-similarity-cut)
- [Search policies at runtime](../docs/modules/data/flows.md#search-policies-at-runtime)
