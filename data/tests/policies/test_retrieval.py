import json
from pathlib import Path

import pytest
from clara_testing import MODEL_ID, local_embedder, local_index
from core.retrieval import VectorRetriever

from bankdata.policies.build import build
from bankdata.policies.chunk import Chunking
from bankdata.policies.spec import SAMPLE_LIMITS
from bankdata.policies.tune import Outcome, load_queries, threshold, tune
from policies_harness import SAMPLE, corpus

QUERIES = load_queries(SAMPLE / "queries.toml")


@pytest.fixture(scope="module")
def outcomes(tmp_path_factory: pytest.TempPathFactory) -> tuple[Outcome, ...]:
    sample = corpus(tmp_path_factory.mktemp("retrieval"))
    report = build(sample.target, limits=SAMPLE_LIMITS, chunking=Chunking())
    retriever = VectorRetriever(local_embedder(sample.bedrock), local_index(sample.vectors))
    tuning = tune(retriever, QUERIES, report.corpus_hash, MODEL_ID)
    summary = json.loads(tuning.to_json())
    assert summary["corpus_hash"] == report.corpus_hash
    assert summary["recall_at_3"] == round(tuning.recall, 4)
    return tuning.outcomes


def test_the_expected_chunk_is_in_the_top_three_for_every_labeled_query(
    outcomes: tuple[Outcome, ...],
) -> None:
    misses = [outcome.query.query for outcome in outcomes if outcome.query.doc_id and outcome.rank is None]

    assert misses == []


def test_the_tuned_threshold_keeps_every_hit_and_cuts_every_unrelated_question(
    outcomes: tuple[Outcome, ...],
) -> None:
    hits = [outcome.similarity for outcome in outcomes if outcome.similarity is not None]
    negatives = [outcome.top for outcome in outcomes if not outcome.query.doc_id and outcome.top is not None]

    cut = threshold(hits, negatives)

    assert all(hit >= cut for hit in hits)
    assert all(top < cut for top in negatives)


def test_queries_only_reach_their_country(tmp_path: Path) -> None:
    sample = corpus(tmp_path)
    build(sample.target, limits=SAMPLE_LIMITS, chunking=Chunking())
    retriever = VectorRetriever(local_embedder(sample.bedrock), local_index(sample.vectors))

    chunks = retriever.search("Quanto tempo leva a análise da minha contestação?", "PE", 8, {})

    assert chunks
    assert {chunk.country for chunk in chunks} == {"PE"}


def test_the_threshold_splits_overlapping_similarities_at_the_best_cut() -> None:
    assert threshold([0.8, 0.6, 0.5], [0.55, 0.3]) == 0.4
    assert threshold([0.8], []) == 0.8
    assert threshold([], [0.4]) == 1.0
