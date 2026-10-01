from dataclasses import replace

import pytest
from core.policies import CountryFacts, policy_facts

from bankdata.policies.document import Document, parse
from bankdata.policies.spec import Limits
from bankdata.policies.validate import validate_all
from policies_harness import SOURCES

POLICY = "dispute-deadlines/es.md"
POLICY_PT = "dispute-deadlines/pt-BR.md"
POLICY_EN = "dispute-deadlines/en-US.md"
FAQ = "unrecognized-charges-faq/es.md"
FAQ_PT = "unrecognized-charges-faq/pt-BR.md"
FAQ_EN = "unrecognized-charges-faq/en-US.md"
KEYS = sorted(path.relative_to(SOURCES).as_posix() for path in SOURCES.rglob("*.md"))

Found = list[tuple[str, int, str]]


def original(key: str) -> str:
    return (SOURCES / key).read_text(encoding="utf-8")


def line(key: str, needle: str) -> int:
    [number] = [index for index, text in enumerate(original(key).splitlines(), 1) if needle in text]
    return number


def edit(key: str, old: str, new: str) -> dict[str, str]:
    text = original(key)
    assert text.count(old) == 1, old
    return {key: text.replace(old, new)}


def sources(changes: dict[str, str], without: tuple[str, ...] = ()) -> list[Document]:
    return [parse(key, changes.get(key) or original(key)) for key in KEYS if key not in without]


def problems(
    changes: dict[str, str] | None = None,
    facts: dict[str, CountryFacts] | None = None,
    without: tuple[str, ...] = (),
) -> Found:
    found = validate_all(sources(changes or {}, without), facts or policy_facts(), Limits())
    return [(problem.file, problem.line, problem.code) for key in KEYS for problem in found.get(key, [])]


def messages(changes: dict[str, str], without: tuple[str, ...] = ()) -> list[str]:
    found = validate_all(sources(changes, without), policy_facts(), Limits())
    return [str(problem) for listed in found.values() for problem in listed]


def test_every_sample_file_is_valid_under_the_production_limits() -> None:
    assert len(KEYS) == 6
    assert problems() == []


@pytest.mark.parametrize(
    ("key", "old", "new", "code"),
    [
        (POLICY, "nunca supera el máximo legal", "nunca supera los 45 días", "raw_figure"),
        (POLICY, "Tampoco aplica", "Llame al 555 123 4567. Tampoco aplica", "raw_contact"),
        (POLICY, "Este resumen no", "Este resumen, en latambank.com, no", "raw_contact"),
        (POLICY, "no cuentan fines de semana", "no cuentan el domingo", "raw_date"),
        (POLICY, "Cada aclaración cubre un cargo", "Cada aclaración cubre dos cargos", "number_word"),
        (POLICY, "que no hizo la compra", "que no hubo fraude", "forbidden_word"),
        (
            POLICY,
            "para objetar un cargo, según la lectura que hace el banco de la norma aplicable.",
            "para objetar un cargo.",
            "legal_disclaimer",
        ),
        (POLICY, "Usted puede reportar", "Tú puedes reportar", "register"),
        (FAQ, "Clara le ayuda a revisarlo", "Clara te ayuda a revisarlo", "register"),
        (FAQ_PT, "Se alguém da sua família", "Se alguém da tua família", "register"),
        (POLICY, "El banco sigue las reglas", "El banco sigue las reglas de la CNBV y", "literal_name"),
        (
            POLICY,
            "Usted conserva sus derechos",
            "Todo cliente mexicano conserva sus derechos",
            "literal_name",
        ),
        (
            POLICY,
            "a la defensoría del banco, {{",
            "a la Defensoría del Cliente de LATAM Bank, {{",
            "literal_name",
        ),
        (POLICY_PT, "O banco segue as regras", "No Brasil, o banco segue as regras", "literal_name"),
        (POLICY_PT, "ou o órgão de defesa", "ou o Procon", "literal_name"),
        (POLICY_EN, "This summary does not", "This summary of U.S. law does not", "literal_name"),
        (POLICY_EN, "the consumer protection agency at any time", "the CFPB at any time", "literal_name"),
        (FAQ_EN, "Many companies charge", "Many Brazilian companies charge", "literal_name"),
        (POLICY_EN, "Deadlines in business days", "US deadlines in business days", "literal_name"),
        (POLICY, "title: Plazos de respuesta", "title: Plazos en Perú de respuesta", "literal_name"),
    ],
)
def test_each_rule_fails_naming_file_and_line(key: str, old: str, new: str, code: str) -> None:
    at = line(key, old)

    assert problems(edit(key, old, new)) == [(key, at, code)]


@pytest.mark.parametrize(
    ("new", "code"),
    [
        ("{{policy.claims.assignment_time}}", "placeholder_unknown"),
        ("{{ policy.claims.assign_time }}", "placeholder_malformed"),
    ],
)
def test_a_bad_placeholder_fails_its_file_and_the_parity_of_the_others(new: str, code: str) -> None:
    old = "{{policy.claims.assign_time}}"

    found = problems(edit(POLICY, old, new))

    assert [item for item in found if item[0] == POLICY] == [(POLICY, line(POLICY, old), code)]
    assert {(file, rule) for file, _, rule in found if file != POLICY} == {
        (POLICY_PT, "parity"),
        (POLICY_EN, "parity"),
    }


