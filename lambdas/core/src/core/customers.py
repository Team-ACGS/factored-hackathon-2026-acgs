import os
from collections.abc import Mapping
from typing import Any

import boto3

from core.conditional import put_if_absent
from core.read_model import projection, public

CUSTOMER_ATTRIBUTES = ("email", "created_at", "country", "language", "setup_completed_at")


def create_customer(session: boto3.Session, customer_id: str, email: str, created_at: str) -> bool:
    table = session.resource("dynamodb").Table(os.environ["TABLE_CUSTOMERS"])
    return put_if_absent(
        table, {"customer_id": customer_id, "email": email, "created_at": created_at}, "customer_id"
    )


def public_customer(item: Mapping[str, Any]) -> dict[str, Any]:
    return public(item, CUSTOMER_ATTRIBUTES)


def read_customer(session: boto3.Session, customer_id: str) -> dict[str, Any] | None:
    table = session.resource("dynamodb").Table(os.environ["TABLE_CUSTOMERS"])
    item = table.get_item(
        Key={"customer_id": customer_id}, ConsistentRead=True, **projection(CUSTOMER_ATTRIBUTES)
    ).get("Item")
    return public_customer(item) if item else None
