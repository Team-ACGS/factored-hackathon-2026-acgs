import os
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from boto3.dynamodb.conditions import ConditionBase, Key

from core.read_model import projection, public

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table

MEMORY_ATTRIBUTES = ("memory_key", "type", "subject", "note", "source_room_id", "created_at")
MEMORY_TYPES = ("recognized_charge", "recognized_merchant")


def memory_key(memory_type: str, subject: str) -> str:
    return f"{memory_type}#{subject}"


def public_memory(item: Mapping[str, Any]) -> dict[str, Any]:
    return public(item, MEMORY_ATTRIBUTES)


class Memory:
    def __init__(self, table: "Table") -> None:
        self._table = table

    @classmethod
    def from_dynamodb(cls, dynamodb: "DynamoDBServiceResource") -> "Memory":
        return cls(dynamodb.Table(os.environ["TABLE_MEMORY"]))

    def memory(self, customer_id: str, key: str) -> dict[str, Any] | None:
        item = self._table.get_item(
            Key={"customer_id": customer_id, "memory_key": key}, **projection(MEMORY_ATTRIBUTES)
        ).get("Item")
        return public_memory(item) if item else None

    def memories(self, customer_id: str, prefix: str, max_rows: int) -> tuple[list[dict[str, Any]], bool]:
        condition: ConditionBase = Key("customer_id").eq(customer_id)
        if prefix:
            condition = condition & Key("memory_key").begins_with(prefix)
        request: dict[str, Any] = {
            "KeyConditionExpression": condition,
            "Limit": max_rows,
            **projection(MEMORY_ATTRIBUTES),
        }
        page = self._table.query(**request)
        items = list(page["Items"])
        while "LastEvaluatedKey" in page and len(items) < max_rows:
            request["Limit"] = max_rows - len(items)
            page = self._table.query(**request, ExclusiveStartKey=page["LastEvaluatedKey"])
            items.extend(page["Items"])
        return [public_memory(item) for item in items], "LastEvaluatedKey" in page
