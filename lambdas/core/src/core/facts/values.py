from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, ClassVar

from core.countries import zone
from core.ids import format_instant

Json = dict[str, Any]


@dataclass(frozen=True)
class Money:
    TYPE: ClassVar[str] = "money"
    amount: Decimal
    currency: str

    def to_model(self) -> Json:
        return {"type": self.TYPE, "amount": format(self.amount, "f"), "currency": self.currency}


@dataclass(frozen=True)
class Day:
    TYPE: ClassVar[str] = "date"
    value: date

    def to_model(self) -> Json:
        return {"type": self.TYPE, "value": self.value.isoformat()}


@dataclass(frozen=True)
class Instant:
    TYPE: ClassVar[str] = "datetime"
    value: datetime

    def to_model(self) -> Json:
        return {"type": self.TYPE, "value": format_instant(self.value)}


@dataclass(frozen=True)
class Period:
    TYPE: ClassVar[str] = "period"
    start: date
    end: date

    def to_model(self) -> Json:
        return {"type": self.TYPE, "from": self.start.isoformat(), "to": self.end.isoformat()}


@dataclass(frozen=True)
class Count:
    TYPE: ClassVar[str] = "count"
    value: int
    noun: str

    def to_model(self) -> Json:
        return {"type": self.TYPE, "value": self.value, "noun": self.noun}


@dataclass(frozen=True)
class Last4:
    TYPE: ClassVar[str] = "last4"
    value: str

    def to_model(self) -> Json:
        return {"type": self.TYPE, "value": self.value}


@dataclass(frozen=True)
class Status:
    TYPE: ClassVar[str] = "status"
    domain: str
    value: str

    def to_model(self) -> Json:
        return {"type": self.TYPE, "domain": self.domain, "value": self.value}


@dataclass(frozen=True)
class Label:
    TYPE: ClassVar[str] = "enum"
    domain: str
    value: str

    def to_model(self) -> Json:
        return {"type": self.TYPE, "domain": self.domain, "value": self.value}


@dataclass(frozen=True)
class Labels:
    TYPE: ClassVar[str] = "enum_list"
    domain: str
    values: tuple[str, ...]

    def to_model(self) -> Json:
        return {"type": self.TYPE, "domain": self.domain, "values": list(self.values)}


@dataclass(frozen=True)
class Merchant:
    TYPE: ClassVar[str] = "merchant"
    value: str

    def to_model(self) -> Json:
        return {"type": self.TYPE, "value": self.value}


@dataclass(frozen=True)
class City:
    TYPE: ClassVar[str] = "city"
    value: str

    def to_model(self) -> Json:
        return {"type": self.TYPE, "value": self.value}


@dataclass(frozen=True)
class Country:
    TYPE: ClassVar[str] = "country"
    code: str

    def to_model(self) -> Json:
        return {"type": self.TYPE, "value": self.code}


@dataclass(frozen=True)
class CaseCode:
    TYPE: ClassVar[str] = "case_id"
    value: str

    def to_model(self) -> Json:
        return {"type": self.TYPE, "value": self.value}


@dataclass(frozen=True)
class Ratio:
    TYPE: ClassVar[str] = "ratio"
    value: Decimal

    def to_model(self) -> Json:
        return {"type": self.TYPE, "value": format(self.value, "f")}


@dataclass(frozen=True)
class Percent:
    TYPE: ClassVar[str] = "percent"
    value: Decimal

    def to_model(self) -> Json:
        return {"type": self.TYPE, "value": format(self.value, "f")}


@dataclass(frozen=True)
class Channel:
    TYPE: ClassVar[str] = "channel"
    kind: str
    value: str

    def to_model(self) -> Json:
        return {"type": self.TYPE, "kind": self.kind, "value": self.value}


@dataclass(frozen=True)
class Url:
    TYPE: ClassVar[str] = "url"
    value: str

    def to_model(self) -> Json:
        return {"type": self.TYPE, "value": self.value}


@dataclass(frozen=True)
class Text:
    TYPE: ClassVar[str] = "text"
    value: str

    def to_model(self) -> Json:
        return {"type": self.TYPE, "value": self.value}


