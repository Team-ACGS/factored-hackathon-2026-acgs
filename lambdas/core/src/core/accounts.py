import os
import time
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Literal

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from core.ids import format_instant, parse_uuid7, uuid7_time
from core.read_model import projection, public

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table

CARD_ATTRIBUTES = (
    "product_id",
    "product_type",
    "product_number",
    "currency",
    "current_balance",
    "credit_limit",
    "product_status",
    "expiration_date",
    "balance_as_of",
    "blocked_at",
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


BATCH_ATTEMPTS = 4
BATCH_BACKOFF_SECONDS = 0.05
READ_BACK_ATTEMPTS = 2
ACTIVE = "Active"
BLOCKED = "Blocked"

Blocking = Literal["written", "redelivered", "already", "missing", "inactive"]


class ReadIncomplete(Exception):
    pass


def card_type(product_type: object) -> str | None:
    text = str(product_type or "").lower()
    if "créd" in text or "cred" in text:
        return "credit"
    if "déb" in text or "deb" in text:
        return "debit"
    return None


def transaction_date(transaction_id: str) -> str:
    return format_instant(uuid7_time(parse_uuid7(transaction_id)))


def transaction_key(product_id: str, transaction_id: str) -> str:
    return f"{product_id}#{transaction_date(transaction_id)}#{transaction_id}"


def public_transaction(item: Mapping[str, Any]) -> dict[str, Any]:
    return public(item, TRANSACTION_ATTRIBUTES)


class Accounts:
    def __init__(self, products: "Table", transactions: "Table") -> None:
        self._products = products
        self._transactions = transactions

    @classmethod
    def from_dynamodb(cls, dynamodb: "DynamoDBServiceResource") -> "Accounts":
        return cls(
            dynamodb.Table(os.environ["TABLE_PRODUCTS"]), dynamodb.Table(os.environ["TABLE_TRANSACTIONS"])
        )

    def cards(self, customer_id: str, attributes: Sequence[str] = CARD_ATTRIBUTES) -> list[dict[str, Any]]:
        request = {
            "KeyConditionExpression": Key("customer_id").eq(customer_id),
            **projection(attributes),
        }
        page = self._products.query(**request)
        items = list(page["Items"])
        while "LastEvaluatedKey" in page:
            page = self._products.query(**request, ExclusiveStartKey=page["LastEvaluatedKey"])
            items.extend(page["Items"])
        return [public(item, attributes) for item in items]

    def card(
        self, customer_id: str, product_id: str, attributes: Sequence[str] = CARD_ATTRIBUTES
    ) -> dict[str, Any] | None:
        item = self._products.get_item(
            Key={"customer_id": customer_id, "product_id": product_id}, **projection(attributes)
        ).get("Item")
        return public(item, attributes) if item else None

    def block(self, customer_id: str, product_id: str, ask_id: str, now: str) -> Blocking:
        key = {"customer_id": customer_id, "product_id": product_id}
        try:
            self._products.update_item(
                Key=key,
                UpdateExpression="SET product_status = :blocked, blocked_by = :ask, blocked_at = :now",
                ConditionExpression="product_status = :active",
                ExpressionAttributeValues={
                    ":blocked": BLOCKED,
                    ":ask": ask_id,
                    ":now": now,
                    ":active": ACTIVE,
                },
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise
        else:
            return "written"
        item = self._products.get_item(
            Key=key, ConsistentRead=True, ProjectionExpression="product_status, blocked_by"
        ).get("Item")
        if item is None:
            return "missing"
        if item.get("product_status") != BLOCKED:
            return "inactive"
        return "redelivered" if item.get("blocked_by") == ask_id else "already"

    def read_status(self, customer_id: str, product_id: str) -> str | None:
        for attempt in range(READ_BACK_ATTEMPTS):
            try:
                item = self._products.get_item(
                    Key={"customer_id": customer_id, "product_id": product_id},
                    ConsistentRead=True,
                    ProjectionExpression="product_status",
                ).get("Item")
            except ClientError:
                if attempt + 1 == READ_BACK_ATTEMPTS:
                    return None
                continue
            return str(item["product_status"]) if item and item.get("product_status") else None
        return None

    def transaction(
        self,
        customer_id: str,
        product_id: str,
        transaction_id: str,
        attributes: Sequence[str] = TRANSACTION_ATTRIBUTES,
    ) -> dict[str, Any] | None:
        item = self._transactions.get_item(
            Key={"customer_id": customer_id, "transaction_key": transaction_key(product_id, transaction_id)},
            ConsistentRead=True,
            **projection(attributes),
        ).get("Item")
        return public(item, attributes) if item else None

    def newest_transactions(
        self, customer_id: str, product_id: str, limit: int, after_key: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        request: dict[str, Any] = {
            "KeyConditionExpression": Key("customer_id").eq(customer_id)
            & Key("transaction_key").begins_with(f"{product_id}#"),
            "ScanIndexForward": False,
            "ConsistentRead": True,
            "Limit": limit + 1,
            **projection(TRANSACTION_ATTRIBUTES),
        }
        if after_key is not None:
            request["ExclusiveStartKey"] = {"customer_id": customer_id, "transaction_key": after_key}
        items = self._transactions.query(**request)["Items"]
        page = [public_transaction(item) for item in items[:limit]]
        if len(items) <= limit:
            return page, None
        last = page[-1]
        return page, transaction_key(last["product_id"], last["transaction_id"])

    def transactions_between(
        self,
        customer_id: str,
        product_id: str,
        start: str,
        end: str,
        attributes: Sequence[str],
        max_rows: int,
    ) -> tuple[list[dict[str, Any]], bool]:
        request: dict[str, Any] = {
            "KeyConditionExpression": Key("customer_id").eq(customer_id)
            & Key("transaction_key").between(f"{product_id}#{start}", f"{product_id}#{end}"),
            "ScanIndexForward": False,
            "Limit": max_rows,
            **projection(attributes),
        }
        page = self._transactions.query(**request)
        items = list(page["Items"])
        while "LastEvaluatedKey" in page and len(items) < max_rows:
            request["Limit"] = max_rows - len(items)
            page = self._transactions.query(**request, ExclusiveStartKey=page["LastEvaluatedKey"])
            items.extend(page["Items"])
        return [public(item, attributes) for item in items], "LastEvaluatedKey" in page

    def transaction_on_any_card(
        self, customer_id: str, product_ids: Sequence[str], transaction_id: str, attributes: Sequence[str]
    ) -> dict[str, Any] | None:
        if not product_ids:
            return None
        table = self._transactions.name
        keys = [
            {"customer_id": customer_id, "transaction_key": transaction_key(product_id, transaction_id)}
            for product_id in product_ids
        ]
        request: dict[str, Any] = {table: {"Keys": keys, "ConsistentRead": True, **projection(attributes)}}
        found: list[dict[str, Any]] = []
        for attempt in range(BATCH_ATTEMPTS):
            if attempt:
                time.sleep(BATCH_BACKOFF_SECONDS * 2 ** (attempt - 1))
            response = self._transactions.meta.client.batch_get_item(RequestItems=request)
            found.extend(response["Responses"].get(table, []))
            request = response.get("UnprocessedKeys") or {}
            if not request:
                return public(found[0], attributes) if found else None
        raise ReadIncomplete(f"{table} kept keys unprocessed after {BATCH_ATTEMPTS} attempts")
