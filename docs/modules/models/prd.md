---
updated: 2026-09-27
source: setup
---

# models: product

Status: designed, not built.

## Purpose

Gives the assistant two fast, cheap decisions on every customer message: whether the message is an attack to ignore (the injection detector), and what the customer is asking for, with the option to abstain instead of guessing (the intent router).
The user of this module is the team building and evaluating Clara, not a bank customer or agent; a customer never interacts with `models` directly, only through the assistant's turn pipeline.
It exists because the dataset offers nothing to train a classifier on: `complaints.description` is five sentences and `call_transcripts` are templated balance inquiries (`docs/analysis/findings.md`, "Text columns are empty of information"), so both components are trained on utterances the team wrote and labeled itself, with provenance declared rather than hidden (`docs/problem-statement.md` section 10, "Learned components are trained on team-generated data with declared provenance, because the dataset offers no alternative").

## User flows

### Train a component

1. A team member writes or extends the labeled utterance set for the router or the injection detector, in Spanish (es-MX, es-CO, es-AR) and Brazilian Portuguese.
2. Claude Sonnet 5 labels the set; agreement between the model and human labelers is reported as label quality [inferido: the exact human-labeling process, one or two people, is not fixed in any source read].
3. The set is split by author and by scenario card, not at random, so the same person's phrasing or the same case never appears on both sides of the split; the held-out hash is committed before anyone touches prompts (`hackathon/docs/kickoff-compliance.md`, "Leakage prevention").
4. Multilingual e5 embeddings feed a logistic regression head; SetFit contrastive fine-tuning of the encoder is considered as a second level before the logistic head, compared against the frozen-encoder version on the held-out (`docs/tasks/_drafts/turn_flow.md`, "Encoder choice").
5. The trained artifact is compared against baselines (keywords, TF-IDF, Claude Sonnet 5 zero-shot, and Jev if access is granted, `hackathon/docs/kickoff-compliance.md`) and only kept if it earns its place.
6. The chosen artifact, with its data hash, split and validation metrics, is versioned to S3; nothing is committed to git.

### Abstain instead of guessing

1. The intent router scores a customer message against the thirteen intents of `docs/tasks/_drafts/turn_flow.md`.
2. If confidence is above the threshold, the label is used to route the turn.
3. If confidence is below the threshold, the router abstains and the turn asks a templated clarifying question instead of acting on a guess (`hackathon/docs/kickoff-compliance.md`, "Clarify ambiguous requests").

### Detect an injection attempt

1. The injection detector scores the customer's message, and separately scores tool outputs that carry attacker-reachable text (a merchant name, a stored case note).
2. A message or tool output scored as an attack gets a fixed, logged reply instead of reaching the router, the composer, or a write (`docs/tasks/_drafts/turn_flow.md`, `hackathon/docs/modules/assistant/ard.md` "injection detector runs on tool outputs, not only on the customer message").

### Improve from reviewed conversations

1. A human reviewer labels a past conversation as correct, wrong intent, should have escalated, or unsafe.
2. Labeled conversations become new training rows with provenance `reviewed_by_human` (`docs/product/02-technical-flows.md`, "Black box C: review, diagnose, improve").
3. The router and detector are retrained and evaluated on the frozen held-out plus the adversarial set.
4. A retrained version is promoted only if it beats the current version and does not raise unsafe outcomes; otherwise it is rejected and the numbers are kept.

## Rules

- No component is trained on the dataset's own text columns (`complaints.description`, `call_transcripts.*`); every label traces to a team-written utterance with declared provenance.
- The held-out set is frozen and its hash committed before prompts or training code changes, and it is kept by a custodian outside the team (`hackathon/docs/kickoff-compliance.md`).
- A retrained version replaces the serving version only after it beats the current one on the same held-out and does not increase unsafe outcomes.
- The router abstains below its confidence threshold rather than guessing; abstention is a designed behavior, not a failure mode.
- Portuguese coverage is entirely team-generated; there is not one real Portuguese example in the dataset (`docs/problem-statement.md` 4.6).

## Out of scope

- Deciding what the assistant does with a label: the policy table and state machine own that (assistant module).
- Composing or extracting text from a customer message: Claude Sonnet 5 does that, not a trained component (`docs/tasks/_drafts/architecture_and_layout.md`).
- The fraud score: a planted deterministic rule in the dataset (score above 30 implies fraud), reported as a rule, never presented as a trained model (`docs/problem-statement.md` section 10).
- The product-wide held-out set, system-level baselines (rules bot, naive LLM) and the offline judge: owned by `evaluation/`.
- Serving infrastructure: designed as a Lambda container image, following the agreed lambdas/SQS/AppSync Events architecture; not built and not in `infra/` yet.

## Open questions

- Whether the encoder is `multilingual-e5-small` or `-large`, and whether SetFit contrastive fine-tuning is used or the encoder stays frozen with only the logistic head trained, is left to a day-5 comparison on the held-out (accuracy, recall on the safety-critical class, calibration, latency, memory); no source read fixes the answer yet (`docs/tasks/_drafts/turn_flow.md`). [inferido: resolution pending, not yet written anywhere]
- Who authors and maintains the labeled utterance set (a shared artifact with the assistant module's intent list, or owned solely here) is not fixed in any source. [inferido]
- The exact number of training utterances is cited as 600 in `docs/tasks/_drafts/turn_flow.md` and as "the 600 training utterances" plus "150 held-out messages" in the superseded `docs/product/03-architecture.md`; whether these numbers still hold after the labeling model changed from Opus to Claude Sonnet 5 is not confirmed anywhere read. [inferido]
