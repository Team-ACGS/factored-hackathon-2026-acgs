import random
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from core.ids import parse_uuid7, uuid7_time
from crud.catalog import COUNTRIES, SUSPICIOUS_POOL
from crud.generator import CaseKind, Claim, Score, generate, manual_transaction
from harness import uuid7

ANCHOR = datetime(2026, 9, 28, 15, 30, tzinfo=UTC)


def claim(country: str = "MX", customer_id: str = "customer-1", anchor: datetime = ANCHOR) -> Claim:
    return Claim(customer_id=customer_id, country=COUNTRIES[country], anchor=anchor)


def when(item: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(item["transaction_date"])


def by_card(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    cards: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        cards[item["product_id"]].append(item)
    return cards


@pytest.mark.parametrize("country", sorted(COUNTRIES))
def test_an_account_has_two_credit_cards_and_one_debit_card_in_the_country_currency(country: str) -> None:
    account = generate(claim(country))

    assert [card["product_type"] for card in account.cards] == [
        "Tarjeta Crédito",
        "Tarjeta Crédito",
        "Tarjeta Débito",
    ]
    currency = COUNTRIES[country].currency
    assert {card["currency"] for card in account.cards} == {currency}
    assert {item["currency"] for item in account.transactions} == {currency}
    assert {item["transaction_country"] for item in account.transactions} == {country}
    for card in account.cards[:2]:
        assert Decimal(0) < card["current_balance"] < card["credit_limit"]
    assert "credit_limit" not in account.cards[2]


@pytest.mark.parametrize("country", sorted(COUNTRIES))
def test_each_card_has_one_hundred_transactions_over_the_last_three_months(country: str) -> None:
    account = generate(claim(country))

    cards = by_card(account.transactions)
    assert sorted(cards) == sorted(card["product_id"] for card in account.cards)
    assert [len(items) for items in cards.values()] == [100, 100, 100]
    assert all(ANCHOR - timedelta(days=90) < when(item) < ANCHOR for item in account.transactions)
    assert len({item["transaction_key"] for item in account.transactions}) == 300


@pytest.mark.parametrize("country", sorted(COUNTRIES))
def test_every_merchant_of_the_country_has_at_least_four_transactions(country: str) -> None:
    account = generate(claim(country))

    counts = Counter(item["merchant_name"] for item in account.transactions)
    assert set(counts) == {merchant.name for merchant in COUNTRIES[country].merchants}
    assert min(counts.values()) >= 4


def test_each_card_follows_the_dataset_status_mix() -> None:
    account = generate(claim())

    for items in by_card(account.transactions).values():
        assert Counter(item["transaction_status"] for item in items) == {
            "Approved": 92,
            "Declined": 5,
            "Pending": 2,
            "Reversed": 1,
        }


def test_response_codes_follow_the_status() -> None:
    account = generate(claim())

    for item in account.transactions:
        if item["transaction_status"] in ("Approved", "Reversed"):
            assert item["response_code"] == "00"
        else:
            assert item["response_code"] in {"05", "14", "51", "54"}


@pytest.mark.parametrize("customer_id", ["customer-1", "customer-2", "customer-3", "customer-4"])
def test_the_three_explainable_cases_are_planted_and_the_fresh_hold_is_the_only_fresh_pending(
    customer_id: str,
) -> None:
    account = generate(claim(customer_id=customer_id))

    cases = dict(account.cases)
    assert list(cases) == [CaseKind.FRESH_HOLD, CaseKind.REVERSED_CHARGE, CaseKind.STALE_PENDING]
    fresh, reversed_charge, stale = cases.values()
    assert fresh["transaction_status"] == "Pending"
    assert ANCHOR - when(fresh) <= timedelta(days=7)
    assert reversed_charge["transaction_status"] == "Reversed"
    assert stale["transaction_status"] == "Pending"
    assert ANCHOR - when(stale) > timedelta(days=7)
    fresh_pending = [
        item
        for item in account.transactions
        if item["transaction_status"] == "Pending" and ANCHOR - when(item) <= timedelta(days=7)
    ]
    assert fresh_pending == [fresh]
    assert len({case["product_id"] for case in cases.values()}) == 3
    merchants = Counter(item["merchant_name"] for item in account.transactions)
    assert all(merchants[case["merchant_name"]] >= 4 for case in cases.values())


def test_generated_rows_carry_origin_setup_a_low_score_and_no_fraud_label() -> None:
    account = generate(claim())

    assert {item["origin"] for item in account.transactions} == {"setup"}
    assert all(Decimal(0) <= item["fraud_score"] <= Decimal(30) for item in account.transactions)
    assert all("is_fraud" not in item for item in account.transactions)


def test_transaction_keys_sort_a_card_by_date() -> None:
    account = generate(claim())

    for product_id, items in by_card(account.transactions).items():
        ordered = sorted(items, key=lambda item: item["transaction_key"])
        assert [when(item) for item in ordered] == sorted(when(item) for item in items)
        assert all(item["transaction_key"].startswith(f"{product_id}#") for item in items)


def test_one_claim_always_generates_the_same_account() -> None:
    assert generate(claim()) == generate(claim())
    assert generate(claim()).transactions != generate(claim(customer_id="customer-2")).transactions
    assert (
        generate(claim()).transactions != generate(claim(anchor=ANCHOR + timedelta(seconds=1))).transactions
    )


def test_the_suspicious_pool_shares_no_merchant_with_any_country() -> None:
    local = {merchant.name for country in COUNTRIES.values() for merchant in country.merchants}

    assert not local & {merchant.name for merchant in SUSPICIOUS_POOL}
    assert all(len({m.name for m in country.merchants}) == 12 for country in COUNTRIES.values())


def test_a_normal_transaction_uses_one_of_the_country_merchants_and_is_dated_by_its_id() -> None:
    transaction_id = uuid7()

    item = manual_transaction(random.Random(1), claim("CO"), "card-1", transaction_id)  # noqa: S311

    assert item["merchant_name"] in {merchant.name for merchant in COUNTRIES["CO"].merchants}
    assert item["origin"] == "manual_normal"
    assert item["transaction_status"] == "Approved"
    assert item["currency"] == "COP"
    assert when(item) == uuid7_time(parse_uuid7(transaction_id))
    assert Decimal(0) <= item["fraud_score"] <= Decimal(30)


@pytest.mark.parametrize(
    ("score", "low", "high"),
    [(Score.FLAGGED, Decimal(31), Decimal(100)), (Score.MISSED, Decimal(0), Decimal(30))],
)
def test_a_suspicious_transaction_is_an_outside_merchant_with_the_chosen_score(
    score: Score, low: Decimal, high: Decimal
) -> None:
    for seed in range(20):
        item = manual_transaction(random.Random(seed), claim("PE"), "card-1", uuid7(), 4821, score)  # noqa: S311

        name, _, suffix = item["merchant_name"].rpartition(" ")
        assert name in {merchant.name for merchant in SUSPICIOUS_POOL}
        assert suffix == "4821"
        assert item["origin"] == "manual_suspicious"
        assert item["transaction_country"] == "PE"
        assert item["channel"] == "Web"
        assert low <= item["fraud_score"] <= high
        assert "is_fraud" not in item


def test_a_suspicious_transaction_without_score_has_none() -> None:
    item = manual_transaction(random.Random(1), claim(), "card-1", uuid7(), 1234, Score.NONE)  # noqa: S311

    assert "fraud_score" not in item
