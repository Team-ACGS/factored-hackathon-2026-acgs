import json
import re
from dataclasses import replace
from pathlib import Path

import pymupdf
import pytest
from botocore.exceptions import ClientError
from core.facts.check import fold
from core.policies import CountryFacts, decode_figures, policy_facts

from bankdata.policies.build import MANIFEST_KEY, Report, build
from bankdata.policies.chunk import Chunking
from policies_harness import DOMAIN, Corpus, corpus

DEADLINES = "dispute-deadlines/es.md"
FAQ = "unrecognized-charges-faq/en-US.md"
EDITIONS = ("mx", "co", "ar", "pe", "br", "us")
DEADLINES_EDITIONS = sorted(f"{country}-dispute-deadlines" for country in EDITIONS)
FAQ_EDITIONS = sorted(f"{country}-unrecognized-charges-faq" for country in EDITIONS)
NOT_SPANISH = ["br-dispute-deadlines", "us-dispute-deadlines"]
NON_WORD = re.compile(r"[^a-z0-9]+")


def run(sample: Corpus, facts: dict[str, CountryFacts] | None = None, prune: bool = True) -> Report:
    return build(sample.target, facts=facts, chunking=Chunking(), prune=prune)


def manifest(sample: Corpus) -> dict[str, object]:
    data = sample.policies.read(MANIFEST_KEY)
    assert data is not None
    loaded: dict[str, object] = json.loads(data)
    return loaded


def entry(sample: Corpus, doc_id: str) -> dict[str, object]:
    documents = manifest(sample)["documents"]
    assert isinstance(documents, dict)
    found: dict[str, object] = documents[doc_id]
    return found


@pytest.fixture
def sample(tmp_path: Path) -> Corpus:
    return corpus(tmp_path)


def test_the_first_build_publishes_one_edition_per_country_in_the_0013_form(sample: Corpus) -> None:
    report = run(sample)

    assert report.problems == []
    assert len(report.built) == 12
    assert report.embedded == report.written == len(sample.vectors.vectors) == 6 * 10 + 6 * 4
    deadlines = entry(sample, "pe-dispute-deadlines")
    assert deadlines["pdf_url"] == f"https://{DOMAIN}/PE/pe-dispute-deadlines-v1-f2.pdf"
    assert deadlines["source_key"] == DEADLINES
    assert sample.documents.read("PE/pe-dispute-deadlines-v1-f2.pdf")
    assert sample.documents.read("US/us-unrecognized-charges-faq-v1-f2.pdf")
    assert sample.policies.read("rendered/MX/mx-dispute-deadlines-v1-f2.md")
    assert "pe-dispute-deadlines-v1-f2-s9-c1" in sample.vectors.vectors
    assert "br-unrecognized-charges-faq-v1-f2-s4-c1" in sample.vectors.vectors
    metadata = sample.vectors.vectors["co-dispute-deadlines-v1-f2-s10-c1"][1]
    assert (metadata["country"], metadata["language"], metadata["doc_id"]) == (
        "CO",
        "es-CO",
        "co-dispute-deadlines",
    )
    assert {call["input_type"] for call in sample.bedrock.calls} == {"search_document"}


def test_a_second_run_is_identical_and_writes_nothing(sample: Corpus, tmp_path: Path) -> None:
    first = run(sample)
    before = sample.policies.read(MANIFEST_KEY)
    keys = set(sample.vectors.vectors)
    sample.bedrock.calls.clear()
    sample.policies.writes.clear()
    sample.documents.writes.clear()
    writes = sample.vectors.writes

    second = run(sample)

    assert second.corpus_hash == first.corpus_hash
    assert second.built == []
    assert second.embedded == 0
    assert sample.vectors.writes == writes
    assert sample.vectors.deletes == 0
    assert sample.bedrock.calls == []
    assert sample.policies.writes == []
    assert sample.documents.writes == []
    assert set(sample.vectors.vectors) == keys
    fresh = corpus(tmp_path / "fresh")
    run(fresh)
    assert fresh.policies.read(MANIFEST_KEY) == before
    assert set(fresh.vectors.vectors) == keys


def test_a_new_facts_value_with_a_new_facts_version_rebuilds_the_country(sample: Corpus) -> None:
    run(sample)
    facts = policy_facts()
    peru = facts["PE"]
    review = {"type": "count", "value": 12, "noun": "business_day"}
    changed = {**facts, "PE": replace(peru, version=3, specs={**peru.specs, "claims.review_time": review})}

    report = run(sample, changed)

    assert report.problems == []
    assert sorted(report.built) == ["pe-dispute-deadlines", "pe-unrecognized-charges-faq"]
    old, new = "pe-dispute-deadlines-v1-f2-s7-c1", "pe-dispute-deadlines-v1-f3-s7-c1"
    assert old not in sample.vectors.vectors
    metadata = sample.vectors.vectors[new][1]
    assert "12 días hábiles" in metadata["text"]
    assert decode_figures(metadata["figures"])["claims.review_time"] == review
    assert "10 días hábiles" in sample.vectors.vectors["mx-dispute-deadlines-v1-f2-s7-c1"][1]["text"]
    assert sample.documents.read("PE/pe-dispute-deadlines-v1-f2.pdf")


