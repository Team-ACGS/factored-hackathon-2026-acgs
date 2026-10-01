import math
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

import core
from core.facts import Ledger, render_value
from core.facts.values import Text
from core.policies import LANGUAGES, decode_figures, encode_figures, figure, policy_facts
from core.tools.charges import FRESH_HOLD_DAYS

FACTS = tomllib.loads((Path(core.__file__).parent / "policy_facts.toml").read_text(encoding="utf-8"))
COUNTRIES = ("MX", "CO", "AR", "PE", "BR", "US")
NOW = datetime(2026, 10, 1, 15, 0, tzinfo=UTC)


def _calendar_days(fact: dict[str, Any]) -> int:
    if fact["noun"] == "day":
        return int(fact["value"])
    assert fact["noun"] == "business_day"
    return math.ceil(int(fact["value"]) / 5) * 7


@pytest.mark.parametrize("country", COUNTRIES)
def test_the_bank_resolves_a_claim_after_assigning_and_reviewing_it(country: str) -> None:
    claims = {key: fact["value"] for key, fact in FACTS[country]["claims"].items() if fact["type"] == "count"}

    assert claims["resolution_time"] >= claims["assign_time"] + claims["review_time"]


@pytest.mark.parametrize("country", COUNTRIES)
def test_the_bank_resolves_a_claim_within_its_reading_of_the_norm(country: str) -> None:
    resolution = FACTS[country]["claims"]["resolution_time"]
    norm = FACTS[country]["legal"]["claim_response"]

    assert _calendar_days(resolution) <= _calendar_days(norm)


@pytest.mark.parametrize("country", COUNTRIES)
def test_an_express_replacement_arrives_before_a_regular_one(country: str) -> None:
    cards = FACTS[country]["cards"]

    assert cards["express_replacement_time"]["noun"] == cards["replacement_time"]["noun"] == "business_day"
    assert cards["express_replacement_time"]["value"] < cards["replacement_time"]["value"]


@pytest.mark.parametrize("country", COUNTRIES)
def test_the_documented_hold_window_is_the_one_triage_applies(country: str) -> None:
    hold = FACTS[country]["holds"]["fresh_hold"]

    assert (hold["value"], hold["noun"]) == (FRESH_HOLD_DAYS, "day")


def test_every_country_declares_the_same_keys_and_each_renders_in_its_language() -> None:
    countries = policy_facts()
    keys = set(countries["MX"].specs)

    for country, facts in countries.items():
        assert set(facts.specs) == keys
        assert facts.language == LANGUAGES[country]
        locale = facts.language if facts.language == "pt-BR" else facts.language[:2]
        for key in keys:
            assert render_value(facts.figure(key), Ledger(country, NOW), locale)


NAMES = ("authority.regulator", "authority.consumer_agency", "authority.norm_name", "service.ombudsman_name")


@pytest.mark.parametrize("country", COUNTRIES)
def test_every_country_names_its_authorities_in_plain_words(country: str) -> None:
    facts = policy_facts()[country]
    locale = facts.language if facts.language == "pt-BR" else facts.language[:2]

    for key in NAMES:
        name = facts.figure(key)
        assert isinstance(name, Text)
        assert render_value(name, Ledger(country, NOW), locale) == name.value
        assert not any(character.isdigit() for character in name.value)
        assert name.value.split()[0].lower() not in {"el", "la", "los", "las", "o", "a", "the"}


def test_only_legal_deadlines_are_unverified() -> None:
    facts = policy_facts()["AR"]

    assert {key for key in facts.specs if not facts.verified(key)} == {
        "legal.claim_response",
        "legal.report_window",
    }


def test_figures_survive_the_vector_metadata_round_trip() -> None:
    specs = policy_facts()["BR"].specs

    decoded = decode_figures(encode_figures(specs))

    assert {key: figure(spec) for key, spec in decoded.items()} == {
        key: figure(spec) for key, spec in specs.items()
    }
