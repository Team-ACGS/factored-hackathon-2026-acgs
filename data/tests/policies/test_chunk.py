import re
from itertools import pairwise

from core.policies import policy_facts

from bankdata.policies.chunk import Chunking, chunk_document, chunk_section, estimate_tokens
from bankdata.policies.dedupe import Candidate, dedupe
from bankdata.policies.document import parse
from bankdata.policies.render import RenderedDocument, RenderedSection, render
from policies_harness import SAMPLE

SMALL = Chunking(min_tokens=20, max_tokens=60, overlap=0.15)
DIGIT = re.compile(r"\d")
LIST_MARKER = re.compile(r"^\s*\d+\.\s", re.MULTILINE)


def sample(key: str) -> RenderedDocument:
    document = parse(key, (SAMPLE / "valid" / key).read_text(encoding="utf-8"))
    return render(document, policy_facts()[key[:2]])


def guide() -> RenderedDocument:
    return sample("PE/pending_charges/pe-pending-charges.md")


def test_chunks_stay_inside_their_section_and_are_deterministic() -> None:
    document = guide()

    chunks = chunk_document(document, SMALL)

    assert chunks == chunk_document(guide(), SMALL)
    for chunk in chunks:
        section = document.sections[chunk.section - 1]
        assert section.text[chunk.start : chunk.end] == chunk.text
    assert {chunk.section for chunk in chunks} == {section.number for section in document.sections}


def test_consecutive_chunks_overlap_by_about_fifteen_percent() -> None:
    document = guide()
    section = document.sections[6]

    chunks = chunk_section(section, SMALL)

    assert len(chunks) > 2
    for previous, following in pairwise(chunks):
        overlap = previous.end - following.start
        assert 0 < overlap <= 0.15 * (previous.end - previous.start)
        assert estimate_tokens(previous.text) <= SMALL.max_tokens


def test_production_chunks_hold_three_to_four_hundred_fifty_tokens() -> None:
    sentence = "El banco revisa cada movimiento con cuidado y te explica lo que encontró en tu caso. "
    section = RenderedSection(1, "Reglas", (sentence * 60).strip(), ())

    chunks = chunk_section(section, Chunking())

    assert len(chunks) > 3
    assert all(300 <= estimate_tokens(chunk.text) <= 450 for chunk in chunks[:-1])
    assert all(estimate_tokens(chunk.text) <= 450 for chunk in chunks)
    assert all(previous.end > following.start for previous, following in pairwise(chunks))


def test_every_rendered_figure_of_a_chunk_is_in_its_figures_map() -> None:
    for key in ("PE/pending_charges/pe-pending-charges.md", "PE/dispute_lifecycle/pe-dispute-lifecycle.md"):
        document = sample(key)
        for chunk in chunk_document(document, SMALL):
            section = document.sections[chunk.section - 1]
            figures = document.figures(chunk.start, chunk.end, section)
            text = section.text
            for span in section.spans:
                if span.start < chunk.end and span.end > chunk.start:
                    assert span.key in figures
                    text = text[: span.start] + " " * (span.end - span.start) + text[span.end :]
            assert not DIGIT.search(LIST_MARKER.sub("", text[chunk.start : chunk.end])), (key, chunk)


def test_a_figure_renders_from_the_country_facts() -> None:
    document = guide()

    times = document.sections[4]

    assert "10 días" in times.text
    assert {span.key for span in times.spans} == {
        "holds.preauth_hotel",
        "holds.preauth_fuel",
        "holds.preauth_car_rental",
    }


def test_dedupe_drops_exact_and_near_duplicates_within_a_country() -> None:
    text = " ".join(f"palabra{index}" for index in range(40))
    near = text.replace("palabra39", "otra")
    candidates = [
        Candidate("pe-a-v1-f1-s1-c1", "PE", "card_blocking", text),
        Candidate("pe-b-v1-f1-s1-c1", "PE", "card_replacement", text.upper()),
        Candidate("br-a-v1-f1-s1-c1", "BR", "card_blocking", text),
        Candidate("pe-a-v1-f1-s2-c1", "PE", "card_blocking", near),
        Candidate("pe-c-v1-f1-s1-c1", "PE", "pending_charges", text.replace("palabra0", "otra")),
    ]

    assert dedupe(candidates) == {
        "pe-b-v1-f1-s1-c1": "pe-a-v1-f1-s1-c1",
        "pe-a-v1-f1-s2-c1": "pe-a-v1-f1-s1-c1",
    }