def test_a_facts_value_changed_without_a_new_version_fails_the_country(sample: Corpus) -> None:
    run(sample)
    facts = policy_facts()
    peru = facts["PE"]
    review = {"type": "count", "value": 12, "noun": "business_day"}
    changed = {**facts, "PE": replace(peru, specs={**peru.specs, "claims.review_time": review})}

    report = run(sample, changed)

    assert {problem.code for problem in report.problems} == {"facts_version"}
    assert {problem.file for problem in report.problems} == {
        "lambdas/core/src/core/policy_facts.toml",
        DEADLINES,
        "unrecognized-charges-faq/es.md",
    }
    assert report.built == []
    assert "pe-dispute-deadlines-v1-f2-s7-c1" in sample.vectors.vectors


def bump(sample: Corpus, document: str, old: str | None = None, new: str = "") -> None:
    for path in sample.source(document).iterdir():
        text = path.read_text(encoding="utf-8").replace("version: 1", "version: 2")
        path.write_text(text.replace(old, new) if old and path.name == "es.md" else text, encoding="utf-8")


def test_a_new_document_version_replaces_its_vectors_and_keeps_the_old_pdf(sample: Corpus) -> None:
    run(sample)
    bump(sample, "dispute-deadlines", "en cualquier momento", "cuando lo necesite")

    report = run(sample)

    assert report.problems == []
    assert sorted(report.built) == DEADLINES_EDITIONS
    assert not any("dispute-deadlines-v1-" in key for key in sample.vectors.vectors)
    assert "mx-dispute-deadlines-v2-f2-s10-c1" in sample.vectors.vectors
    assert sample.documents.read("MX/mx-dispute-deadlines-v1-f2.pdf")
    assert sample.documents.read("MX/mx-dispute-deadlines-v2-f2.pdf")


def test_a_changed_text_without_a_new_version_fails_every_edition_and_keeps_the_published_ones(
    sample: Corpus,
) -> None:
    run(sample)
    path = sample.source(DEADLINES)
    path.write_text(path.read_text(encoding="utf-8").replace("en cualquier momento", "ya"), encoding="utf-8")

    report = run(sample)

    assert [(problem.file, problem.code) for problem in report.problems] == [(DEADLINES, "version")]
    assert report.built == []
    assert sorted(report.skipped) == sorted([*FAQ_EDITIONS, *NOT_SPANISH])
    assert entry(sample, "pe-dispute-deadlines")["version"] == 1
    assert "pe-dispute-deadlines-v1-f2-s10-c1" in sample.vectors.vectors


def test_an_invalid_base_file_fails_its_editions_alone(sample: Corpus) -> None:
    path = sample.source(DEADLINES)
    path.write_text(path.read_text(encoding="utf-8").replace("que no hizo la compra", "que no hubo fraude"))

    report = run(sample)

    assert [(problem.file, problem.code) for problem in report.problems] == [(DEADLINES, "forbidden_word")]
    assert sorted(report.built) == sorted([*FAQ_EDITIONS, *NOT_SPANISH])


def test_a_parity_failure_fails_every_edition_of_the_document(sample: Corpus) -> None:
    path = sample.source(FAQ)
    path.write_text(
        path.read_text(encoding="utf-8").replace("or to {{policy.channels.email}}.", "or by email.")
    )

    report = run(sample)

    assert [(problem.file, problem.code) for problem in report.problems] == [(FAQ, "parity")]
    assert sorted(report.built) == DEADLINES_EDITIONS


def test_a_removed_document_loses_its_vectors_but_not_its_pdfs(sample: Corpus) -> None:
    run(sample)
    for path in sample.source("dispute-deadlines").iterdir():
        path.unlink()

    report = run(sample)

    assert sorted(report.removed) == DEADLINES_EDITIONS
    assert not any("dispute-deadlines" in key for key in sample.vectors.vectors)
    assert sample.documents.read("PE/pe-dispute-deadlines-v1-f2.pdf")
    documents = manifest(sample)["documents"]
    assert isinstance(documents, dict)
    assert len(documents) == 6


def test_a_folder_build_keeps_the_published_documents_it_does_not_hold(sample: Corpus) -> None:
    run(sample)
    for path in sample.source("dispute-deadlines").iterdir():
        path.unlink()

    report = run(sample, prune=False)

    assert report.removed == []
    assert "pe-dispute-deadlines-v1-f2-s9-c1" in sample.vectors.vectors
    assert entry(sample, "pe-dispute-deadlines")["version"] == 1


def test_a_build_that_stops_midway_resumes_where_it_stopped(sample: Corpus) -> None:
    sample.bedrock.fail_on_call = 4

    with pytest.raises(ClientError):
        run(sample)

    done = manifest(sample)["documents"]
    assert isinstance(done, dict)
    assert len(done) == 3
    sample.bedrock.fail_on_call = None
    sample.bedrock.calls.clear()

    report = run(sample)

    assert sorted(report.skipped) == sorted(done)
    assert len(report.built) == 9
    assert len(sample.bedrock.calls) == 9
    assert report.embedded == sum(report.chunks_per_document[doc_id] for doc_id in report.built)


def plain(text: str) -> str:
    return " ".join(
        NON_WORD.sub(" ", fold(re.sub(r"(\*\*|^#+\s|^\s*\d+\.\s|^-\s)", " ", text, flags=re.M))).split()
    )


def test_every_chunk_page_holds_its_opening_words(sample: Corpus) -> None:
    run(sample)

    for key, (_, metadata) in sample.vectors.vectors.items():
        pdf = sample.documents.read(metadata["url"].removeprefix(f"https://{DOMAIN}/"))
        assert pdf is not None
        with pymupdf.open(stream=pdf, filetype="pdf") as document:
            page = plain(document[int(metadata["page_start"]) - 1].get_text())
        opening = " ".join(plain(metadata["text"]).split()[:3])
        assert opening in page, key
        assert int(metadata["page_start"]) >= 2
