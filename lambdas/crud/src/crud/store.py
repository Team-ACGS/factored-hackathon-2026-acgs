import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from botocore.exceptions import ClientError

from core.cases import Cases
from core.customers import public_customer

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table


class CustomerNotFound(Exception):
    pass


class SetupAlreadyCompleted(Exception):
    pass


@dataclass(frozen=True)
class SetupClaim:
    country: str | None
    setup_claimed_at: str | None
    setup_completed_at: str | None

    @classmethod
    def from_item(cls, item: Mapping[str, Any]) -> "SetupClaim":
        return cls(
            country=_optional(item.get("country")),
            setup_claimed_at=_optional(item.get("setup_claimed_at")),
            setup_completed_at=_optional(item.get("setup_completed_at")),
        )


class Store:
    def __init__(
        self, customers: "Table", products: "Table", transactions: "Table", complaints: "Table"
    ) -> None:
        self._customers = customers
        self._products = products
        self._transactions = transactions
        self._cases = Cases(complaints)

    @classmethod
    def from_dynamodb(cls, dynamodb: "DynamoDBServiceResource") -> "Store":
        return cls(
            dynamodb.Table(os.environ["TABLE_CUSTOMERS"]),
            dynamodb.Table(os.environ["TABLE_PRODUCTS"]),
            dynamodb.Table(os.environ["TABLE_TRANSACTIONS"]),
            dynamodb.Table(os.environ["TABLE_COMPLAINTS"]),
        )

    def claim(self, customer_id: str) -> SetupClaim | None:
        item = self._customers.get_item(Key={"customer_id": customer_id}, ConsistentRead=True).get("Item")
        return SetupClaim.from_item(item) if item else None

    def claim_setup(self, customer_id: str, country: str, language: str, now: str) -> SetupClaim:
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
            return SetupClaim.from_item(attributes)
        except ClientError as error:
            if not _condition_failed(error):
                raise
        stored = self.claim(customer_id)
        if stored is None:
            raise CustomerNotFound(customer_id)
        if stored.setup_completed_at is not None:
            raise SetupAlreadyCompleted(customer_id)
        return stored

    def complete_setup(self, customer_id: str, now: str) -> dict[str, Any]:
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
        return public_customer(attributes)

    def write_account(
        self, cards: Iterable[Mapping[str, Any]], transactions: Iterable[Mapping[str, Any]]
    ) -> None:
        for card in cards:
            self._products.put_item(Item=dict(card))
        with self._transactions.batch_writer() as batch:
            for item in transactions:
                batch.put_item(Item=dict(item))

    def write_claim(self, item: Mapping[str, Any]) -> bool:
        return self._cases.write_if_absent(item)

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


def _condition_failed(error: ClientError) -> bool:
    return error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"


def _optional(value: object) -> str | None:
    return None if value is None else str(value)
