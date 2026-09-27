---
updated: 2026-09-27
source: setup
---

# data: product

Status: built.

## Purpose

Lets the team regenerate every number that goes into a doc or a slide with one command, from the same raw dataset, instead of trusting a figure someone typed by hand.
The user here is the team itself (analysts and engineers writing `docs/`), not a bank customer or agent.
`hackathon/data/README.md`: "It exists so that any number in a doc or a slide can be regenerated with one command."

## User flows

### Turn the raw dataset into curated tables

1. A developer sets `BANKDATA_ROOT` (local folder or `s3://` bucket) and runs `uv run bankdata ingest`.
2. The command reports rows written per table.
3. The developer runs `uv run bankdata check`; a non-zero exit means the dataset broke a declared contract (missing rows, wrong column, duplicate key, a row after the data clock) and nothing downstream should be trusted until it is fixed.

Errors and empty states: a failing contract prints which table and which check failed, with the offending count; the CLI exits 1 so a broken dataset stops a CI run rather than silently produce wrong figures.

### Turn a query into a committed figure

1. A developer writes an exploratory query under `sql/scratch/` and runs `uv run bankdata scratch` to see it on real data.
2. Once the query answers something that will be cited in a doc, the developer moves it to `sql/figures/<group>/<name>.sql`.
3. `uv run bankdata figures <group>` rewrites every CSV under `figures/<group>/`, committed to git.
4. The doc cites `figures/<group>/<name>.csv`; anyone can reproduce the number by rerunning the command.

Errors and empty states: a query using `USING SAMPLE` is barred from `sql/figures/` by convention (README), because a figure must be exactly reproducible; nothing in the code enforces this today. [inferido]

## Rules

- Every committed figure must trace to a SQL file under `sql/figures/`; nothing is hand-edited into `figures/`.
- A dataset that fails `bankdata check` is not fit to generate figures from, even if the commands would still run.
- Fixture-based tests never touch the real dataset, so this module's test suite proves the pipeline's logic, not the current data's cleanliness; only `bankdata check` against real data does that (see `docs/analysis/findings.md` for the last real run).

## Out of scope

- Serving any table to the running product: `hackathon/data/README.md` states the runtime service does not import this package.
- Seeding the serving DynamoDB tables (customers, products, transactions, complaints, staff, rooms, messages) from curated Parquet: infra/ defines those tables and identity owns the IAM roles on them, but the seed itself is a separate process, not this module.
- Fixing the dataset's own defects (see `docs/analysis/findings.md`): this module reports what the data is, it does not repair it.
- Turn events: this module neither produces nor reads them. They land in S3 from the running system and will later feed a deferred, separately owned analysis ETL; that ETL is undesigned and outside this module.

## Open questions

- Whether `sql/scratch/` queries using `USING SAMPLE` should be actively blocked from `sql/figures/` by a contract check, since today it is only a documented convention. [inferido]
