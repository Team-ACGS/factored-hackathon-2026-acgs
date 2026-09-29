from datetime import UTC, datetime

import boto3

from core.accounts import Accounts, public_transaction
from crud.catalog import COUNTRIES
from crud.generator import Claim, generate
from harness import Aws

ACCOUNT = generate(Claim("customer-1", COUNTRIES["PE"], datetime(2026, 9, 28, tzinfo=UTC)))


def test_the_public_transaction_never_carries_origin_or_keys() -> None:
    public = public_transaction({**ACCOUNT.transactions[0], "is_fraud": True})

    assert not {"origin", "customer_id", "transaction_key", "is_fraud"} & set(public)
    assert public["transaction_id"] == ACCOUNT.transactions[0]["transaction_id"]


def test_reads_never_return_origin_even_when_it_is_stored(aws: Aws) -> None:
    for card in ACCOUNT.cards:
        aws.products.put_item(Item=card)
    stored = ACCOUNT.transactions[0]
    aws.transactions.put_item(Item=stored)
    accounts = Accounts.from_session(boto3.Session())

    detail = accounts.transaction("customer-1", stored["product_id"], stored["transaction_id"])
    listed, _ = accounts.newest_transactions("customer-1", stored["product_id"], 20)

    assert detail is not None
    assert "origin" not in detail
    assert listed == [detail]
    assert all("customer_id" not in card for card in accounts.cards("customer-1"))
