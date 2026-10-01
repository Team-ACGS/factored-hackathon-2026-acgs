import math
import tomllib
from pathlib import Path
from typing import Any

import pytest

import core
from core.tools.charges import FRESH_HOLD_DAYS

FACTS = tomllib.loads((Path(core.__file__).parent / "policy_facts.toml").read_text(encoding="utf-8"))
COUNTRIES = ("MX", "CO", "AR", "PE", "BR", "US")


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
def test_the_documented_hold_window_is_the_one_triage_applies(country: str) -> None:
    hold = FACTS[country]["holds"]["fresh_hold"]

    assert (hold["value"], hold["noun"]) == (FRESH_HOLD_DAYS, "day")
