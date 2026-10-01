import random
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from core.ids import format_instant, parse_uuid7, uuid7_time
from core.tools.movements import cadence_of
from crud.catalog import COUNTRIES, SUSPICIOUS_POOL
from crud.generator import (
    Account,
    CaseKind,
    Claim,
    Score,
    generate,
    manual_transaction,
    max_purchase,
    seeded_claim,
)
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
def test_every_occasional_merchant_of_the_country_has_at_least_four_transactions(country: str) -> None:
    account = generate(claim(country))

    counts = Counter(item["merchant_name"] for item in account.transactions)
    assert set(counts) == {merchant.name for merchant in COUNTRIES[country].merchants}
    occasional = [
        merchant.name for merchant in COUNTRIES[country].merchants if not merchant.profile.recurring
    ]
    assert min(counts[name] for name in occasional) >= 4


@pytest.mark.parametrize("customer_id", ["customer-1", "customer-2", "customer-3", "customer-4"])
@pytest.mark.parametrize("country", sorted(COUNTRIES))
def test_each_subscription_bills_one_card_monthly_on_a_fixed_day(country: str, customer_id: str) -> None:
    account = generate(claim(country, customer_id))

    zone = COUNTRIES[country].zone
    for merchant in COUNTRIES[country].merchants:
        if not merchant.profile.recurring:
            continue
        charges = sorted(
            (item for item in account.transactions if item["merchant_name"] == merchant.name), key=when
        )
        days = [when(item).astimezone(zone).date() for item in charges]
        assert len(charges) == 3
        assert len({item["product_id"] for item in charges}) == 1
        assert len({day.day for day in days}) == 1
        assert cadence_of(days) == "monthly"
        assert {item["transaction_status"] for item in charges} == {"Approved"}
        assert len({item["amount"] for item in charges}) == 1


@pytest.mark.parametrize("country", sorted(COUNTRIES))
def test_the_largest_purchase_bounds_every_amount_the_generator_can_draw(country: str) -> None:
    largest = max_purchase(COUNTRIES[country])
    rate = COUNTRIES[country].usd_rate
    catalog = [
        *(m.profile.usd_high for m in COUNTRIES[country].merchants),
        *(m.usd_high for m in SUSPICIOUS_POOL),
    ]

    drawn = [
        manual_transaction(random.Random(seed), claim(country), "card-1", uuid7(), suffix)["amount"]  # noqa: S311
        for seed in range(200)
        for suffix in (None, 1000)
    ]

    assert max(drawn) <= largest
    assert largest >= max(Decimal(str(high)) * rate for high in catalog) - COUNTRIES[country].rounding


@pytest.mark.parametrize("customer_id", ["customer-1", "customer-2", "customer-3", "customer-4"])
@pytest.mark.parametrize("country", sorted(COUNTRIES))
def test_every_card_can_take_twenty_of_the_largest_purchase_and_has_a_balance_as_of_setup(
    country: str, customer_id: str
) -> None:
    account = generate(claim(country, customer_id))

    largest = max_purchase(COUNTRIES[country])
    credit, other_credit, debit = account.cards
    for card in (credit, other_credit):
        assert card["credit_limit"] - card["current_balance"] >= 20 * largest
    assert debit["current_balance"] >= 20 * largest
    assert {card["balance_as_of"] for card in account.cards} == {format_instant(ANCHOR)}


def debit_card(account: Account) -> dict[str, Any]:
    return next(card for card in account.cards if card["product_type"] == "Tarjeta Débito")


@pytest.mark.parametrize("customer_id", ["customer-1", "customer-2", "customer-3", "customer-4"])
@pytest.mark.parametrize("country", sorted(COUNTRIES))
def test_the_seeded_claim_disputes_the_newest_quiet_in_store_debit_purchase_a_week_old(
    country: str, customer_id: str
) -> None:
    account = generate(claim(country, customer_id))

    card = debit_card(account)
    cutoff = uuid7_time(parse_uuid7(card["product_id"])) - timedelta(days=7)
    eligible = [
        item
        for item in account.transactions
        if item["product_id"] == card["product_id"]
        and item["transaction_status"] == "Approved"
        and item["channel"] == "POS"
        and item["fraud_score"] <= 30
        and when(item) <= cutoff
    ]
    disputed = max(eligible, key=when)
    assert account.claim is not None
    opened = when(disputed) + timedelta(days=1)
    assert account.claim == {
        "customer_id": customer_id,
        "complaint_id": disputed["transaction_id"],
        "area": "claims",
        "status": "In Process",
        "creation_date": format_instant(opened),
        "assignment_date": format_instant(opened + timedelta(days=2)),
        "first_response_date": format_instant(opened + timedelta(days=6)),
        "transaction_id": disputed["transaction_id"],
        "product_id": card["product_id"],
    }


def test_the_seeded_claim_skips_charges_with_a_signal_or_too_recent() -> None:
    account = generate(claim())
    card = debit_card(account)
    assert account.claim is not None
    disputed = next(
        item for item in account.transactions if item["transaction_id"] == account.claim["transaction_id"]
    )
    flagged = {**disputed, "fraud_score": Decimal("31")}
    abroad = {**disputed, "transaction_country": "US"}
    others = [item for item in account.transactions if item is not disputed]

    for changed in (flagged, abroad):
        moved = seeded_claim(claim(), account.cards, [*others, changed])
        assert moved is not None
        assert moved["transaction_id"] != disputed["transaction_id"]
    assert (
        seeded_claim(
            claim(), account.cards, [item for item in others if item["product_id"] != card["product_id"]]
        )
        is None
    )


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
    assert generate(claim()).claim == generate(claim()).claim
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
