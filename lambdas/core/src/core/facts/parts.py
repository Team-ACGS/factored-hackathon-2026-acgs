from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from core.facts.values import Json


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
    ids: tuple[str, ...]

    def to_wire(self) -> Json:
        return {"type": "view", "view": self.view, "ids": list(self.ids)}


@dataclass(frozen=True)
class Ask:
    ask: str
    target: str | None = None

    def to_wire(self) -> Json:
        return {"type": "ask", "ask": self.ask, "target": self.target}


Part = Say | View | Ask


def parse_parts(raw: Sequence[Mapping[str, Any]]) -> list[Part]:
    return [_parse(item) for item in raw]


def _parse(item: Mapping[str, Any]) -> Part:
    kind = item.get("type")
    if kind == "say" and isinstance(item.get("text"), str):
        return Say(item["text"])
    if kind == "view" and isinstance(item.get("view"), str) and _strings(item.get("ids")):
        return View(item["view"], tuple(item["ids"]))
    target = item.get("target")
    if kind == "ask" and isinstance(item.get("ask"), str) and (target is None or isinstance(target, str)):
        return Ask(item["ask"], target)
    raise InvalidPart(f"not a say, view or ask part: {kind!r}")


def _strings(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(entry, str) for entry in value)
