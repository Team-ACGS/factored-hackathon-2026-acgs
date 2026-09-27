---
updated: 2026-09-27
source: setup
---

# models: technical

Status: designed, not built.
Compute follows the agreed architecture: lambdas, SQS, AppSync Events, not ECS or SSE.
`docs/product/03-architecture.md`'s in-process FastAPI-on-ECS-Fargate shape and `docs/tasks/_drafts/turn_flow.md`'s dedicated ECS model service are both superseded on this point.
Serving these two components is planned as a Lambda container image, not EC2; it is not yet reflected in `infra/`, which does not exist.
The intent router's class list is the thirteen intents of `docs/tasks/_drafts/turn_flow.md` ("Intents: what the customer says"); the five-class list in `docs/product/03-architecture.md` and `docs/product/02-technical-flows.md` is superseded.

## Structure

Nothing exists yet; the agreed folder is `training/` (`docs/tasks/_drafts/architecture_and_layout.md`, repo folder list).
No file layout inside `training/` is fixed in any source read. [inferido]

## Endpoints owned

None; this module has no HTTP surface.
Serving, when built, is planned as a Lambda container image invoked by the assistant module, not by API Gateway directly [inferido: no route or invocation contract is fixed in any source read].
`docs/tasks/_drafts/turn_flow.md`'s `Predictor` interface (`predict(text) -> label, probability, model_version`) was drafted for its own superseded ECS/EC2 compute layout; whether it still describes the call shape between `lambdas/chatbot` and the model's Lambda container image is not fixed in any source read. [inferido]

Jobs, listeners or scheduled work: training and retraining runs are triggered by a human review cycle, not scheduled (`docs/product/02-technical-flows.md`, "Black box C"); no automation of this trigger is designed.

## Depends on

- Labeled utterances in Spanish (es-MX, es-CO, es-AR) and Brazilian Portuguese, authored by the team with declared provenance; Claude Sonnet 5 on Bedrock labels the set (brief supersedes the "Opus as teacher" role in `docs/product/03-architecture.md`, "How the large model is used").
- Human review labels from live or held-out conversations, carrying provenance `reviewed_by_human` (`docs/product/02-technical-flows.md`).
- Multilingual e5 encoder weights (`multilingual-e5-small` or `-large`, undecided; SetFit contrastive fine-tuning considered as an optional second training level before the logistic head, `docs/tasks/_drafts/turn_flow.md`).
- S3 for artifact storage; artifacts are never committed to git (brief; `docs/tasks/_drafts/architecture_and_layout.md`, "Decided", "Own-model serving stays out of `infra/` for now").

## Depended on by

- assistant: calls the intent router (with abstention) and the injection detector (on the customer message and again on tool outputs) inside its turn pipeline, running as lambdas per the agreed architecture; the exact invocation between `lambdas/chatbot` and the model's Lambda container image is not fixed (`hackathon/docs/modules/assistant/trd.md`, "models: the injection detector and intent router ... loaded as versioned S3 artifacts; serving is not in `infra/` yet"). [inferido: invocation contract]
- evaluation: the component-level comparator work (this module's classifier against keywords, TF-IDF, Claude Sonnet 5 zero-shot, and Jev if access is granted, `hackathon/docs/kickoff-compliance.md`) and the product-wide held-out run both exercise this module's trained artifacts. [inferido: whether the comparator harness itself lives in `training/` or in `evaluation/` is not fixed in any source read]

## Configuration

Not designed yet; no env vars, artifact keys or bucket names are named in any source read. [inferido]

## Testing

Not built yet.
The held-out set is frozen and its hash committed before prompts or training code change (`hackathon/docs/kickoff-compliance.md`, "Leakage prevention"); promotion requires beating the current version on that held-out plus the adversarial set without raising unsafe outcomes (`docs/product/02-technical-flows.md`, "Black box C").
