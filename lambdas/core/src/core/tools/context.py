from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from core.access import customer_session
from core.countries import zone
from core.ids import format_instant
from core.retrieval import PolicySearch

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource

HISTORY_DAYS = 92
MAX_ROWS = 500
MAX_CARDS = 4


class NotFound(Exception):
    pass


class InvalidArgument(ValueError):
    pass


@dataclass(frozen=True)
class Verdict:
    decision: str
    rule_ids: tuple[str, ...] = ()


Decide = Callable[[Mapping[str, Any]], Verdict | None]


@dataclass(frozen=True)
class ToolContext:
    customer_id: str
    country: str
    language: str
    now: datetime
    service: str = "chatbot"
    decide: Decide | None = None
    policies: PolicySearch | None = None

    @property
    def zone(self) -> timezone:
        return zone(self.country)

    @property
    def today(self) -> date:
        return self.now.astimezone(self.zone).date()

    @property
    def window_start(self) -> date:
        return self.today - timedelta(days=HISTORY_DAYS - 1)

    def dynamodb(self) -> "DynamoDBServiceResource":
        return customer_session(self.customer_id, self.service, read_only=True).dynamodb

    def local_day(self, instant: datetime) -> date:
        return instant.astimezone(self.zone).date()

    def day_start(self, day: date) -> str:
        return format_instant(datetime.combine(day, time(), self.zone))


@dataclass(frozen=True)
class ToolResult:
    tool: str
    ids: tuple[str, ...]


def instant(value: object) -> datetime:
    return datetime.fromisoformat(str(value))


def decimal(value: object) -> Decimal:
    return Decimal(str(value))


def median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2
