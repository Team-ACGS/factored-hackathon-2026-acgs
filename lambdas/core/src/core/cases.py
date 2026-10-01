import os
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from boto3.dynamodb.conditions import Key

from core.conditional import put_if_absent
from core.read_model import projection, public

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table

COMPLAINT_ATTRIBUTES = (
    "complaint_id",
    "area",
    "status",
    "creation_date",
    "assignment_date",
    "first_response_date",
    "resolution_date",
    "closing_date",
    "transaction_id",
    "product_id",
    "summary",
    "summary_points",
    "summary_language",
    "summary_generated_at",
    "summary_source",
)

CASE_TYPES = {"fraud": "fraud", "claims": "claim", "service": "service"}
STAGES = {
    "In Process": "in_review",
    "Escalated": "in_review",
    "Resolved": "resolved",
    "Rejected": "resolved",
    "Closed": "closed",
}
OPEN_STAGES = frozenset({"opened", "assigned", "in_review"})

_FNV_OFFSET = 0x811C9DC5
_FNV_PRIME = 0x01000193


def case_code(complaint_id: str, opened_at: str) -> str:
    digest = _FNV_OFFSET
    for unit in _utf16_leads(complaint_id):
        digest = ((digest ^ unit) * _FNV_PRIME) & 0xFFFFFFFF
    return f"CLR-{opened_at[:4]}-{digest % 1_000_000:06d}"


def case_type(area: object) -> str:
    return CASE_TYPES.get(str(area), "claim")


def stage(case: Mapping[str, Any]) -> str:
    status = case.get("status")
    if status == "Open" or status not in STAGES:
        return "assigned" if case.get("assignment_date") else "opened"
    return STAGES[str(status)]


def public_case(item: Mapping[str, Any]) -> dict[str, Any]:
    return public(item, COMPLAINT_ATTRIBUTES)


class Cases:
    def __init__(self, complaints: "Table") -> None:
        self._complaints = complaints

    @classmethod
    def from_dynamodb(cls, dynamodb: "DynamoDBServiceResource") -> "Cases":
        return cls(dynamodb.Table(os.environ["TABLE_COMPLAINTS"]))

    def case(self, customer_id: str, complaint_id: str) -> dict[str, Any] | None:
        item = self._complaints.get_item(
            Key={"customer_id": customer_id, "complaint_id": complaint_id}, **projection(COMPLAINT_ATTRIBUTES)
        ).get("Item")
        return public_case(item) if item else None

    def cases(self, customer_id: str, max_rows: int) -> tuple[list[dict[str, Any]], bool]:
        request: dict[str, Any] = {
            "KeyConditionExpression": Key("customer_id").eq(customer_id),
            "Limit": max_rows,
            **projection(COMPLAINT_ATTRIBUTES),
        }
        page = self._complaints.query(**request)
        items = list(page["Items"])
        while "LastEvaluatedKey" in page and len(items) < max_rows:
            request["Limit"] = max_rows - len(items)
            page = self._complaints.query(**request, ExclusiveStartKey=page["LastEvaluatedKey"])
            items.extend(page["Items"])
        return [public_case(item) for item in items], "LastEvaluatedKey" in page

    def write_if_absent(self, item: Mapping[str, Any]) -> bool:
        return put_if_absent(self._complaints, item, "complaint_id")


def _utf16_leads(text: str) -> list[int]:
    return [code if code < 0x10000 else 0xD800 + ((code - 0x10000) >> 10) for code in map(ord, text)]
