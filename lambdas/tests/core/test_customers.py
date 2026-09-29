from typing import Any

import boto3

from core.customers import CUSTOMER_ATTRIBUTES, public_customer, read_customer
from harness import Aws

STORED: dict[str, Any] = {
    "customer_id": "customer-1",
    "email": "ana@example.com",
    "created_at": "2026-09-28T12:00:00.000Z",
    "country": "MX",
    "language": "es",
    "setup_claimed_at": "2026-09-28T12:01:00.000Z",
    "setup_completed_at": "2026-09-28T12:01:02.000Z",
    "suspicious_suffixes": {"4821", "1234"},
}

HIDDEN = {"customer_id", "setup_claimed_at", "suspicious_suffixes"}


def test_the_public_customer_keeps_only_the_allow_list() -> None:
    public = public_customer(STORED)

    assert set(public) == set(CUSTOMER_ATTRIBUTES)
    assert not HIDDEN & set(public)


def test_reading_a_customer_never_returns_the_planted_suffixes_or_the_setup_claim(aws: Aws) -> None:
    aws.customers.put_item(Item=STORED)

    customer = read_customer(boto3.resource("dynamodb"), "customer-1")

    assert customer == {name: STORED[name] for name in CUSTOMER_ATTRIBUTES}
    assert "4821" not in str(customer)