@dataclass(frozen=True)
class Passage:
    TYPE: ClassVar[str] = "passage"
    value: str

    def to_model(self) -> Json:
        return {"type": self.TYPE, "value": self.value, "untrusted": True, "trace_only": True}


@dataclass(frozen=True)
class Note:
    TYPE: ClassVar[str] = "note"
    value: str

    def to_model(self) -> Json:
        return {"type": self.TYPE, "value": self.value, "untrusted": True}


@dataclass(frozen=True)
class Ref:
    TYPE: ClassVar[str] = "ref"
    kind: str
    value: str

    def to_model(self) -> Json:
        return {"type": self.TYPE, "kind": self.kind, "value": self.value, "trace_only": True}


@dataclass(frozen=True)
class Refs:
    TYPE: ClassVar[str] = "refs"
    kind: str
    values: tuple[str, ...]

    def to_model(self) -> Json:
        return {"type": self.TYPE, "kind": self.kind, "values": list(self.values), "trace_only": True}


@dataclass(frozen=True)
class FactIds:
    TYPE: ClassVar[str] = "ids"
    values: tuple[str, ...]

    def to_model(self) -> Json:
        return {"type": self.TYPE, "values": list(self.values), "trace_only": True}


@dataclass(frozen=True)
class Flag:
    TYPE: ClassVar[str] = "flag"
    value: bool

    def to_model(self) -> Json:
        return {"type": self.TYPE, "value": self.value, "trace_only": True}


@dataclass(frozen=True)
class Trace:
    TYPE: ClassVar[str] = "trace"
    value: str | tuple[str, ...]

    def to_model(self) -> Json:
        value = list(self.value) if isinstance(self.value, tuple) else self.value
        return {"type": self.TYPE, "value": value, "trace_only": True}


Value = (
    Money
    | Day
    | Instant
    | Period
    | Count
    | Last4
    | Status
    | Label
    | Labels
    | Merchant
    | City
    | Country
    | CaseCode
    | Ratio
    | Percent
    | Channel
    | Url
    | Text
    | Passage
    | Note
    | Ref
    | Refs
    | FactIds
    | Flag
    | Trace
)

TRACE_ONLY: tuple[type, ...] = (Ref, Refs, FactIds, Flag, Trace, Passage)
POLICY_CHUNK = "policy_chunk"


@dataclass(frozen=True)
class Fact:
    id: str
    kind: str
    fields: dict[str, Value]

    def to_model(self) -> Json:
        return {"id": self.id, "kind": self.kind, "fields": {k: v.to_model() for k, v in self.fields.items()}}


@dataclass
class Ledger:
    country: str
    now: datetime
    facts: dict[str, Fact] = field(default_factory=dict)

    @property
    def today(self) -> date:
        return self.now.astimezone(zone(self.country)).date()

    def add(self, kind: str, fields: dict[str, Value | None], prefix: str = "f") -> Fact:
        taken = sum(1 for fact_id in self.facts if fact_id.startswith(prefix))
        fact = Fact(
            id=f"{prefix}{taken + 1}",
            kind=kind,
            fields={name: value for name, value in fields.items() if value is not None},
        )
        self.facts[fact.id] = fact
        return fact

    def get(self, fact_id: str) -> Fact | None:
        return self.facts.get(fact_id)

    def values(self) -> list[Value]:
        return [value for fact in self.facts.values() for value in fact.fields.values()]

    def refs(self) -> set[str]:
        found: set[str] = set()
        for value in self.values():
            if isinstance(value, Ref):
                found.add(value.value)
            elif isinstance(value, Refs):
                found.update(value.values)
        return found

    def chunks(self) -> dict[str, Fact]:
        found: dict[str, Fact] = {}
        for fact in self.facts.values():
            chunk_id = fact.fields.get("chunk_id")
            if fact.kind == POLICY_CHUNK and isinstance(chunk_id, Trace) and isinstance(chunk_id.value, str):
                found[chunk_id.value] = fact
        return found

    def merchants(self) -> set[str]:
        return {value.value for value in self.values() if isinstance(value, Merchant)}

    def payload(self, ids: tuple[str, ...] | list[str] | None = None) -> list[Json]:
        chosen = self.facts if ids is None else {fact_id: self.facts[fact_id] for fact_id in ids}
        return [fact.to_model() for fact in chosen.values()]
