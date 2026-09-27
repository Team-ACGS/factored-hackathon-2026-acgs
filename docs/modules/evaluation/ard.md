---
updated: 2026-09-27
source: setup
---

# evaluation: architecture and debt

## 2026-09-26: baselines are a rules bot and a naive LLM, at system level

- Decision: every hypothesis (H1-H5) is computed for three systems on the same held-out and adversarial material: a rules bot that always opens a claim, a naive LLM with raw tools and no policy layer, and Clara's assistant.
- Alternatives rejected: none recorded at this system level; `docs/ideas/round2/results/ranking.md` (ideation round, not the confirmed design) shows other candidate baselines from competing plans, such as an "L0" baseline that trusts the dataset's known-bad `affected_product_id` join, but none of that round's specific baseline designs was carried into the confirmed spec.
- Reason: the two baselines bound the claim from both sides, the rules bot shows what zero intelligence with maximum caution costs (every case becomes a claim), the naive LLM shows what intelligence without governance risks (no policy layer, no grounding, no isolation) [inferido].
- Debt created: none, not built yet.
- Revisit when: the harness is implemented and the two baselines are actually run.
- Source: docs/problem-statement.md section 9

This is a separate, system-level comparison from the classifier-level baseline named in `docs/kickoff-compliance.md`, "Learned component against a baseline" (keyword matching, TF-IDF, Haiku zero-shot, and Jev if access is granted), which measures the models module's router and injection detector specifically; do not conflate the two.

## 2026-09-26: five fixed adversarial cases

- Decision: injection in the customer's message, injection in a tool-output field (`merchant_name`), an expired session, an attempt at cross-customer access, and a tool call failure are the five adversarial cases the harness must run against every system under test.
- Alternatives rejected: none recorded.
- Reason: each targets a distinct control named elsewhere in the design (the injection detector on inbound text, the injection detector on tool outputs, session expiry checks, IAM row isolation, and bounded-retry/fallback behavior), so together they exercise every safety control the assistant module claims to have.
- Debt created: none of the five fixtures exist yet; `docs/kickoff-compliance.md` section 5 names reliability fixtures generally (retries, fallback, tool-down) as "the first thing to slip" of the whole plan. This module owns building all five fixtures; `hackathon/docs/modules/assistant/ard.md` already records, as its own debt, that no adversarial fixture for tool-output injection exists yet to validate its detector-on-tool-outputs decision in practice, the assistant module owns the runtime defense, this module owns the fixture that tests it.
- Revisit when: the fixtures are built and first run.
- Source: docs/kickoff-compliance.md, "Measured failures"

## 2026-09-26: CI runs the harness against recorded LLM responses, not live calls

- Decision: the held-out and adversarial harness runs in CI against recorded LLM responses, never live model calls.
- Alternatives rejected: live LLM calls in CI, implicitly rejected; the confirmed design states the recorded-response approach directly.
- Reason: keeps CI deterministic and free of both token cost and live-model availability risk on every pull request.
- Debt created: no recording or fixture mechanism (a cassette format, a mock provider, where recordings are stored and refreshed) is specified anywhere yet.
- Revisit when: the harness is implemented and a recording mechanism has to be chosen.
- Source: docs/kickoff-compliance.md, "Reproducibility"; consistent with docs/product/03-architecture.md, "GitHub Actions with recorded LLM responses", one of the few lines of that otherwise superseded document that the agreed architecture does not contradict.

## 2026-09-26: held-out custody by an outside custodian, hash committed before prompts are touched

- Decision: the held-out set is handed to a custodian outside the team, who commits its hash before the team touches any prompt.
- Alternatives rejected: none recorded [inferido].
- Reason: without an outside custodian and a committed hash, the team could see the held-out messages before or during prompt iteration and unconsciously tune to them, which would invalidate every H1-H5 number as an honest held-out result [inferido].
- Debt created: no custodian is named yet, no hash-commit mechanism (a file, a commit, a third-party attestation) is specified; `docs/kickoff-compliance.md` section 5 already flags the held-out's realism as thinner than it sounds, since it is written by real people but from scenario cards the team designed, not from a real distribution of dispute conversations.
- Revisit when: the held-out set is actually built and a custodian is identified.
- Source: docs/kickoff-compliance.md, "Leakage prevention"

