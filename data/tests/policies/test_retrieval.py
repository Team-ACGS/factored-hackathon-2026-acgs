import json
from pathlib import Path

import pytest
from clara_testing import MODEL_ID, local_embedder, local_index
from core.retrieval import VectorRetriever

from bankdata.policies.build import build
from bankdata.policies.chunk import Chunking
from bankdata.policies.tune import Answer, LabeledQuery, Tuning, load_queries, threshold, tune
from policies_harness import SAMPLE, corpus

QUERIES = load_queries(SAMPLE / "queries.toml")


@pytest.fixture(scope="module")
def tuning(tmp_path_factory: pytest.TempPathFactory) -> Tuning:
    sample = corpus(tmp_path_factory.mktemp("retrieval"))
    build(sample.target, chunking=Chunking())
    retriever = VectorRetriever(local_embedder(sample.bedrock), local_index(sample.vectors))
    return tune(retriever, QUERIES, "hash", MODEL_ID)


def test_an_accepted_answer_is_in_the_top_three_for_every_labeled_query(tuning: Tuning) -> None:
    misses = [
        outcome.query.query for outcome in tuning.outcomes if outcome.query.answerable and not outcome.hit()
    ]

    assert misses == []
    assert json.loads(tuning.to_json())["overall"]["recall_at_3"] == 1.0


def test_each_language_gets_a_cut_that_keeps_its_hits_and_cuts_its_unrelated_questions(
    tuning: Tuning,
) -> None:
    for language, cut in tuning.thresholds.items():
        outcomes = tuning.measured(language)
        hits = [outcome.similarity for outcome in outcomes if outcome.similarity is not None]
        tops = [
            outcome.top for outcome in outcomes if not outcome.query.answerable and outcome.top is not None
        ]

        assert hits, language
        assert all(hit >= cut for hit in hits), language
        assert all(top < cut for top in tops), language


def test_the_summary_reports_recall_per_language_at_three_and_at_the_tools_k(tuning: Tuning) -> None:
    summary = json.loads(tuning.to_json())

    assert set(summary["languages"]) == {"es", "pt", "en"}
    assert summary["thresholds"] == dict(tuning.thresholds)
    for block in summary["languages"].values():
        assert {"recall_at_3", "recall_at_4", "answered", "hits_passing", "unrelated_passing"} <= set(block)
    assert summary["near_duplicates"] == 0


def test_any_accepted_answer_counts_as_a_hit(tmp_path: Path) -> None:
    sample = corpus(tmp_path)
    build(sample.target, chunking=Chunking())
    retriever = VectorRetriever(local_embedder(sample.bedrock), local_index(sample.vectors))
    query = "¿Cuánto tarda la revisión de mi aclaración?"
    returned = retriever.search(query, "PE", 4, {})
    second = returned[1]
    section = int(second.chunk_id.split("-s")[-1].split("-c")[0])

    only_second = LabeledQuery("PE", query, (Answer(second.doc_id, section),))
    neither = LabeledQuery("PE", query, (Answer("pe-unrecognized-charges-faq", 99),))
    outcomes = tune(retriever, [only_second, neither], "hash", MODEL_ID).outcomes

    assert outcomes[0].rank == 2
    assert outcomes[1].rank is None


def test_cross_language_questions_are_reported_but_never_set_a_cut(tmp_path: Path) -> None:
    sample = corpus(tmp_path)
    build(sample.target, chunking=Chunking())
    retriever = VectorRetriever(local_embedder(sample.bedrock), local_index(sample.vectors))
    english = LabeledQuery("PE", "What is the best mortgage rate this year?", (), "en")
    spanish = [query for query in QUERIES if query.document_language == "es"]

    with_cross = tune(retriever, [*spanish, english], "hash", MODEL_ID)
    without = tune(retriever, spanish, "hash", MODEL_ID)

    assert with_cross.thresholds["es"] == without.thresholds["es"]
    assert json.loads(with_cross.to_json())["cross_language"]["queries"] == 1
    assert english.cross_language
    assert not LabeledQuery("PE", "x", (), "es").cross_language


def test_queries_only_reach_their_country(tmp_path: Path) -> None:
    sample = corpus(tmp_path)
    build(sample.target, chunking=Chunking())
    retriever = VectorRetriever(local_embedder(sample.bedrock), local_index(sample.vectors))

    chunks = retriever.search("Quanto tempo leva a análise da minha contestação?", "PE", 8, {})

    assert chunks
    assert {chunk.country for chunk in chunks} == {"PE"}


def test_the_cut_is_the_best_split_that_lets_at_most_one_in_ten_unrelated_questions_through() -> None:
    hits = [0.8, 0.7, 0.6, 0.5]
    negatives = [0.65, 0.55, 0.3, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2]

    assert threshold(hits, negatives) == 0.575
    assert threshold(hits, negatives, max_rate=0.2) == 0.4
    assert threshold([0.8, 0.6, 0.5], [0.55, 0.3]) == 0.575
    assert threshold([0.8], []) == 0.8
    assert threshold([], [0.4]) == 1.0
    assert threshold([0.4], [0.9]) == 0.95
