import base64
import json
import threading
from collections.abc import Mapping
from typing import Any

import boto3
import pytest

from core.access import customer_session
from core.customers import create_customer
from crud import handler as crud
from crud.catalog import COUNTRIES, SUSPICIOUS_POOL
from crud.generator import CaseKind
from crud.store import Store
from harness import STAFF_POOL_ID, Aws, LambdaContext, api_event, claims, uuid7

SUB = "0f3c5e1a-0000-4000-8000-000000000001"
OTHER = "0f3c5e1a-0000-4000-8000-000000000002"
HIDDEN = ("origin", "suspicious_suffixes", "setup_claimed_at")


def call(
    method: str,
    path: str,
    context: LambdaContext,
    body: object = None,
    query: dict[str, str] | None = None,
    token: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    response = crud.handler(api_event(method, path, token or claims(sub=SUB), body, query), context)
    assert not any(hidden in response["body"] for hidden in HIDDEN)
    return response["statusCode"], json.loads(response["body"] or "null")


def signed_up(customer_id: str) -> None:
    create_customer(boto3.Session(), customer_id, f"{customer_id}@example.com", "2026-09-28T12:00:00.000Z")


def set_up(context: LambdaContext, customer_id: str = SUB, country: str = "MX") -> dict[str, Any]:
    status, body = call(
        "POST",
        "/crud/profile/setup",
        context,
        {"country": country, "language": "es"},
        token=claims(sub=customer_id),
    )
    assert status == 201
    return body


def cards(context: LambdaContext, customer_id: str = SUB) -> list[dict[str, Any]]:
    status, body = call("GET", "/crud/cards", context, token=claims(sub=customer_id))
    assert status == 200
    return list(body["cards"])


def page(context: LambdaContext, product_id: str, cursor: str | None = None) -> tuple[int, dict[str, Any]]:
    return call("GET", f"/crud/cards/{product_id}", context, query={"cursor": cursor} if cursor else None)


def add(context: LambdaContext, product_id: str, **body: object) -> tuple[int, dict[str, Any]]:
    return call(
        "POST", f"/crud/cards/{product_id}/transactions", context, {"transaction_id": uuid7(), **body}
    )


def items(table: Any, customer_id: str = SUB) -> list[dict[str, Any]]:
    return [item for item in table.scan()["Items"] if item["customer_id"] == customer_id]


@pytest.fixture
def customer(aws: Aws) -> None:
    signed_up(SUB)


@pytest.fixture
def sessions(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    tagged: list[str] = []

    def recording(customer_id: str, service: str) -> boto3.Session:
        tagged.append(customer_id)
        return customer_session(customer_id, service)

    monkeypatch.setattr(crud, "customer_session", recording)
    return tagged


def test_a_new_customer_has_no_setup_until_it_completes(
    aws: Aws, customer: None, context: LambdaContext
) -> None:
    assert call("GET", "/crud/profile", context) == (
        200,
        {"profile": {"country": None, "language": None, "setup_completed": False}},
    )

    body = set_up(context)

    assert body["profile"] == {"country": "MX", "language": "es", "setup_completed": True}
    assert call("GET", "/crud/profile", context)[1]["profile"]["setup_completed"] is True


def test_setup_writes_the_account_in_the_customer_partition_and_returns_the_planted_cases(
    aws: Aws, customer: None, context: LambdaContext, sessions: list[str]
) -> None:
    body = set_up(context)

    assert set(sessions) == {SUB}
    assert len(items(aws.products)) == 3
    assert len(items(aws.transactions)) == 300
    assert [case["kind"] for case in body["cases"]] == [kind.value for kind in CaseKind]
    stored = {item["transaction_id"]: item for item in items(aws.transactions)}
    for case in body["cases"]:
        transaction = case["transaction"]
        assert (
            stored[transaction["transaction_id"]]["transaction_status"] == transaction["transaction_status"]
        )
        assert transaction["product_id"] in {card["product_id"] for card in cards(context)}


def test_a_second_setup_is_rejected_and_writes_nothing(
    aws: Aws, customer: None, context: LambdaContext
) -> None:
    set_up(context)
    before = items(aws.transactions)

    status, _ = call("POST", "/crud/profile/setup", context, {"country": "BR", "language": "pt-BR"})

    assert status == 409
    assert items(aws.transactions) == before
    assert call("GET", "/crud/profile", context)[1]["profile"]["country"] == "MX"


def test_a_setup_that_failed_halfway_resumes_to_the_same_data(
    aws: Aws, customer: None, context: LambdaContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = Store.write_account

    def partial(store: Store, cards: Any, transactions: Any) -> None:
        original(store, cards, list(transactions)[:120])
        raise RuntimeError("lambda timed out")

    monkeypatch.setattr(Store, "write_account", partial)
    with pytest.raises(RuntimeError):
        call("POST", "/crud/profile/setup", context, {"country": "CO", "language": "en"})
    assert call("GET", "/crud/profile", context)[1]["profile"]["setup_completed"] is False
    monkeypatch.setattr(Store, "write_account", original)

    body = set_up(context, country="BR")

    assert body["profile"]["country"] == "CO"
    assert len(items(aws.transactions)) == 300
    assert {item["currency"] for item in items(aws.transactions)} == {"COP"}


def test_two_concurrent_setups_complete_once_with_one_account(
    aws: Aws, customer: None, context: LambdaContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = Store.write_account
    both_writing = threading.Barrier(2, timeout=10)

    def synchronized(store: Store, cards: Any, transactions: Any) -> None:
        both_writing.wait()
        original(store, cards, transactions)

    monkeypatch.setattr(Store, "write_account", synchronized)
    statuses: list[int] = []

    def request() -> None:
        statuses.append(call("POST", "/crud/profile/setup", context, {"country": "AR", "language": "es"})[0])

    threads = [threading.Thread(target=request) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(statuses) == [201, 409]
    assert len(items(aws.products)) == 3
    assert len(items(aws.transactions)) == 300


@pytest.mark.parametrize(
    "body",
    [
        {"country": "CL", "language": "es"},
        {"country": "MX", "language": "fr"},
        {"country": "MX"},
        {"country": ["MX"], "language": "es"},
        {"country": "MX", "language": {"code": "es"}},
        [],
    ],
)
def test_a_setup_outside_the_catalog_is_rejected(
    aws: Aws, customer: None, context: LambdaContext, body: object
) -> None:
    status, _ = call("POST", "/crud/profile/setup", context, body)

    assert status == 400
    assert items(aws.transactions) == []


def test_cards_are_listed_credit_first(aws: Aws, customer: None, context: LambdaContext) -> None:
    set_up(context)

    listed = cards(context)

    assert [card["product_type"] for card in listed] == [
        "Tarjeta Crédito",
        "Tarjeta Crédito",
        "Tarjeta Débito",
    ]
    assert all(card["currency"] == "MXN" and card["product_number"].startswith("**** ") for card in listed)


def test_a_card_pages_through_all_its_transactions_newest_first(
    aws: Aws, customer: None, context: LambdaContext
) -> None:
    set_up(context)
    product_id = cards(context)[0]["product_id"]

    seen: list[dict[str, Any]] = []
    cursor: str | None = None
    pages = 0
    while True:
        status, body = page(context, product_id, cursor)
        assert status == 200
        assert body["card"]["product_id"] == product_id
        assert body["server_time"].endswith("Z")
        seen.extend(body["transactions"])
        pages += 1
        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert pages == 5
    assert len({item["transaction_id"] for item in seen}) == 100
    dates = [item["transaction_date"] for item in seen]
    assert dates == sorted(dates, reverse=True)
    assert {item["transaction_status"] for item in seen} == {"Approved", "Declined", "Pending", "Reversed"}


def encoded(key: str) -> str:
    return base64.urlsafe_b64encode(key.encode()).decode().rstrip("=")


def test_a_tampered_cursor_is_a_bad_request(aws: Aws, customer: None, context: LambdaContext) -> None:
    set_up(context)
    signed_up(OTHER)
    set_up(context, OTHER)
    first, second = (card["product_id"] for card in cards(context)[:2])
    foreign_card = cards(context, OTHER)[0]["product_id"]
    other_cards_cursor = page(context, second)[1]["next_cursor"]
    foreign_transaction = items(aws.transactions, OTHER)[0]["transaction_id"]

    for cursor in [
        "not a cursor!",
        "%%%",
        encoded("garbage"),
        encoded(f"{first}#2026-09-01T00:00:00.000Z#{uuid7()}"),
        other_cards_cursor,
        encoded(f"{foreign_card}#x#{foreign_transaction}"),
        base64.urlsafe_b64encode(b"\xff\xfe").decode(),
    ]:
        assert page(context, first, cursor)[0] == 400, cursor


def test_another_customers_card_and_transaction_are_not_found(
    aws: Aws, customer: None, context: LambdaContext
) -> None:
    set_up(context)
    signed_up(OTHER)
    set_up(context, OTHER)
    foreign = items(aws.transactions, OTHER)[0]

    assert page(context, foreign["product_id"])[0] == 404
    status, _ = call(
        "GET", f"/crud/cards/{foreign['product_id']}/transactions/{foreign['transaction_id']}", context
    )
    assert status == 404
    assert add(context, foreign["product_id"], kind="normal")[0] == 404
    assert len(items(aws.transactions, OTHER)) == 300


@pytest.mark.parametrize("product_id", ["not-a-card", uuid7()])
def test_an_unknown_card_is_not_found(
    aws: Aws, customer: None, context: LambdaContext, product_id: str
) -> None:
    set_up(context)

    assert page(context, product_id)[0] == 404


def test_a_transaction_detail_comes_from_the_read_model(
    aws: Aws, customer: None, context: LambdaContext
) -> None:
    set_up(context)
    stored = items(aws.transactions)[0]

    status, body = call(
        "GET", f"/crud/cards/{stored['product_id']}/transactions/{stored['transaction_id']}", context
    )

    assert status == 200
    assert body["transaction"]["merchant_name"] == stored["merchant_name"]
    assert body["transaction"]["amount"] == str(stored["amount"])
    assert set(body["transaction"]) == {
        "transaction_id",
        "product_id",
        "transaction_date",
        "transaction_type",
        "transaction_category",
        "amount",
        "currency",
        "channel",
        "merchant_name",
        "merchant_category",
        "transaction_country",
        "transaction_city",
        "transaction_status",
        "response_code",
        "fraud_score",
    }
    missing = call("GET", f"/crud/cards/{stored['product_id']}/transactions/{uuid7()}", context)
    assert missing[0] == 404


def test_a_normal_transaction_uses_a_customer_merchant_and_tops_the_list(
    aws: Aws, customer: None, context: LambdaContext
) -> None:
    set_up(context)
    product_id = cards(context)[1]["product_id"]

    status, body = add(context, product_id, kind="normal")

    assert status == 201
    added = body["transaction"]
    assert added["merchant_name"] in {merchant.name for merchant in COUNTRIES["MX"].merchants}
    assert added["transaction_status"] == "Approved"
    assert page(context, product_id)[1]["transactions"][0] == added
    stored = next(
        item for item in items(aws.transactions) if item["transaction_id"] == added["transaction_id"]
    )
    assert stored["origin"] == "manual_normal"


def test_a_retried_add_returns_the_stored_transaction(
    aws: Aws, customer: None, context: LambdaContext
) -> None:
    set_up(context)
    product_id = cards(context)[0]["product_id"]
    body = {"transaction_id": uuid7(), "kind": "suspicious", "score": "flagged"}

    first = call("POST", f"/crud/cards/{product_id}/transactions", context, body)
    retry = call("POST", f"/crud/cards/{product_id}/transactions", context, body)

    assert (first[0], retry[0]) == (201, 200)
    assert retry[1] == first[1]
    assert len(items(aws.transactions)) == 301


def suffix(transaction: Mapping[str, Any]) -> str:
    return str(transaction["merchant_name"]).rpartition(" ")[2]


def test_suspicious_transactions_use_outside_merchants_with_suffixes_unique_in_the_account(
    aws: Aws, customer: None, context: LambdaContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_up(context)
    product_id = cards(context)[2]["product_id"]
    drawn = iter([4821, 4821, 4821, 1234, 1234, 7777])
    monkeypatch.setattr(crud, "_draw_suffix", lambda: next(drawn))

    added = [add(context, product_id, kind="suspicious")[1]["transaction"] for _ in range(3)]

    assert [suffix(transaction) for transaction in added] == ["4821", "1234", "7777"]
    pool = {merchant.name for merchant in SUSPICIOUS_POOL}
    assert all(str(transaction["merchant_name"]).rpartition(" ")[0] in pool for transaction in added)
    stored = aws.customers.get_item(Key={"customer_id": SUB})["Item"]["suspicious_suffixes"]
    assert stored == {"4821", "1234", "7777"}
    status, body = call("GET", "/crud/profile", context)
    assert (status, body) == (200, {"profile": {"country": "MX", "language": "es", "setup_completed": True}})


@pytest.mark.parametrize(
    ("score", "check"),
    [
        ("flagged", lambda value: value is not None and 31 <= float(value) <= 100),
        ("missed", lambda value: value is not None and 0 <= float(value) <= 30),
        ("none", lambda value: value is None),
    ],
)
def test_the_suspicious_score_follows_the_chosen_option(
    aws: Aws, customer: None, context: LambdaContext, score: str, check: Any
) -> None:
    set_up(context)
    product_id = cards(context)[0]["product_id"]

    status, body = add(context, product_id, kind="suspicious", score=score)

    assert status == 201
    assert check(body["transaction"]["fraud_score"])


@pytest.mark.parametrize(
    "body",
    [
        {"transaction_id": uuid7(), "kind": "fraud"},
        {"transaction_id": uuid7(), "kind": "suspicious", "score": 99},
        {"transaction_id": "abc", "kind": "normal"},
        {"transaction_id": uuid7(1_000_000_000_000), "kind": "normal"},
    ],
)
def test_an_invalid_add_is_rejected(aws: Aws, customer: None, context: LambdaContext, body: object) -> None:
    set_up(context)
    product_id = cards(context)[0]["product_id"]

    status, _ = call("POST", f"/crud/cards/{product_id}/transactions", context, body)

    assert status == 400
    assert len(items(aws.transactions)) == 300


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/crud/profile"),
        ("POST", "/crud/profile/setup"),
        ("GET", "/crud/cards"),
        ("GET", f"/crud/cards/{uuid7()}"),
        ("GET", f"/crud/cards/{uuid7()}/transactions/{uuid7()}"),
        ("POST", f"/crud/cards/{uuid7()}/transactions"),
    ],
)
def test_a_staff_token_gets_forbidden(
    aws: Aws, context: LambdaContext, sessions: list[str], method: str, path: str
) -> None:
    staff = claims(STAFF_POOL_ID, groups="agents")

    status, _ = call(method, path, context, {"country": "MX", "language": "es"}, token=staff)

    assert status == 403
    assert sessions == []