## 2026-09-26: split by author and by scenario card, train in Spanish, test includes Portuguese

- Decision: the held-out split keys are author identity and scenario card, not a plain random row split; the training material is written in Spanish and the held-out test material includes Portuguese.
- Alternatives rejected: a simple random split, rejected implicitly since the confirmed design calls out author and scenario specifically as the leakage-relevant keys [inferido].
- Reason: a random split could put the same author's writing style, or the same scenario's phrasing, on both sides of the split, letting a model memorize an author's or a scenario's surface form rather than generalize across dialect [inferido].
- Debt created: none yet, this is a design not yet executed.
- Revisit when: the held-out set exists and the split can be checked against these keys.
- Source: docs/kickoff-compliance.md, "Appropriate split" and "Leakage prevention"

## 2026-09-26: promotion from the improvement console requires beating the current version with no more unsafe outcomes

- Decision: a rule change, threshold change or prompt change proposed in the improvement console is promoted only if it beats the current version on the frozen held-out plus the adversarial set, and does not increase the count of unsafe outcomes; otherwise it is rejected and shown with the numbers.
- Alternatives rejected: none recorded.
- Reason: makes "improve" accountable to the same yardstick used to evaluate the system itself, rather than a prompt edit judged by feel [inferido].
- Debt created: none, not built yet.
- Revisit when: the console is implemented and a first change is actually proposed for promotion.
- Source: docs/product/01-flows.md flow 4; docs/product/02-technical-flows.md, black box C

## 2026-09-27: offline judge is Claude Sonnet 5, not Opus, and is deferred

- Supersedes: 2026-09-26 judge model choice in docs/product/03-architecture.md ("Claude Opus 5 as judge... Opus 5 as teacher") and docs/product/02-technical-flows.md, black box C ("Offline judge [LLM] Opus 5").
- Decision: the offline judge, when built, runs on Claude Sonnet 5 (low effort) on Bedrock, no Opus; but the judge itself, over both the held-out set and sampled real conversations, is deferred, not dropped.
- Alternatives rejected: the mixed Haiku/Sonnet/Opus roster of the earlier, now-superseded `docs/product/03-architecture.md`, where Opus judged offline, Opus taught the classifiers by labeling, Haiku composed by default, and Sonnet was an escalation path.
- Reason: `docs/tasks/_drafts/architecture_and_layout.md` consolidates the whole LLM roster to Sonnet 5 only, across every role including the judge, for the same general reasoning already recorded in `hackathon/docs/modules/assistant/ard.md`'s own Sonnet-only decision, reducing variance and keeping cost and latency easy to reason about within the hackathon's budget [inferido: the specific quality tradeoff of Sonnet versus Opus as a judge is not discussed anywhere, only the general roster consolidation]; Sebastian defers the judge itself as part of deferring turn events analysis (`docs/tasks/_drafts/turn_events_analysis.md`, 2026-09-27), leaving H1-H4 and the CI half of H5 to run without it.
- Debt created: `docs/product/03-architecture.md`'s entire "How the large model is used" section (Opus as teacher and judge, Haiku as default composer, escalation to Sonnet) and its budget table are now stale and nobody has rewritten them to a Sonnet-only roster; separately, the improvement console's judge-notes input has no build date.
- Revisit when: `docs/tasks/_drafts/turn_events_analysis.md` is picked back up.
- Source: docs/tasks/_drafts/architecture_and_layout.md ("Decided", LLM roster); Sebastian's decisions, 2026-09-27, item 7; docs/tasks/_drafts/turn_events_analysis.md

## 2026-09-27: judge validated against human labels before its scores are trusted (design retained, deferred with the judge)

