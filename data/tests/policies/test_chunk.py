import re

from core.policies import policy_facts

from bankdata.policies.chunk import Chunking, chunk_document, oversized
from bankdata.policies.dedupe import Candidate, dedupe
from bankdata.policies.document import expand, parse
from bankdata.policies.render import RenderedDocument, render
from policies_harness import SOURCES

DIGIT = re.compile(r"\d")
LIST_MARKER = re.compile(r"^\s*\d+\.\s", re.MULTILINE)
KEYS = sorted(path.relative_to(SOURCES).as_posix() for path in SOURCES.rglob("*.md"))


def editions(key: str, text: str | None = None) -> list[RenderedDocument]:
    source = parse(key, text or (SOURCES / key).read_text(encoding="utf-8"))
    return [render(edition, policy_facts()[edition.country]) for edition in expand(source)]


def test_a_base_file_expands_into_one_edition_per_country_of_its_language() -> None:
    found = {key: [(document.country, document.doc_id) for document in editions(key)] for key in KEYS}

    assert found["dispute-deadlines/es.md"] == [
        ("MX", "mx-dispute-deadlines"),
        ("CO", "co-dispute-deadlines"),
        ("AR", "ar-dispute-deadlines"),
        ("PE", "pe-dispute-deadlines"),
    ]
    assert found["dispute-deadlines/pt-BR.md"] == [("BR", "br-dispute-deadlines")]
    assert found["unrecognized-charges-faq/en-US.md"] == [("US", "us-unrecognized-charges-faq")]
    assert [document.language for document in editions("dispute-deadlines/es.md")] == [
        "es-MX",
        "es-CO",
        "es-AR",
        "es-PE",
    ]


def test_each_section_becomes_one_chunk() -> None:
    for key in KEYS:
        for document in editions(key):
            chunks = chunk_document(document)

            assert [(chunk.section, chunk.number) for chunk in chunks] == [
                (section.number, 1) for section in document.sections
            ]
            assert [chunk.text for chunk in chunks] == [section.text.strip() for section in document.sections]
            assert oversized(document, Chunking()) == []


def test_a_section_too_long_to_embed_fails_with_file_line_and_country() -> None:
    key = "dispute-deadlines/es.md"
    text = (SOURCES / key).read_text(encoding="utf-8")
    words = " ".join(["administración"] * 240)
    long = text.replace("Este resumen no reemplaza la norma ni cita sus artículos.", words)
    line = text.splitlines().index("## Marco regulatorio") + 1

    found = [problem for document in editions(key, long) for problem in oversized(document, Chunking())]

    assert [(problem.file, problem.line, problem.code) for problem in found] == [
        (key, line, "chunk_length")
    ] * 4
    assert [problem.message.split(" in ")[1].split()[0] for problem in found] == ["MX", "CO", "AR", "PE"]


def test_one_text_renders_each_country_its_own_figures_and_names() -> None:
    [mexico, colombia, argentina, peru] = editions("dispute-deadlines/es.md")
    regulatory = [document.sections[9] for document in (mexico, colombia, argentina, peru)]

    assert "(Comisión Nacional Bancaria y de Valores)" in regulatory[0].text
    assert "(Banco Central de la República Argentina)" in regulatory[2].text
    assert "(Reglamento de Tarjetas de Crédito y Débito)" in regulatory[3].text
    assert "10 días hábiles" in mexico.sections[6].text
    assert "8 días hábiles" in argentina.sections[6].text
    chunk = chunk_document(colombia)[9]
    figures = colombia.figures(chunk.start, chunk.end, colombia.sections[9])
    assert figures["authority.regulator"] == {
        "type": "name",
        "value": "Superintendencia Financiera de Colombia",
    }


def test_every_rendered_figure_of_a_chunk_is_in_its_figures_map() -> None:
    for key in KEYS:
        for document in editions(key):
            for chunk in chunk_document(document):
                section = document.sections[chunk.section - 1]
                figures = document.figures(chunk.start, chunk.end, section)
                text = section.text
                for span in section.spans:
                    assert span.key in figures
                    text = text[: span.start] + " " * (span.end - span.start) + text[span.end :]
                assert not DIGIT.search(LIST_MARKER.sub("", text[chunk.start : chunk.end])), (key, chunk)


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
