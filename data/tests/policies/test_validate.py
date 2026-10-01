from pathlib import Path

import pytest
from core.policies import policy_facts

from bankdata.policies.document import parse
from bankdata.policies.spec import SAMPLE_LIMITS, Limits
from bankdata.policies.validate import validate
from policies_harness import SAMPLE

GUIDE = "PE/pending_charges/pe-pending-charges.md"
VALID = sorted((SAMPLE / "valid").rglob("*.md"))


def problems(root: Path, key: str, limits: Limits = SAMPLE_LIMITS) -> list[tuple[str, int, str]]:
    found = validate(parse(key, (root / key).read_text(encoding="utf-8")), policy_facts(), limits)
    return [(problem.file, problem.line, problem.code) for problem in found]


@pytest.mark.parametrize("path", VALID, ids=[path.name for path in VALID])
def test_every_sample_document_is_valid(path: Path) -> None:
    root = SAMPLE / "valid"

    assert problems(root, path.relative_to(root).as_posix()) == []


@pytest.mark.parametrize(
    ("rule", "line", "code"),
    [
        ("frontmatter", 1, "frontmatter"),
        ("missing_section", 48, "structure"),
        ("section_length", 32, "section_length"),
        ("raw_figure", 30, "raw_figure"),
        ("raw_phone", 48, "raw_contact"),
        ("raw_url", 48, "raw_contact"),
        ("raw_date", 18, "raw_date"),
        ("number_word", 40, "number_word"),
        ("placeholder_unknown", 30, "placeholder_unknown"),
        ("placeholder_malformed", 30, "placeholder_malformed"),
        ("legal_disclaimer", 26, "legal_disclaimer"),
        ("forbidden_word", 22, "forbidden_word"),
        ("placeholder_heading", 22, "placeholder_heading"),
    ],
)
def test_each_invalid_fixture_fails_on_its_rule_naming_file_and_line(rule: str, line: int, code: str) -> None:
    root = SAMPLE / "invalid" / rule
    [path] = root.rglob("*.md")
    key = path.relative_to(root).as_posix()

    assert problems(root, key) == [(key, line, code)]


def test_articles_and_plain_words_pass_while_ordinals_do_not() -> None:
    text = (SAMPLE / "valid" / GUIDE).read_text(encoding="utf-8")
    assert "Una preautorización" in text
    assert "tu primera vez" in text

    second = parse(GUIDE, text.replace("tu primera vez", "tu segunda vez"))

    assert [problem.code for problem in validate(second, policy_facts(), SAMPLE_LIMITS)] == ["number_word"]


@pytest.mark.parametrize(
    ("key", "old", "new"),
    [
        (GUIDE, "escríbele a Clara desde la app", "escríbele a Clara si sospechas de terceros"),
        (
            "BR/transaction_statuses/br-transaction-statuses.md",
            "Confira a situação",
            "Segundo o banco, confira a situação para evitar uso por terceiros",
        ),
    ],
)
def test_exempt_words_pass(key: str, old: str, new: str) -> None:
    text = (SAMPLE / "valid" / key).read_text(encoding="utf-8")
    assert old in text

    assert validate(parse(key, text.replace(old, new)), policy_facts(), SAMPLE_LIMITS) == []


def test_the_production_limits_reject_the_short_sample_sections() -> None:
    codes = {code for _, _, code in problems(SAMPLE / "valid", GUIDE, Limits())}

    assert codes == {"section_length"}


def test_a_path_that_does_not_match_the_frontmatter_fails() -> None:
    text = (SAMPLE / "valid" / GUIDE).read_text(encoding="utf-8")

    found = validate(parse("BR/pending_charges/pe-pending-charges.md", text), policy_facts(), SAMPLE_LIMITS)

    assert [(problem.line, problem.code) for problem in found] == [(2, "frontmatter")]
