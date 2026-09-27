---
updated: 2026-09-27
source: setup
---

# models: flows

Status: designed, not built.
Only the training and promotion loop is diagrammed; everything else in this module is a training script, not a flow.

## Train, evaluate, promote or reject

Runs whenever the labeled utterance set changes, or after a batch of human-reviewed conversations becomes new training rows (`docs/product/02-technical-flows.md`, "Black box C").

```mermaid
stateDiagram-v2
    [*] --> Labeled: team utterances + reviewed_by_human rows
    Labeled --> Split: split by author and scenario card
    Split --> Trained: e5 embeddings + logistic regression (SetFit optional)
    Trained --> Evaluated: score on frozen held-out + adversarial set
    Evaluated --> Promoted: beats current version, unsafe outcomes not up
    Evaluated --> Rejected: does not beat current version, or unsafe outcomes rise
    Promoted --> Versioned: artifact + metadata to S3
    Rejected --> [*]: numbers kept, current version stays serving
    Versioned --> [*]
```

```mermaid
sequenceDiagram
    participant R as Reviewer
    participant T as training/
    participant H as Frozen held-out
    participant S as S3 (versioned artifacts)

    R->>T: labeled conversation (provenance reviewed_by_human)
    T->>T: train router + injection detector
    T->>H: evaluate candidate
    H-->>T: metrics vs current version
    alt beats current, no more unsafe outcomes
        T->>S: upload artifact + metadata (data hash, split, metrics, threshold)
    else does not beat current
        T-->>R: rejected, with the numbers
    end
```
