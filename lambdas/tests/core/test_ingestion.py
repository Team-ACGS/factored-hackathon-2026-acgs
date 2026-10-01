import random
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import boto3
import pytest

from core.accounts import public_transaction, transaction_date, transaction_key
from core.ids import parse_uuid7, uuid7_time
from core.ingestion import (
    TRANSACTION_CONTRACT_VERSION,
    Accepted,
    ContractViolation,
    Duplicate,
    Ingestion,
    UnknownCard,
    check,
)
from core.observability import logger
from crud.catalog import COUNTRIES
from crud.generator import Claim, generate, manual_transaction
from harness import Aws, uuid7

CUSTOMER = "0f3c5e1a-0000-4000-8000-000000000001"
NOW = datetime.now(UTC)
CLAIM = Claim(CUSTOMER, COUNTRIES["MX"], NOW - timedelta(days=1))
CARDS = generate(CLAIM).cards
CREDIT, _, DEBIT = CARDS


def purchase(card: dict[str, Any], **changes: Any) -> dict[str, Any]:
    item = manual_transaction(random.Random(7), CLAIM, card["product_id"], uuid7())  # noqa: S311
    item.update(changes)
    return item


def ingestion() -> Ingestion:
    return Ingestion.from_dynamodb(boto3.resource("dynamodb"))


def stored_card(aws: Aws, card: dict[str, Any]) -> dict[str, Any]:
    return aws.products.get_item(Key={"customer_id": CUSTOMER, "product_id": card["product_id"]})["Item"]


def stored_rows(aws: Aws) -> list[dict[str, Any]]:
    return aws.transactions.scan()["Items"]


@pytest.fixture
def cards(aws: Aws) -> None:
    for card in CARDS:
        aws.products.put_item(Item=card)


