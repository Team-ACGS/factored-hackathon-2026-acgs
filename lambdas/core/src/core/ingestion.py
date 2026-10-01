import os
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from botocore.exceptions import ClientError

from core.accounts import Accounts, card_type, public_transaction, transaction_date, transaction_key
from core.ids import InvalidId, format_instant, parse_uuid7, uuid7_time
from core.observability import logger

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table

TRANSACTION_CONTRACT_VERSION = 1
MAX_CLOCK_SKEW = timedelta(minutes=2)
MAX_FRAUD_SCORE = Decimal(100)
DECLINE_CODES = frozenset({"05", "14", "51", "54"})
RESPONSE_CODES = {
    "Approved": frozenset({"00"}),
    "Reversed": frozenset({"00"}),
    "Declined": DECLINE_CODES,
    "Pending": DECLINE_CODES,
}
CARD_FIELDS = ("product_type", "currency", "current_balance", "credit_limit")


class Origin(StrEnum):
    SETUP = "setup"
    MANUAL_NORMAL = "manual_normal"
    MANUAL_SUSPICIOUS = "manual_suspicious"


class ContractViolation(ValueError):
    def __init__(self, fields: tuple[str, ...], reason: str = "") -> None:
        self.fields = fields
        detail = f": {reason}" if reason else ""
        super().__init__(
            f"transaction breaks contract v{TRANSACTION_CONTRACT_VERSION} on {', '.join(fields)}{detail}"
        )


class UnknownCard(LookupError):
    pass


@dataclass(frozen=True)
class Accepted:
    transaction: dict[str, Any]


@dataclass(frozen=True)
class Duplicate:
    transaction: dict[str, Any]


def check(item: Mapping[str, Any], currency: str | None, now: datetime) -> None:
    failed = _violations(item, now)
    if not failed and item["currency"] != currency:
        failed = ["currency"]
    if failed:
        raise ContractViolation(tuple(failed))


class Ingestion:
    def __init__(self, products: "Table", transactions: "Table") -> None:
        self._products = products
        self._transactions = transactions
        self._accounts = Accounts(products, transactions)

    @classmethod
    def from_dynamodb(cls, dynamodb: "DynamoDBServiceResource") -> "Ingestion":
        return cls(
            dynamodb.Table(os.environ["TABLE_PRODUCTS"]), dynamodb.Table(os.environ["TABLE_TRANSACTIONS"])
        )

    def accept(self, item: Mapping[str, Any], now: datetime) -> Accepted | Duplicate:
        failed = _violations(item, now)
        if failed:
            raise ContractViolation(tuple(failed))
        customer_id, product_id = item["customer_id"], item["product_id"]
        card = self._accounts.card(customer_id, product_id, CARD_FIELDS)
        if card is None:
            raise UnknownCard(product_id)
        check(item, card["currency"], now)

        writes: list[Any] = [
            {
                "Put": {
                    "TableName": self._transactions.name,
                    "Item": dict(item),
                    "ConditionExpression": "attribute_not_exists(transaction_key)",
                }
            }
        ]
        moves = item["transaction_status"] == "Approved"
        if moves:
            writes.append(self._balance_move(card, item, now))
        try:
            self._transactions.meta.client.transact_write_items(TransactItems=writes)
        except ClientError as error:
            reasons = _cancellation_reasons(error)
            if reasons[:1] == ["ConditionalCheckFailed"]:
                return Duplicate(self._stored(item))
            if reasons[1:2] == ["ConditionalCheckFailed"]:
                raise ContractViolation(("amount",), "more than the card can take") from error
            raise
        logger.info(
            "transaction accepted",
            contract_version=TRANSACTION_CONTRACT_VERSION,
            transaction_id=item["transaction_id"],
            origin=item["origin"],
            balance_moved=moves,
        )
        return Accepted(public_transaction(item))

    def _balance_move(
        self, card: Mapping[str, Any], item: Mapping[str, Any], now: datetime
    ) -> dict[str, Any]:
        amount: Decimal = item["amount"]
        purchased_at = uuid7_time(parse_uuid7(item["transaction_id"]))
        names = {"#id": "product_id", "#balance": "current_balance", "#as_of": "balance_as_of"}
        values: dict[str, Any] = {":amount": amount, ":as_of": format_instant(max(now, purchased_at))}
        kind = card_type(card["product_type"])
        if kind == "debit":
            expression = "SET #balance = #balance - :amount, #as_of = :as_of"
            condition = "attribute_exists(#id) AND #balance >= :amount"
        elif kind == "credit":
            expression = "SET #as_of = :as_of ADD #balance :amount"
            condition = "attribute_exists(#id)"
            if card["credit_limit"] is not None:
                condition += " AND #balance <= :ceiling"
                values[":ceiling"] = Decimal(card["credit_limit"]) - amount
        else:
            raise ContractViolation(("product_id",), "not a credit or debit card")
        return {
            "Update": {
                "TableName": self._products.name,
                "Key": {"customer_id": item["customer_id"], "product_id": item["product_id"]},
                "UpdateExpression": expression,
                "ConditionExpression": condition,
                "ExpressionAttributeNames": names,
                "ExpressionAttributeValues": values,
            }
        }

    def _stored(self, item: Mapping[str, Any]) -> dict[str, Any]:
        stored = self._accounts.transaction(item["customer_id"], item["product_id"], item["transaction_id"])
        if stored is None:
            raise LookupError(f"transaction {item['transaction_id']} lost its condition but is not stored")
        return stored


