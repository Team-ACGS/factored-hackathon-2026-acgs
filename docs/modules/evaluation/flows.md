---
updated: 2026-09-27
source: setup
---

# evaluation: flows

Status: designed, not built.

## Held-out and adversarial run

Runs in CI, against recorded LLM responses, whenever the harness is invoked; it is the source of H1-H4 and the CI half of H5.
The judge step is deferred (`docs/tasks/_drafts/turn_events_analysis.md`, 2026-09-27), kept in the diagram as the design to build toward.

```mermaid
sequenceDiagram
  participant CI as CI job
  participant H as Harness
  participant B1 as Rules bot
  participant B2 as Naive LLM
  participant C as Clara (assistant)
  participant J as Offline judge (Sonnet 5, deferred)
  CI->>H: run held-out + adversarial set
  H->>B1: every case
  H->>B2: every case
  H->>C: every case
  B1-->>H: outcomes, no verification
  B2-->>H: outcomes, ungoverned
  C-->>H: outcomes + full trace
  H->>J: sampled conversations
  J-->>H: clarity, tone, language, next-steps scores
  H-->>CI: H1-H5 per system, with denominators
```

Source: `docs/kickoff-compliance.md`, "Reproducibility" and "Measured failures"; `docs/problem-statement.md` section 9.

## Improvement console: review, diagnose, improve

Not built now: the console is the fourth web, `analysts.factoredai.sdfles.com`, and its judge-scores input is deferred with the judge itself (Sebastian's decisions, 2026-09-27, items 6 and 7).
Kept here as the design to build toward; runs whenever a human reviewer opens the console, and nothing here changes the live assistant by itself.

```mermaid
stateDiagram-v2
  [*] --> Aggregated: traces, agent labels, ratings, judge scores arrive
  Aggregated --> Reviewed: reviewer opens a conversation
  Reviewed --> Labeled: reviewer labels it (correct / wrong intent / should have escalated / unsafe)
  Labeled --> Proposed: reviewer proposes training rows, a rule change, or a prompt change
  Proposed --> Evaluated: re-run on the frozen held-out + adversarial set
  Evaluated --> Promoted: beats current version, no more unsafe outcomes
  Evaluated --> Rejected: does not beat it, or unsafe outcomes rise
  Promoted --> [*]
  Rejected --> [*]
```

Source: `docs/product/01-flows.md` flow 4; `docs/product/02-technical-flows.md`, black box C.
