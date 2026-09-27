---
updated: 2026-09-27
source: setup
---

# evaluation: technical

Status: designed, not built.

## Structure

Planned, none of these paths exist yet.

| Path | What |
|---|---|
| `evaluation/` | Held-out custody, baselines, metric computation (H1-H5), adversarial cases, harness entrypoint for CI [inferido: exact file layout; only the folder name is decided, in `docs/tasks/_drafts/architecture_and_layout.md`, 2026-09-27, folder list] |
| A fourth `apps/` web, `analysts.factoredai.sdfles.com` | The improvement console; group and role `analysts`; decided as the console's home, **not built now** (Sebastian's decisions, 2026-09-27, item 6) [inferido: the folder name under `apps/` is not given, only the domain and the group] |

## Endpoints owned

Not yet specified.
No API route or lambda is named for this module in Sebastian's decisions or in `docs/tasks/_drafts/architecture_and_layout.md`; a role `role-analyst` exists for the console's IAM story, but the console is explicitly not built now, so no route exists to specify [inferido: whether a lambda is ever named for this module, versus the console reading the same tables through existing lambdas, is open].

Jobs, listeners or scheduled work:
- The held-out and adversarial run, in CI, against recorded LLM responses (`docs/kickoff-compliance.md`, "Reproducibility"; corroborated by `docs/product/03-architecture.md`'s "GitHub Actions, tests, eval-as-job with recorded LLM responses", the one line of that superseded doc not contradicted by the agreed architecture) [inferido: trigger, cadence and whether it also runs on demand are not specified].
- Turn events are emitted from day one regardless of this module's own build status: `lambdas/chatbot` (assistant) calls `PutEvents` at the end of every turn to the EventBridge bus `clara`, which fans out through Firehose to S3 as gzipped JSON, ids only, never message text, each event carrying a `trace_id` (Sebastian's decisions, 2026-09-27, item 7). Analyzing those events, and an LLM judge over held-out and sampled real conversations, are both **deferred, not dropped**: `docs/tasks/_drafts/turn_events_analysis.md` (status: deferred, 2026-09-27) proposes, pending Sebastian, that `assistant` keeps emitting and `evaluation` owns the event contract and the analysis, with DuckDB over S3 as the analysis engine and Claude Sonnet 5 as the eventual judge [inferido: that ownership line is a proposal in a deferred document, not a confirmed decision].

## Depends on

- assistant: the module under evaluation; the harness runs cases against its turn pipeline, and (once built) the deferred analysis reads its turn events, as input to metrics and to the improvement console (`docs/product/02-technical-flows.md`, black box C; `docs/tasks/_drafts/turn_events_analysis.md`).
- models: the router and injection detector are evaluated here as a "learned component against a baseline" (keyword matching, TF-IDF, Haiku zero-shot, and Jev if access is granted), per `docs/kickoff-compliance.md`, "Prove it works".
- cases: `complaints` is the case table (there is no separate `cases` table; `cases` is a module name only, Sebastian's decisions, 2026-09-27, item 1); the harness reads it to compute H1 and H2, and officer resolutions and agent labels on it feed the improvement console.
- messaging: reads `rooms` (which carries the customer's 1-5 rating and comment, Sebastian's decisions, item 8) and `messages` (for H4 re-ask grading); the rating is explicitly a weak signal that only prioritizes human review, never trains anything directly (`docs/product/02-technical-flows.md`, "Feedback email and rating").
- identity: owns the IAM roles (`role-customer`, `role-agent`, `role-officer`, `role-analyst`) and session/token semantics that the expired-session and cross-customer adversarial cases must reproduce against (Sebastian's decisions, item 2 and 6; `docs/kickoff-compliance.md`, "Measured failures").
- legal deadlines (`hackathon/docs/domain/legal-deadlines.md`, unverified as of 2026-09-26): an invented or wrong deadline is one of the named H2 unsafe-outcome classes (`docs/problem-statement.md` section 9), so the deadline table's verification status bounds what H2 can certify; cross-reference `hackathon/docs/modules/assistant/ard.md`, "legal due dates depend on an unverified deadline table".
- Bedrock Claude Sonnet 5 (low effort): the model named for the offline judge, not Opus (`docs/tasks/_drafts/architecture_and_layout.md`, "Decided", LLM roster; supersedes `docs/product/03-architecture.md`'s "Claude Opus 5, offline judge" and `02-technical-flows.md`'s black box C judge label, both 2026-09-26); the judge itself is deferred (`docs/tasks/_drafts/turn_events_analysis.md`, 2026-09-27), so this is the model chosen for a feature not yet being built.
- CloudWatch Logs, EMF metrics (namespaces `Clara/Backend`, `Clara/Assistant`), X-Ray tracing, and Powertools for AWS Lambda (Logger, Metrics, Tracer, Idempotency) on every lambda: the near-term observability this module's harness and any future console can read from, distinct from the deferred turn-events analysis (Sebastian's decisions, 2026-09-27, item 7).

## Depended on by

None confirmed.
`docs/product/01-flows.md` flow 4 shows the console's output ("new rules, data, prompts") flowing back to the assistant engine only through a human reviewer who promotes a change after a fresh held-out run, not as an automated call from this module into another; no other module's docs name a dependency on evaluation [inferido].

## Configuration

Not designed yet; no env vars are named in any source. [inferido]
The held-out set's custody model (kept by a person outside the team, hash committed before prompts are touched) implies at least one out-of-repo credential or handoff step, not yet specified. [inferido]

## Testing

Not built yet.
The module is itself the test harness for the rest of the system: `docs/problem-statement.md` section 9 defines the five metrics (H1-H5) it must compute, `docs/kickoff-compliance.md` ("Prove it works", "Measured failures") names the two baselines, the held-out custody and split rules, and the five adversarial cases (injection in the message, injection in `merchant_name`, expired session, cross-customer access, tool failure) the harness must run.
CI runs the harness with recorded LLM responses rather than live calls, per `docs/kickoff-compliance.md`, "Reproducibility".
The offline judge and the analysis of real turn events (which H5's "measured on the deployed system" framing would otherwise draw on) are deferred, so near term H1-H4 and the CI-measured half of H5 do not need either.
