import os
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import boto3
from boto3.dynamodb.conditions import Key

from core.ids import format_instant, parse_uuid7, uuid7_time

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import Table

CARD_ATTRIBUTES = (
    "product_id",
    "product_type",
    "product_number",
    "currency",
    "current_balance",
    "credit_limit",
    "product_status",
    "expiration_date",
)

TRANSACTION_ATTRIBUTES = (
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
)


def transaction_date(transaction_id: str) -> str:
    return format_instant(uuid7_time(parse_uuid7(transaction_id)))


def transaction_key(product_id: str, transaction_id: str) -> str:
    return f"{product_id}#{transaction_date(transaction_id)}#{transaction_id}"


def public_card(item: Mapping[str, Any]) -> dict[str, Any]:
    return _public(item, CARD_ATTRIBUTES)


def public_transaction(item: Mapping[str, Any]) -> dict[str, Any]:
    return _public(item, TRANSACTION_ATTRIBUTES)


class Accounts:
    def __init__(self, products: "Table", transactions: "Table") -> None:
        self._products = products
        self._transactions = transactions

    @classmethod
    def from_session(cls, session: boto3.Session) -> "Accounts":
        dynamodb = session.resource("dynamodb")
        return cls(
            dynamodb.Table(os.environ["TABLE_PRODUCTS"]), dynamodb.Table(os.environ["TABLE_TRANSACTIONS"])
        )

    def cards(self, customer_id: str) -> list[dict[str, Any]]:
        request = {
            "KeyConditionExpression": Key("customer_id").eq(customer_id),
            **_projection(CARD_ATTRIBUTES),
        }
        page = self._products.query(**request)
        items = list(page["Items"])
        while "LastEvaluatedKey" in page:
            page = self._products.query(**request, ExclusiveStartKey=page["LastEvaluatedKey"])
            items.extend(page["Items"])
        return [public_card(item) for item in items]

    def card(self, customer_id: str, product_id: str) -> dict[str, Any] | None:
        item = self._products.get_item(
            Key={"customer_id": customer_id, "product_id": product_id}, **_projection(CARD_ATTRIBUTES)
        ).get("Item")
        return public_card(item) if item else None

    def transaction(self, customer_id: str, product_id: str, transaction_id: str) -> dict[str, Any] | None:
        item = self._transactions.get_item(
            Key={"customer_id": customer_id, "transaction_key": transaction_key(product_id, transaction_id)},
            ConsistentRead=True,
            **_projection(TRANSACTION_ATTRIBUTES),
        ).get("Item")
        return public_transaction(item) if item else None

    def newest_transactions(
        self, customer_id: str, product_id: str, limit: int, after_key: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        request: dict[str, Any] = {
            "KeyConditionExpression": Key("customer_id").eq(customer_id)
            & Key("transaction_key").begins_with(f"{product_id}#"),
            "ScanIndexForward": False,
            "ConsistentRead": True,
            "Limit": limit + 1,
            **_projection(TRANSACTION_ATTRIBUTES),
        }
        if after_key is not None:
            request["ExclusiveStartKey"] = {"customer_id": customer_id, "transaction_key": after_key}
        items = self._transactions.query(**request)["Items"]
        page = [public_transaction(item) for item in items[:limit]]
        if len(items) <= limit:
            return page, None
        last = page[-1]
        return page, transaction_key(last["product_id"], last["transaction_id"])


def _projection(attributes: Sequence[str]) -> dict[str, Any]:
    names = {f"#a{index}": name for index, name in enumerate(attributes)}
    return {"ProjectionExpression": ", ".join(names), "ExpressionAttributeNames": names}


def _public(item: Mapping[str, Any], attributes: Sequence[str]) -> dict[str, Any]:
    return {name: _plain(item.get(name)) for name in attributes}


def _plain(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
    return value
