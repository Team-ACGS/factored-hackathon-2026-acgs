---
updated: 2026-09-27
source: setup
---

# models: architecture and debt

## 2026-09-26: multilingual e5 embeddings plus a logistic regression head, not a fine-tuned transformer

- Decision: both the intent router and the injection detector are `multilingual-e5-small` or `-large` embeddings feeding a logistic regression head, trained on the team's own labeled utterances.
- Alternatives rejected: fine-tuning a transformer end to end, per `docs/product/03-architecture.md`'s "Choices and why" table ("Fine-tuned transformers: no time, no data").
- Reason: millisecond inference, minutes to train on CPU, and a full label-and-split story the rubric asks for, against a fine-tune that needs more data and time than the dataset or the schedule provide. [inferido]
- Debt created: none.
- Revisit when: never, unless the day-5 comparison shows the frozen encoder or SetFit result does not clear the baselines.
- Source: docs/product/03-architecture.md ("Choices and why")

## 2026-09-26: SetFit contrastive fine-tuning considered as an optional second training level

- Decision: training has two possible levels: level 1 keeps the encoder frozen and fits only the logistic head on the 600 utterances; level 2 (SetFit) additionally fine-tunes the encoder contrastively on pairs built from the labels before the logistic head.
- Alternatives rejected: none recorded as rejected; both levels are kept as candidates, decided by measurement, not by design.
- Reason: level 1 is minutes of work and most of the gain; level 2 costs 5 to 15 minutes on CPU for the small encoder (about 30 for large) and may separate safety-critical nuances better (e.g. NOT_ME vs DOES_NOT_RECOGNIZE, voseo vs Portuguese). [inferido]
- Debt created: no day-5 comparison exists yet; which level (and which encoder size) ships is an open question in this module's prd.md.
- Revisit when: the day-5 held-out comparison (small frozen, small SetFit, large frozen, large SetFit, Claude Sonnet 5 zero-shot) is run.
- Source: docs/tasks/_drafts/turn_flow.md ("Encoder choice: `multilingual-e5-small` vs `-large`, and what \"training\" means for us")

## 2026-09-26: trained on team-generated utterances with declared provenance, never on the dataset's own text columns

- Decision: the router and the detector are trained only on utterances the team wrote and labeled, with provenance declared as such; the dataset's `complaints.description`, `call_transcripts.*` and similar text columns are never used as training input.
- Alternatives rejected: training on the dataset's own complaint or transcript text, which `docs/analysis/findings.md` and `docs/product/03-architecture.md` both name explicitly as a mistake ("Any model trained on those texts learns a five-entry lookup table and appears to understand"; "Any proposal trained on the dataset's text columns" is listed under "What we deliberately do not build").
- Reason: `complaints.description` has 5 distinct values across 67,095 rows and `call_transcripts.full_text` is 546 balance-inquiry templates with unfilled placeholders; there is no real signal to learn from.
- Debt created: the entire label set is team-generated, so every reported metric is offline over cases the team itself imagined, not real dispute conversations; `hackathon/docs/kickoff-compliance.md` names this explicitly as a stated weakness ("the held-out is written by real people but from scenario cards we designed, so the distribution is the one we imagined").
- Revisit when: never with this dataset; only if a future dataset carries real dispute text.
- Source: docs/problem-statement.md sections 4.7, 10; docs/analysis/findings.md

## 2026-09-27: labeling model is Claude Sonnet 5, not Opus

- Decision: Claude Sonnet 5 on Bedrock labels the training utterances.
- Alternatives rejected: Claude Opus 5 as teacher and second labeler, the role described in the now-superseded `docs/product/03-architecture.md` ("How the large model is used", "Teacher (distillation)").
- Reason: matches the single-model roster decided for the whole product (Claude Sonnet 5 only, low effort, plus labeling and the offline judge), per `docs/tasks/_drafts/architecture_and_layout.md`, "Decided".
- Debt created: `docs/product/03-architecture.md`'s cost estimate for "Claude Opus 5 as teacher" (US$2, labels 600 utterances and second-labels 150 held-out messages) no longer applies to the actual labeling model and has not been recomputed for Sonnet 5 in any source read. [inferido]
- Revisit when: a cost or latency measurement is taken with the actual labeling pipeline.
- Source: brief (models module scope, 2026-09-27); docs/tasks/_drafts/architecture_and_layout.md

## 2026-09-27: split by author and scenario card, held-out frozen and hashed before touching prompts

- Decision: the labeled set is split by author and by scenario card, not at random, so no author's phrasing or scenario appears on both sides; training happens in Spanish and testing includes Portuguese to check generalization; the held-out's hash is committed before anyone touches prompts, and a custodian outside the team keeps the held-out itself.
- Alternatives rejected: a random split, which would leak an author's idiolect or a scenario's phrasing across train and test.
- Reason: the kickoff rubric asks for demonstrated leakage prevention, and a random split over a small, team-written set is exactly where an author's style would otherwise leak. [inferido]
- Debt created: `hackathon/docs/kickoff-compliance.md` itself names the resulting held-out distribution as a stated weakness, not a defect of this decision: "there is not a single real dispute conversation in the dataset ... the distribution is the one we imagined."
- Revisit when: never as a method; the weakness above is about the data source, not the split method.
- Source: hackathon/docs/kickoff-compliance.md ("Leakage prevention", "Appropriate split")