def test_a_placeholder_in_a_heading_fails() -> None:
    old = "### ¿Hasta cuándo puedo reportar un cargo?"
    new = "### ¿Puedo reportar un cargo después de {{policy.claims.report_window}}?"

    found = problems(edit(FAQ, old, new))

    assert [item for item in found if item[0] == FAQ] == [(FAQ, line(FAQ, old), "placeholder_heading")]


def test_a_missing_frontmatter_field_fails_at_the_top() -> None:
    assert problems(edit(POLICY, "topic: dispute_deadlines\n", "")) == [(POLICY, 1, "frontmatter")]


def test_a_path_that_does_not_match_the_frontmatter_fails() -> None:
    document = parse("dispute-lifecycle/es.md", original(POLICY))

    found = validate_all([document], policy_facts(), Limits())["dispute-lifecycle/es.md"]

    assert [(problem.line, problem.code) for problem in found if problem.code != "parity"] == [
        (2, "frontmatter")
    ]


def test_a_placeholder_missing_for_one_country_names_file_line_and_country() -> None:
    facts = policy_facts()
    colombia = facts["CO"]
    specs = {key: spec for key, spec in colombia.specs.items() if key != "claims.assign_time"}
    changed = {**facts, "CO": replace(colombia, specs=specs)}

    found = validate_all(sources({}), changed, Limits())

    [problem] = [problem for listed in found.values() for problem in listed]
    assert (problem.file, problem.line, problem.code) == (
        POLICY,
        line(POLICY, "{{policy.claims.assign_time}}"),
        "placeholder_unknown",
    )
    assert problem.message.endswith("is not a key of CO")


def test_the_bank_and_the_assistant_names_and_a_lowercase_us_pass() -> None:
    changes = {
        **edit(
            FAQ, "Si tiene dudas, Clara puede", "Si tiene dudas, Clara, la asistente de LATAM Bank, puede"
        ),
        **edit(FAQ_EN, "Clara helps you review it", "Clara and LATAM Bank help us review it"),
    }

    assert problems(changes) == []


def test_removing_a_section_from_one_language_fails_parity_naming_document_section_and_language() -> None:
    text = original(POLICY_PT)
    start, end = text.index("## Exceções"), text.index("## Prazos")
    changed = text[:start] + text[end:]

    found = [message for message in messages({POLICY_PT: changed}) if ": parity: " in message]

    assert found[-1] == (
        f"{POLICY_PT}:{changed.count(chr(10)) + 1}: parity: "
        "document dispute-deadlines: section 10 'Marco regulatorio' of es is missing in pt-BR"
    )
    assert found[0].startswith(
        f"{POLICY_PT}:{line(POLICY_PT, '## Exceções')}: parity: "
        "document dispute-deadlines: section 8 of pt-BR differs from es: "
        "missing transactions.duplicate_review"
    )


def test_removing_a_placeholder_from_one_language_fails_parity() -> None:
    changes = edit(FAQ_EN, "or to {{policy.channels.email}}.", "or by email.")

    found = validate_all(sources(changes), policy_facts(), Limits())

    [problem] = [problem for listed in found.values() for problem in listed]
    assert (problem.file, problem.line, problem.code) == (
        FAQ_EN,
        line(FAQ_EN, "## During the review"),
        "parity",
    )
    assert problem.message == (
        "document unrecognized-charges-faq: section 3 of en-US differs from es: missing channels.email"
    )


def test_a_missing_language_file_fails_parity_naming_the_document_and_the_language() -> None:
    found = messages({}, without=(FAQ_EN,))

    assert found == [f"{FAQ}:1: parity: document unrecognized-charges-faq has no en-US file"]


def test_a_shared_field_that_differs_across_languages_fails_parity() -> None:
    assert problems(edit(POLICY_EN, "version: 1", "version: 2")) == [(POLICY_EN, 7, "parity")]


def test_a_section_outside_sixty_to_two_hundred_fifty_words_fails() -> None:
    sentence = " El banco revisa cada movimiento con cuidado."
    short = edit(
        POLICY,
        "Cuando eso ocurre, el banco le explica el motivo y le indica la nueva fecha estimada "
        "antes de que venza el plazo original.\n",
        "",
    )
    long = edit(
        POLICY,
        "sin importar el monto del cargo ni el canal por el que llegó.",
        f"sin importar el monto.{sentence * 24}",
    )

    assert problems(short) == [(POLICY, line(POLICY, "## Excepciones"), "section_length")]
    assert problems(long) == [(POLICY, line(POLICY, "## Propósito"), "section_length")]


def test_a_document_outside_six_hundred_to_one_thousand_fifty_words_fails() -> None:
    padding = (
        "El banco revisa cada caso con cuidado, le explica cada paso con claridad "
        "y le avisa por la app cuando algo cambia en su aclaración."
    )
    text = original(POLICY).replace(".\n\n## ", f".\n{padding}\n\n## ")

    found = problems({POLICY: text})

    assert found == [(POLICY, line(POLICY, "## Propósito"), "document_length")]