def test_a_valid_row_is_written_and_logged_with_the_contract_version(
    aws: Aws, cards: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    logged: list[dict[str, Any]] = []
    monkeypatch.setattr(logger, "info", lambda message, **keys: logged.append(keys))
    item = purchase(CREDIT)

    outcome = ingestion().accept(item, NOW)

    assert outcome == Accepted(public_transaction(item))
    assert stored_rows(aws) == [item]
    assert [keys["contract_version"] for keys in logged] == [TRANSACTION_CONTRACT_VERSION]


def test_an_approved_credit_charge_adds_its_amount_and_stamps_the_balance(aws: Aws, cards: None) -> None:
    item = purchase(CREDIT)

    ingestion().accept(item, NOW)

    card = stored_card(aws, CREDIT)
    assert card["current_balance"] == CREDIT["current_balance"] + item["amount"]
    purchased_at = uuid7_time(parse_uuid7(item["transaction_id"]))
    assert datetime.fromisoformat(card["balance_as_of"]) >= purchased_at


def test_an_approved_debit_charge_subtracts_its_amount(aws: Aws, cards: None) -> None:
    item = purchase(DEBIT)

    ingestion().accept(item, NOW)

    assert stored_card(aws, DEBIT)["current_balance"] == DEBIT["current_balance"] - item["amount"]


@pytest.mark.parametrize(("status", "code"), [("Pending", "05"), ("Declined", "51"), ("Reversed", "00")])
def test_a_charge_that_is_not_approved_moves_nothing(aws: Aws, cards: None, status: str, code: str) -> None:
    item = purchase(CREDIT, transaction_status=status, response_code=code)

    assert isinstance(ingestion().accept(item, NOW), Accepted)

    assert stored_card(aws, CREDIT) == CREDIT
    assert stored_rows(aws) == [item]


def test_the_same_row_twice_is_written_once_and_moves_the_balance_once(aws: Aws, cards: None) -> None:
    item = purchase(DEBIT)

    first = ingestion().accept(item, NOW)
    second = ingestion().accept(item, NOW)

    assert second == Duplicate(first.transaction)
    assert stored_rows(aws) == [item]
    assert stored_card(aws, DEBIT)["current_balance"] == DEBIT["current_balance"] - item["amount"]


def test_a_debit_charge_above_the_funds_is_refused_and_writes_nothing(aws: Aws, cards: None) -> None:
    item = purchase(DEBIT, amount=DEBIT["current_balance"] + Decimal("0.01"))

    with pytest.raises(ContractViolation) as refused:
        ingestion().accept(item, NOW)

    assert refused.value.fields == ("amount",)
    assert stored_rows(aws) == []
    assert stored_card(aws, DEBIT) == DEBIT


def test_a_credit_charge_past_the_limit_is_refused_and_one_that_reaches_it_is_not(
    aws: Aws, cards: None
) -> None:
    available = CREDIT["credit_limit"] - CREDIT["current_balance"]

    with pytest.raises(ContractViolation):
        ingestion().accept(purchase(CREDIT, amount=available + Decimal("0.01")), NOW)
    ingestion().accept(purchase(CREDIT, amount=available), NOW)

    assert stored_card(aws, CREDIT)["current_balance"] == CREDIT["credit_limit"]
    assert len(stored_rows(aws)) == 1


def test_a_duplicate_that_would_now_exceed_the_funds_still_returns_the_stored_row(
    aws: Aws, cards: None
) -> None:
    item = purchase(DEBIT)
    first = ingestion().accept(item, NOW)
    aws.products.update_item(
        Key={"customer_id": CUSTOMER, "product_id": DEBIT["product_id"]},
        UpdateExpression="SET current_balance = :empty",
        ExpressionAttributeValues={":empty": Decimal(0)},
    )

    assert ingestion().accept(item, NOW) == Duplicate(first.transaction)
    assert stored_card(aws, DEBIT)["current_balance"] == 0


def test_an_unknown_card_writes_nothing(aws: Aws, cards: None) -> None:
    item = purchase(CREDIT)
    other = uuid7()
    item.update(product_id=other, transaction_key=transaction_key(other, item["transaction_id"]))

    with pytest.raises(UnknownCard):
        ingestion().accept(item, NOW)

    assert stored_rows(aws) == []


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"customer_id": "customer-1"}, "customer_id"),
        ({"amount": Decimal(0)}, "amount"),
        ({"amount": "120.00"}, "amount"),
        ({"currency": "USD"}, "currency"),
        ({"currency": "pesos"}, "currency"),
        ({"transaction_country": "Mexico"}, "transaction_country"),
        ({"transaction_status": "Settled"}, "transaction_status"),
        ({"response_code": "51"}, "response_code"),
        ({"fraud_score": Decimal(101)}, "fraud_score"),
        ({"origin": "replay"}, "origin"),
        ({"merchant_name": " "}, "merchant_name"),
        ({"transaction_key": "card#date#id"}, "transaction_key"),
        ({"transaction_date": "2026-01-01T00:00:00.000Z"}, "transaction_date"),
        ({"ingested_at": "2026-10-01T00:00:00.000Z"}, "ingested_at"),
        ({"lineage_source": "crud"}, "lineage_source"),
        ({"contract_version": 1}, "contract_version"),
    ],
)
def test_a_contract_failure_names_the_field_and_writes_nothing(
    aws: Aws, cards: None, changes: dict[str, Any], field: str
) -> None:
    with pytest.raises(ContractViolation) as refused:
        ingestion().accept(purchase(CREDIT, **changes), NOW)

    assert refused.value.fields == (field,)
    assert field in str(refused.value)
    assert stored_rows(aws) == []
    assert stored_card(aws, CREDIT) == CREDIT


def test_a_missing_field_is_named(aws: Aws, cards: None) -> None:
    item = purchase(CREDIT)
    del item["channel"]

    with pytest.raises(ContractViolation) as refused:
        ingestion().accept(item, NOW)

    assert refused.value.fields == ("channel",)


def test_a_row_dated_past_the_clock_skew_is_refused() -> None:
    later = int((NOW + timedelta(minutes=3)).timestamp() * 1000)
    transaction_id = uuid7(later)
    item = purchase(
        CREDIT,
        transaction_id=transaction_id,
        transaction_key=transaction_key(CREDIT["product_id"], transaction_id),
        transaction_date=transaction_date(transaction_id),
    )

    with pytest.raises(ContractViolation) as refused:
        check(item, "MXN", NOW)

    assert refused.value.fields == ("transaction_id",)
    check(item, "MXN", NOW + timedelta(minutes=1))


def test_a_written_row_carries_no_lineage_and_its_freshness_comes_from_its_id(aws: Aws, cards: None) -> None:
    item = purchase(CREDIT)

    ingestion().accept(item, NOW)

    [row] = stored_rows(aws)
    assert not {name for name in row if name in {"ingested_at", "contract_version"} or "lineage" in name}
    minted = uuid7_time(parse_uuid7(row["transaction_id"]))
    assert minted == datetime.fromisoformat(row["transaction_date"])
    assert timedelta(0) <= datetime.now(UTC) - minted < timedelta(minutes=1)
