import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import boto3
from botocore.exceptions import ClientError

from core.conditional import put_if_absent

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import Table


class CustomerNotFound(Exception):
    pass


class SetupAlreadyCompleted(Exception):
    pass


@dataclass(frozen=True)
class CustomerProfile:
    country: str | None
    language: str | None
    setup_claimed_at: str | None
    setup_completed_at: str | None

    @classmethod
    def from_item(cls, item: Mapping[str, Any]) -> "CustomerProfile":
        return cls(
            country=_optional(item.get("country")),
            language=_optional(item.get("language")),
            setup_claimed_at=_optional(item.get("setup_claimed_at")),
            setup_completed_at=_optional(item.get("setup_completed_at")),
        )

    def public(self) -> dict[str, Any]:
        return {
            "country": self.country,
            "language": self.language,
            "setup_completed": self.setup_completed_at is not None,
        }


class Store:
    def __init__(self, customers: "Table", products: "Table", transactions: "Table") -> None:
        self._customers = customers
        self._products = products
        self._transactions = transactions

    @classmethod
    def from_session(cls, session: boto3.Session) -> "Store":
        dynamodb = session.resource("dynamodb")
        return cls(
            dynamodb.Table(os.environ["TABLE_CUSTOMERS"]),
            dynamodb.Table(os.environ["TABLE_PRODUCTS"]),
            dynamodb.Table(os.environ["TABLE_TRANSACTIONS"]),
        )

    def profile(self, customer_id: str) -> CustomerProfile | None:
        item = self._customers.get_item(Key={"customer_id": customer_id}, ConsistentRead=True).get("Item")
        return CustomerProfile.from_item(item) if item else None

    def claim_setup(self, customer_id: str, country: str, language: str, now: str) -> CustomerProfile:
        try:
            attributes = self._customers.update_item(
                Key={"customer_id": customer_id},
                UpdateExpression="SET #country = :country, #language = :language, #claimed = :now",
                ConditionExpression="attribute_exists(#id) AND attribute_not_exists(#claimed)",
                ExpressionAttributeNames={
                    "#id": "customer_id",
                    "#country": "country",
                    "#language": "language",
                    "#claimed": "setup_claimed_at",
                },
                ExpressionAttributeValues={":country": country, ":language": language, ":now": now},
                ReturnValues="ALL_NEW",
            )["Attributes"]
            return CustomerProfile.from_item(attributes)
        except ClientError as error:
            if not _condition_failed(error):
                raise
        stored = self.profile(customer_id)
        if stored is None:
            raise CustomerNotFound(customer_id)
        if stored.setup_completed_at is not None:
            raise SetupAlreadyCompleted(customer_id)
        return stored

    def complete_setup(self, customer_id: str, now: str) -> CustomerProfile:
        try:
            attributes = self._customers.update_item(
                Key={"customer_id": customer_id},
                UpdateExpression="SET #completed = :now",
                ConditionExpression="attribute_exists(#claimed) AND attribute_not_exists(#completed)",
                ExpressionAttributeNames={"#claimed": "setup_claimed_at", "#completed": "setup_completed_at"},
                ExpressionAttributeValues={":now": now},
                ReturnValues="ALL_NEW",
            )["Attributes"]
        except ClientError as error:
            if _condition_failed(error):
                raise SetupAlreadyCompleted(customer_id) from error
            raise
        return CustomerProfile.from_item(attributes)

    def write_account(
        self, cards: Iterable[Mapping[str, Any]], transactions: Iterable[Mapping[str, Any]]
    ) -> None:
        for card in cards:
            self._products.put_item(Item=dict(card))
        with self._transactions.batch_writer() as batch:
            for item in transactions:
                batch.put_item(Item=dict(item))

    def reserve_suspicious_suffix(self, customer_id: str, suffix: int) -> bool:
        try:
            self._customers.update_item(
                Key={"customer_id": customer_id},
                UpdateExpression="ADD #suffixes :suffix",
                ConditionExpression="attribute_exists(#id) AND NOT contains(#suffixes, :value)",
                ExpressionAttributeNames={"#id": "customer_id", "#suffixes": "suspicious_suffixes"},
                ExpressionAttributeValues={":suffix": {f"{suffix:04d}"}, ":value": f"{suffix:04d}"},
            )
        except ClientError as error:
            if _condition_failed(error):
                return False
            raise
        return True

    def add_transaction(self, item: Mapping[str, Any]) -> bool:
        return put_if_absent(self._transactions, item, "transaction_key")


def _condition_failed(error: ClientError) -> bool:
    return error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"


def _optional(value: object) -> str | None:
    return None if value is None else str(value)
