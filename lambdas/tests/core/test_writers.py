from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

import pytest

from core.access import customer_session
from core.accounts import Accounts
from core.cases import Cases
from harness import Aws, DemoAccount, demo_account, uuid7

NOW = datetime(2026, 9, 20, 17, 0, tzinfo=UTC)
CUSTOMER = "c0ffee00-0000-4000-8000-0000000000e1"
OPENED = "2026-09-20T17:00:00.000Z"


@pytest.fixture
def account(aws: Aws) -> DemoAccount:
    return demo_account(aws, CUSTOMER, "MX", "es", NOW - timedelta(hours=1))


def accounts() -> Accounts:
    return Accounts.from_dynamodb(customer_session(CUSTOMER, "chatbot").dynamodb)


def cases() -> Cases:
    return Cases.from_dynamodb(customer_session(CUSTOMER, "chatbot").dynamodb)


def card_row(aws: Aws, product_id: str) -> Mapping[str, object]:
    return aws.products.get_item(Key={"customer_id": CUSTOMER, "product_id": product_id})["Item"]


def test_a_block_writes_once_and_a_redelivery_of_the_same_ask_continues(
    aws: Aws, account: DemoAccount
) -> None:
    card = account.cards[0]["product_id"]
    ask = uuid7()

    assert accounts().block(CUSTOMER, card, ask, OPENED) == "written"
    assert accounts().block(CUSTOMER, card, ask, "2026-09-20T17:05:00.000Z") == "redelivered"

    row = card_row(aws, card)
    assert (row["product_status"], row["blocked_by"], row["blocked_at"]) == ("Blocked", ask, OPENED)
    assert accounts().read_status(CUSTOMER, card) == "Blocked"


def test_a_card_blocked_by_another_ask_or_the_bank_is_never_written_again(
    aws: Aws, account: DemoAccount
) -> None:
    card = account.cards[0]["product_id"]
    first, second = uuid7(), uuid7()
    accounts().block(CUSTOMER, card, first, OPENED)

    assert accounts().block(CUSTOMER, card, second, "2026-09-20T17:05:00.000Z") == "already"
    assert card_row(aws, card)["blocked_by"] == first

    other = account.cards[1]["product_id"]
    aws.products.update_item(
        Key={"customer_id": CUSTOMER, "product_id": other},
        UpdateExpression="SET product_status = :blocked",
        ExpressionAttributeValues={":blocked": "Blocked"},
    )
    assert accounts().block(CUSTOMER, other, second, OPENED) == "already"
    assert "blocked_by" not in card_row(aws, other)


def test_a_block_never_creates_a_card_nor_touches_one_that_is_not_active(
    aws: Aws, account: DemoAccount
) -> None:
    assert accounts().block(CUSTOMER, uuid7(), uuid7(), OPENED) == "missing"
    assert aws.products.scan()["Count"] == len(account.cards)

    card = account.cards[2]["product_id"]
    aws.products.update_item(
        Key={"customer_id": CUSTOMER, "product_id": card},
        UpdateExpression="SET product_status = :expired",
        ExpressionAttributeValues={":expired": "Expired"},
    )
    assert accounts().block(CUSTOMER, card, uuid7(), OPENED) == "inactive"
    assert card_row(aws, card)["product_status"] == "Expired"


def test_a_block_is_keyed_by_the_customer_so_another_customers_card_is_missing(
    aws: Aws, account: DemoAccount
) -> None:
    stranger = "c0ffee00-0000-4000-8000-0000000000e2"
    other = demo_account(aws, stranger, "MX", "es", NOW - timedelta(hours=1))
    card = other.cards[0]["product_id"]

    assert accounts().block(CUSTOMER, card, uuid7(), OPENED) == "missing"
    assert aws.products.get_item(Key={"customer_id": stranger, "product_id": card})["Item"][
        "product_status"
    ] == ("Active")


def test_a_case_opens_once_per_ask_and_reads_back(aws: Aws, account: DemoAccount) -> None:
    row = account.transactions[0]
    ask = uuid7()

    first, created = cases().open(CUSTOMER, ask, "fraud", OPENED, row["product_id"], row["transaction_id"])
    again, recreated = cases().open(
        CUSTOMER, ask, "fraud", "2026-09-20T17:05:00.000Z", row["product_id"], row["transaction_id"]
    )

    assert (created, recreated) == (True, False)
    assert first == again
    assert first is not None
    assert (first["area"], first["creation_date"]) == ("fraud", OPENED)
    stored = aws.complaints.get_item(Key={"customer_id": CUSTOMER, "complaint_id": ask})["Item"]
    assert (stored["case_type"], stored["reception_channel"], stored["status"]) == ("fraud", "clara", "Open")
    assert aws.complaints.scan()["Count"] == 1 + (1 if account.claim else 0)


def test_a_case_whose_row_does_not_match_on_read_back_is_not_confirmed(
    aws: Aws, account: DemoAccount
) -> None:
    row = account.transactions[0]
    ask = uuid7()
    aws.complaints.put_item(Item={"customer_id": CUSTOMER, "complaint_id": ask, "area": "claims"})

    assert cases().open(CUSTOMER, ask, "fraud", OPENED, row["product_id"], row["transaction_id"]) == (
        None,
        False,
    )


def test_the_summary_is_written_once(aws: Aws, account: DemoAccount) -> None:
    ask = uuid7()
    cases().open(CUSTOMER, ask, "service", OPENED)
    summary = {
        "summary": "Pide desbloquear su tarjeta.",
        "summary_points": ["Pide desbloquear su tarjeta."],
        "summary_language": "es",
        "summary_generated_at": OPENED,
        "summary_source": "template",
    }

    assert cases().write_summary(CUSTOMER, ask, summary)
    assert not cases().write_summary(CUSTOMER, ask, {**summary, "summary": "Otra cosa."})
    assert not cases().write_summary(CUSTOMER, uuid7(), summary)

    stored = cases().case(CUSTOMER, ask, consistent=True)
    assert stored is not None
    assert stored["summary"] == "Pide desbloquear su tarjeta."
    assert (
        aws.complaints.get_item(Key={"customer_id": CUSTOMER, "complaint_id": ask})["Item"]["status"]
        == "Open"
    )
