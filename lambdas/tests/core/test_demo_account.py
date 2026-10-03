from datetime import UTC, datetime, timedelta

import pytest

from core.facts.values import Count, Flag, Ledger, Money, Ref
from core.tools import ToolContext, call
from crud.catalog import COUNTRIES
from harness import Aws, demo_account

NOW = datetime(2026, 10, 3, 15, 0, tzinfo=UTC)
CUSTOMER = "c0ffee00-0000-4000-8000-0000000000d1"
LANGUAGES = {"BR": "pt-BR", "US": "en"}


@pytest.mark.parametrize("country", sorted(COUNTRIES))
def test_a_fresh_demo_account_shows_its_balance_a_recurring_series_and_the_planted_claim(
    aws: Aws, country: str
) -> None:
    language = LANGUAGES.get(country, "es")
    account = demo_account(aws, CUSTOMER, country, language, NOW - timedelta(minutes=5))
    tools = ToolContext(CUSTOMER, country, language, NOW)
    ledger = Ledger(country, NOW)

    for card in account.cards:
        [fact_id] = call("card_status", {"card_ref": card["product_id"]}, tools, ledger).ids
        fields = ledger.facts[fact_id].fields
        assert fields["balance_available"] == Flag(True)
        assert isinstance(fields["current_balance"], Money)

    *_, series = call("recurring_charges", {}, tools, ledger).ids
    count = ledger.facts[series].fields["count"]
    assert isinstance(count, Count)
    assert count.value >= 1

    *cases, _ = call("case_status", {}, tools, ledger).ids
    assert account.claim is not None
    assert [ledger.facts[case_id].fields["case_ref"] for case_id in cases] == [
        Ref("case", account.claim["complaint_id"])
    ]