def _cancellation_reasons(error: ClientError) -> list[str]:
    response: dict[str, Any] = dict(error.response)
    if response.get("Error", {}).get("Code") != "TransactionCanceledException":
        return []
    return [str(reason.get("Code")) for reason in response.get("CancellationReasons", [])]


def _violations(item: Mapping[str, Any], now: datetime) -> list[str]:
    failed = sorted(name for name in item if name not in FIELDS)
    for name, valid in FIELDS.items():
        if name not in item:
            if name not in OPTIONAL:
                failed.append(name)
        elif not valid(item[name], item, now):
            failed.append(name)
    return failed


def _uuid(value: object, item: Mapping[str, Any], now: datetime) -> bool:
    try:
        return isinstance(value, str) and str(uuid.UUID(value)) == value
    except ValueError:
        return False


def _uuid7(value: object) -> uuid.UUID | None:
    try:
        return parse_uuid7(value)
    except InvalidId:
        return None


def _product_id(value: object, item: Mapping[str, Any], now: datetime) -> bool:
    return _uuid7(value) is not None


def _transaction_id(value: object, item: Mapping[str, Any], now: datetime) -> bool:
    parsed = _uuid7(value)
    return parsed is not None and uuid7_time(parsed) <= now + MAX_CLOCK_SKEW


def _transaction_key(value: object, item: Mapping[str, Any], now: datetime) -> bool:
    product_id, transaction_id = item.get("product_id"), item.get("transaction_id")
    if _uuid7(product_id) is None or _uuid7(transaction_id) is None:
        return False
    return value == transaction_key(str(product_id), str(transaction_id))


def _transaction_date(value: object, item: Mapping[str, Any], now: datetime) -> bool:
    transaction_id = item.get("transaction_id")
    return _uuid7(transaction_id) is not None and value == transaction_date(str(transaction_id))


def _text(value: object, item: Mapping[str, Any], now: datetime) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _code(length: int) -> Callable[[object, Mapping[str, Any], datetime], bool]:
    def valid(value: object, item: Mapping[str, Any], now: datetime) -> bool:
        return (
            isinstance(value, str)
            and len(value) == length
            and value.isascii()
            and value.isalpha()
            and value.isupper()
        )

    return valid


def _amount(value: object, item: Mapping[str, Any], now: datetime) -> bool:
    return isinstance(value, Decimal) and value.is_finite() and value > 0


def _status(value: object, item: Mapping[str, Any], now: datetime) -> bool:
    return isinstance(value, str) and value in RESPONSE_CODES


def _response_code(value: object, item: Mapping[str, Any], now: datetime) -> bool:
    codes = RESPONSE_CODES.get(str(item.get("transaction_status")))
    return codes is None or (isinstance(value, str) and value in codes)


def _fraud_score(value: object, item: Mapping[str, Any], now: datetime) -> bool:
    return isinstance(value, Decimal) and value.is_finite() and 0 <= value <= MAX_FRAUD_SCORE


def _origin(value: object, item: Mapping[str, Any], now: datetime) -> bool:
    return isinstance(value, str) and value in tuple(Origin)


FIELDS: dict[str, Callable[[Any, Mapping[str, Any], datetime], bool]] = {
    "customer_id": _uuid,
    "transaction_key": _transaction_key,
    "transaction_id": _transaction_id,
    "product_id": _product_id,
    "transaction_date": _transaction_date,
    "transaction_type": _text,
    "transaction_category": _text,
    "amount": _amount,
    "currency": _code(3),
    "channel": _text,
    "merchant_name": _text,
    "merchant_category": _text,
    "transaction_country": _code(2),
    "transaction_city": _text,
    "transaction_status": _status,
    "response_code": _response_code,
    "fraud_score": _fraud_score,
    "origin": _origin,
}
OPTIONAL = frozenset({"fraud_score"})
