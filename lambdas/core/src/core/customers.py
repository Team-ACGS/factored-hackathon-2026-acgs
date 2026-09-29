import os
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from core.conditional import put_if_absent
from core.read_model import projection, public

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource

CUSTOMER_ATTRIBUTES = ("email", "created_at", "country", "language", "setup_completed_at")


def create_customer(
    dynamodb: "DynamoDBServiceResource", customer_id: str, email: str, created_at: str
) -> bool:
    table = dynamodb.Table(os.environ["TABLE_CUSTOMERS"])
    return put_if_absent(
        table, {"customer_id": customer_id, "email": email, "created_at": created_at}, "customer_id"
    )


def public_customer(item: Mapping[str, Any]) -> dict[str, Any]:
    return public(item, CUSTOMER_ATTRIBUTES)


def read_customer(dynamodb: "DynamoDBServiceResource", customer_id: str) -> dict[str, Any] | None:
    table = dynamodb.Table(os.environ["TABLE_CUSTOMERS"])
    item = table.get_item(
        Key={"customer_id": customer_id}, ConsistentRead=True, **projection(CUSTOMER_ATTRIBUTES)
    ).get("Item")
    return public_customer(item) if item else None
