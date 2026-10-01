---
updated: 2026-10-01
source: 0013_policy_search
---

# data: architecture and debt

## 2026-09-27: DuckDB over Parquet as the only engine, local or S3

- Decision: every pipeline step (ingest, contracts, figures, scratch) runs through one DuckDB connection (`hackathon/data/src/bankdata/duck.py`); Parquet is the storage format at every step, and the same code path reads a local `.cache/` root or an `s3://` root by switching `BANKDATA_ROOT`.
- Alternatives rejected: none recorded. [inferido]
- Reason: reproducible, fast, no server to run; matches `docs/product/03-architecture.md`'s "Analytics store: DuckDB over Parquet in S3, reproducible, fast, no server" versus Redshift or Athena, called overkill for 5 GB. [inferido]
- Debt created: none.
- Revisit when: the curated dataset outgrows what a single DuckDB process handles on one machine.
- Source: setup

## 2026-09-27: Contracts as a hard gate, not a warning

- Decision: `bankdata check` (`hackathon/data/src/bankdata/pipeline/contracts.py`) exits 1 on any failed check (non-empty, dictionary ratio in [0.5, 2.0], declared columns and types present, unique non-null key, event date within the data clock plus 1 day tolerance).
- Alternatives rejected: none recorded. [inferido]
- Reason: a broken dataset must stop a CI run or a presentation prep rather than silently produce a wrong figure; `hackathon/data/README.md` frames the whole module around "contracts pass or the pipeline stops". [inferido]
- Debt created: contracts check schema and volume, not content; the real defects in `docs/analysis/findings.md` (random `claimed_amount`, `affected_product_id` pointing to another customer, `origin_interaction_id` always null) pass every contract because they are not schema violations. This is by design, not an oversight; the pipeline's job is structural, not semantic.
- Revisit when: a downstream consumer (the DynamoDB seed process, once built) needs a semantic contract, e.g. "affected_product_id belongs to the complaint's customer".
- Source: setup

## 2026-09-27: Schema declared once, in code, as the single source

- Decision: `hackathon/data/src/bankdata/pipeline/schemas.py` declares every table's columns, types, key, event date and partitioning in one Python dict (`TABLES`); contracts, ingest and (per the module's own comment) future Glue or Postgres DDL are meant to read from it.
- Alternatives rejected: none recorded. [inferido]
- Reason: one place to change a table's shape instead of duplicating it across ingest, contracts and any downstream DDL. [inferido]
- Debt created: the "Glue and Postgres DDL" generation this file's docstring anticipates does not exist yet; only contracts and ingest consume `TABLES` today.
- Revisit when: a component (e.g. the DynamoDB seed process) needs a DynamoDB or Postgres schema derived from these declarations.
- Source: setup

## 2026-09-27: The runtime product does not depend on this package

- Decision: `hackathon/data/README.md` states explicitly "The runtime service does not import this package."; nothing under `lambdas/`, `apps/` or `training/` (none of which exist yet) is expected to import `bankdata`. Confirmed: the process that seeds the serving DynamoDB tables from curated Parquet is a separate process, not this module; infra/ defines the tables and identity owns the IAM roles on them.
- Alternatives rejected: none recorded. [inferido]
- Reason: keeps the analysis pipeline (batch, DuckDB, can run for minutes) decoupled from request-serving code (Lambda, must be fast and stateless). [inferido]
- Debt created: the DynamoDB seed has no owner yet; it is a confirmed gap, not this module's to close.
- Revisit when: the seed process is built and given an owner.
- Source: setup

## 2026-09-27: Figures are committed CSV, always rewritten in full

- Decision: `bankdata figures <group>` deletes and rewrites every CSV under `figures/<group>/` from the SQL files currently in `sql/figures/<group>/`, and the output is committed to git (`hackathon/data/tests/test_analysis.py::test_figures_run_overwrites_group_with_one_csv_per_query` proves a stale CSV for a removed query is deleted).
- Alternatives rejected: leaving scratch output as the source of truth for doc figures (rejected by convention: `sql/scratch/` output is git-ignored and queries using `USING SAMPLE` are barred from `sql/figures/` because "figures must be reproducible", per the README).
- Reason: any number cited in a doc must be regenerable byte-for-byte from a committed query, and git then carries the history of how a figure changed. [inferido]
- Debt created: none.
- Revisit when: never, unless the team stops trusting hand-written doc figures entirely and wants figure generation enforced in CI.
- Source: setup

