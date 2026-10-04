from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, get_args

from core.facts.values import Json

ViewType = Literal["movements", "cards", "card", "movement", "charge", "history", "case"]
AskType = Literal["which_one", "show", "recognize_charge"]
VIEW_TYPES: tuple[str, ...] = get_args(ViewType)
ASK_TYPES: tuple[str, ...] = get_args(AskType)


class InvalidPart(ValueError):
    pass


@dataclass(frozen=True)
class Say:
    text: str

    def to_wire(self) -> Json:
        return {"type": "say", "text": self.text}


@dataclass(frozen=True)
class View:
    view: str
    facts: tuple[str, ...]

    def to_wire(self) -> Json:
        return {"type": "view", "view": self.view, "facts": list(self.facts)}


@dataclass(frozen=True)
class Ask:
    ask: str
    facts: tuple[str, ...]

    def to_wire(self) -> Json:
        return {"type": "ask", "ask": self.ask, "facts": list(self.facts)}


Part = Say | View | Ask


def parse_parts(raw: Sequence[Mapping[str, Any]]) -> list[Part]:
    return [_parse(item) for item in raw]


def _parse(item: Mapping[str, Any]) -> Part:
    kind = item.get("type")
    if kind == "say" and isinstance(item.get("text"), str):
        return Say(item["text"])
    if kind == "view" and isinstance(item.get("view"), str) and _strings(item.get("facts")):
        return View(item["view"], tuple(item["facts"]))
    if kind == "ask" and isinstance(item.get("ask"), str) and _strings(item.get("facts")):
        return Ask(item["ask"], tuple(item["facts"]))
    raise InvalidPart(f"not a say, view or ask part: {kind!r}")


def _strings(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(entry, str) for entry in value)