## 2026-09-27: measured against keyword, TF-IDF, Claude Sonnet 5 zero-shot and Jev baselines

- Decision: the trained router and detector are compared on the same held-out against a keyword baseline, a TF-IDF baseline, Claude Sonnet 5 zero-shot, and Jev if access is granted, on accuracy, calibration, latency and cost.
- Alternatives rejected: shipping the learned component without a baseline comparison.
- Reason: `hackathon/docs/kickoff-compliance.md` names "learned component against a baseline" as a rubric requirement, and separately calls the router "correct but unremarkable" on its own, with "the discipline around it (labels, split, calibration, flip test)" as what carries it.
- Debt created: none of this comparison exists yet; it is designed only.
- Revisit when: the day-5 comparison is run.
- Source: hackathon/docs/kickoff-compliance.md ("Learned component against a baseline", "Where the proposal is weak")

## 2026-09-27: artifacts versioned in S3, never in git; serving deferred and not in `infra/`

- Decision: trained artifacts (the encoder weights or ONNX export, the logistic head, their metadata: data hash, split, validation metrics, threshold) are versioned in S3; git never holds a model artifact. Serving is planned as a Lambda container image, not EC2, and is out of `infra/` for now.
- Alternatives rejected: EC2 always-on serving (Sebastian's original proposal, per `docs/tasks/_drafts/architecture_and_layout.md`, "Sebastian's proposal"); the dedicated always-on ECS or App Runner model service and the in-process-with-the-engine shape drafted in `docs/tasks/_drafts/turn_flow.md`; both are superseded now that the whole application's compute is settled as lambdas, SQS and AppSync Events, not ECS or SSE.
- Reason: no VPC, no always-on cost, fits the hackathon's cost cap; a Lambda container image loads the model at cold start instead of keeping a server running between turns. [inferido, from the "Manager's recommendations" rationale in architecture_and_layout.md, which the Decided section adopts without restating the reason]
- Debt created: the compute shape is settled, but the bucket, key scheme, loading mechanism and the exact invocation between `lambdas/chatbot` and the model's Lambda container image are not designed in any source read.
- Revisit when: this module's serving path is actually built, expected after the turn pipeline itself.
- Source: docs/tasks/_drafts/architecture_and_layout.md ("Decided", "Manager's recommendations"); brief (models module scope, 2026-09-27)

## 2026-09-27: retraining only from human-reviewed conversations, promoted only on a held-out win

- Decision: new training rows come from a human reviewer labeling a past conversation (correct, wrong intent, should have escalated, unsafe), carrying provenance `reviewed_by_human`; a retrained version is evaluated on the frozen held-out plus the adversarial set and promoted only if it beats the current version without raising unsafe outcomes, otherwise rejected with the numbers kept.
- Alternatives rejected: promoting automatically, or retraining from raw customer messages without human review.
- Reason: "nothing changes in the engine without a human and a held-out run" (`docs/product/02-technical-flows.md`).
- Debt created: none; this loop is designed, not built.
- Revisit when: the improvement console and its labeling workflow are built (owned outside this module).
- Source: docs/product/02-technical-flows.md ("Black box C: review, diagnose, improve")

## 2026-09-27: intent router trains on the thirteen intents of `turn_flow.md`

- Decision: the router's class list is the thirteen intents of `docs/tasks/_drafts/turn_flow.md` ("Intents: what the customer says"): GREETING, ME, PRODUCTS, TRANSACTIONS, COMPLAINTS, UNRECOGNIZED_CHARGE, NOT_ME, CASE_STATUS, CONFIRM, DENY, PROVIDE_INFO, HUMAN, OUT_OF_SCOPE.
- Alternatives rejected: the five-class list in `docs/product/03-architecture.md` and `docs/product/02-technical-flows.md` (DOES_NOT_RECOGNIZE, NOT_ME, CASE_STATUS, HUMAN, OUT_OF_SCOPE), both superseded on this point.
- Reason: turn logic follows `docs/tasks/_drafts/turn_flow.md`, which reworked the class list to keep intent, dialogue state and policy decision separate, per Sebastian's decision.
- Debt created: none; this resolves the training-set boundary `hackathon/docs/modules/assistant/ard.md` had flagged as unreconciled between its understand stage and this module.
- Revisit when: never, unless the class list changes again in `turn_flow.md`.
- Source: setup decision, 2026-09-27; docs/tasks/_drafts/turn_flow.md

## 2026-09-27: module is design only, nothing built

- Decision: `training/` is the agreed code location for this module, but it does not exist yet in the hackathon repo; only `hackathon/data/` is built.
- Alternatives rejected: none, this entry records status rather than a choice.
- Reason: confirmed by directory listing of the hackathon repo at setup time.
- Debt created: none beyond the module being design-only; no file layout, configuration or serving invocation contract is fixed in any source read.
- Revisit when: this module's trd.md moves from design to code.
- Source: docs/tasks/_drafts/turn_flow.md; docs/product/03-architecture.md; docs/product/02-technical-flows.md