## 2026-10-01: document validation mirrors the reply check, with sample limits for tests

- Decision: validation reuses `core.facts.check`'s patterns (digits, currency, phones, URLs, emails, number words with their homonyms) plus month and weekday names, not the reply check's relative-day words; it exempts ordered list markers, terceros, terceiros and third parties, and fails a placeholder in any heading. Word and count limits are a `Limits` value: production 300 to 1,500 words, tests `SAMPLE_LIMITS` (20 to 400) so the committed sample stays short, and a test shows the production limits reject it. Each invalid fixture is a full copy of a valid document with exactly one violation.
- Alternatives rejected: a separate word list for documents (documents and Clara would drift); a full-length sample (thousands of words to maintain for tests).
- Reason: a document passes only what Clara could say.
- Debt created: none
- Revisit when: the first real build shows a rule failing documents that read well.
- Source: 0013_policy_search

## 2026-10-01: chunks are sized by a conservative token estimate and deduped per country

- Decision: tokens are estimated as characters over 3.5, so 450 tokens plus the title and section heading stay under Cohere's 512-token input with `truncate` NONE; overlap takes whole trailing sentences up to 15% of the chunk, else a word boundary; a short tail merges into the previous chunk when it fits. The embedded text is title, section and chunk; the metadata `text` is the chunk. Dedupe drops exact normalized duplicates within a country and 5-shingle Jaccard of 0.9 or more within a country and topic, keeping the first in document order.
- Alternatives rejected: a tokenizer dependency (Cohere's is not available offline); a corpus-wide exact dedupe (a country filter would lose the excerpt another country shares).
- Reason: a chunk must never be cut silently, and every country must keep its own excerpts.
- Debt created: none
- Revisit when: an embedding call fails for length, or C's recall points at chunk size.
- Source: 0013_policy_search

## 2026-10-01: editions are immutable, and the build is resumable and conservative with folders

- Decision: an edition is a document `version` plus its country's facts `version`: the PDF path is `<country>/<doc_id>-v<version>-f<facts_version>.pdf` and the chunk id and vector key `<doc_id>-v<version>-f<facts_version>-s<section>-c<chunk>`, and a PDF is never overwritten or deleted. The content hash covers the rendered Markdown (with the facts version), the kept chunks, the chunking parameters, the model and a build version; an unchanged hash is skipped. A changed text or facts value without a new version fails the document, which keeps its published entry. The manifest is written after each published document. A build from a local folder never prunes unless `--prune` is passed. The `policies-builder` role (also allowed `QueryVectors` and `GetVectors`, for tuning) has a 4-hour session; the CLI assumes it from the `personal` profile.
- Alternatives rejected: overwriting an edition in place (an old citation would open different text); one manifest write at the end (a crash would re-embed everything); pruning from any source (a folder of a few documents would unpublish the rest).
- Reason: a citation must always open the text it cited, and a 120-document build must survive interruptions.
- Debt created: none
- Revisit when: the build runs in CI or on a schedule.
- Source: 0013_policy_search

## 2026-10-01: pages come from WeasyPrint anchors and PyMuPDF text, with the brand committed

- Decision: each section heading carries an anchor `s<N>`, and WeasyPrint reports the page of each; PyMuPDF finds a chunk's first page by its opening 8, 5 or 3 words within its section's pages, falling back to the section's first page. The template commits the app's fonts (Hanken Grotesk and Newsreader, OFL, with their licenses) and its brand mark as SVG. `tune-policies` labels a query with `doc_id` and section number; the threshold is the cut that classifies most hits and unrelated questions correctly, placed halfway to the next lower similarity.
- Alternatives rejected: searching the whole PDF (a phrase repeated in another section would win); system fonts (pages would depend on the machine).
- Reason: a citation must open on the page that holds its words.
- Debt created: none
- Revisit when: Sebastian's review of the real PDFs finds a page off.
- Source: 0013_policy_search