- Decision: whatever model judges conversations offline is itself validated against human labels (a kappa-style agreement check) before its scores are used in any metric; this requirement stands even though the judge itself is deferred.
- Alternatives rejected: none recorded; trusting the judge's output unvalidated is implicitly rejected.
- Reason: a judge that scores its own kind of model (an LLM judging an LLM's replies) needs an external check that it agrees with a human rather than only with itself [inferido].
- Debt created: no validation sample size, agreement threshold, or the two human labelers themselves are named yet; `docs/product/02-technical-flows.md` (2026-09-26, superseded on the judge model name but not on this validation requirement) names the mechanism only, not the numbers.
- Revisit when: the judge is implemented and a first validation run against human labels is done.
- Source: docs/kickoff-compliance.md, "Valid labels", "Learned component against a baseline"; docs/product/02-technical-flows.md, black box C

## 2026-09-27: the improvement console is a fourth web, not built now

- Decision: the improvement console is `analysts.factoredai.sdfles.com`, a fourth web in the `apps/` workspace, group and role `analysts`; explicitly not built now, distinct from `backoffice.factoredai.sdfles.com` (group `officers`, the ranked queue, formerly called "analyst").
- Alternatives rejected: `docs/product/03-architecture.md`'s "one SPA, four views", already superseded; folding the console into an existing app.
- Reason: gives the console its own IAM role and its own build timeline, separate from the officer-facing queue it is easy to confuse it with by name.
- Debt created: no lambda, API Gateway route, or `apps/` folder name is given yet for this fourth web; whether it needs a deployed backend at all before turn events analysis exists is open.
- Revisit when: the console's build is scheduled.
- Source: Sebastian's decisions, 2026-09-27, item 6

## 2026-09-27: turn events emitted from day one, their analysis deferred

- Decision: `lambdas/chatbot` (assistant) calls `PutEvents` at the end of every turn to the EventBridge bus `clara`, which fans out through Firehose to S3 as gzipped JSON, ids only, never message text, each event carrying a `trace_id`; this emission happens from day one regardless of this module's own build status. Analyzing those events (single-case investigation, rubric metrics with denominators, dialect flip rate and cost per case from real traffic) is deferred, not dropped.
- Alternatives rejected: `docs/tasks/_drafts/turn_events_analysis.md` proposes DuckDB over S3 as the eventual analysis engine (same engine as `data/`), with Athena optional, and proposes `assistant` as emitter with `evaluation` owning the event contract and the analysis; both are proposals pending Sebastian inside a deferred document, not confirmed decisions [inferido].
- Reason: emitting events costs little and is infrastructure other modules also rely on for observability; analyzing them, and building an LLM judge over them, is a larger, separate effort Sebastian chose to defer rather than build now.
- Debt created: this module's H5 ("measured on the deployed system") and any real-traffic instance of H3 have no data source until this analysis is built; corrects this module's earlier, wrong guess that traces would arrive as generic OpenTelemetry data to CloudWatch, when the design is specifically an ids-only event stream to S3, separate from CloudWatch Logs/EMF/X-Ray observability.
- Revisit when: `docs/tasks/_drafts/turn_events_analysis.md` is picked back up.
- Source: Sebastian's decisions, 2026-09-27, item 7; docs/tasks/_drafts/turn_events_analysis.md

## 2026-09-27: `complaints` is the case table, customer rating lives on the room

- Decision: there is no `cases` table; `complaints` is read (historical complaints and every one Clara opens), with a GSI by area and priority for the staff queue, and `cases` remains a module name only. The customer's 1-5 rating and optional comment are stored on `rooms` (messaging), not a separate feedback table.
- Alternatives rejected: an earlier, uncommitted assumption in this module's own docs of a distinct `cases` table and a distinct customer-feedback table, corrected here.
- Reason: `complaints` already carries the case lifecycle fields the dataset defines; a second table would duplicate it, and the rating is small enough to live alongside the conversation it rates.
- Debt created: none, this corrects a prior inference rather than creating new debt.
- Revisit when: not applicable.
- Source: Sebastian's decisions, 2026-09-27, items 1 and 8

## 2026-09-27: module is design only, nothing built

- Decision: the `evaluation/` folder and the improvement console are the agreed design and scope for this module, but neither exists yet; only `hackathon/data/` is built in this repo.
- Alternatives rejected: none, this entry records status rather than a choice.
- Reason: confirmed by directory listing of the hackathon repo at setup time, 2026-09-27.
- Debt created: the whole module is design debt rather than implementation debt, on top of the specific gaps already recorded above (no custodian, no fixtures, no recording mechanism, no deployed component, no judge validation numbers).
- Revisit when: the first implementation round for this module begins.
- Source: directory listing of the hackathon repo, 2026-09-27
