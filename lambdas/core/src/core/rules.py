from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from core.facts.targets import MIN_OPTIONS, candidate, show_option
from core.facts.values import Ledger
from core.messaging import Message


@dataclass(frozen=True)
class Choice:
    ask: str
    option: str
    read: Mapping[str, Any]


@dataclass(frozen=True)
class TurnState:
    choice: str | None = None


def allowed_asks(state: TurnState, ledger: Ledger) -> frozenset[str]:
    allowed: set[str] = set()
    kinds = Counter(
        found[0] for fact in ledger.facts.values() if (found := candidate(fact, ledger)) is not None
    )
    if state.choice != "which_one" and any(count >= MIN_OPTIONS for count in kinds.values()):
        allowed.add("which_one")
    if state.choice != "show" and any(
        show_option(fact, ledger) is not None for fact in ledger.facts.values()
    ):
        allowed.add("show")
    return frozenset(allowed)


def resolve_choice(message: Message, history: Sequence[Message]) -> Choice | None:
    if not message.input:
        return None
    earlier = [item for item in history if item.message_key < message.message_key]
    asked = next((item for item in reversed(earlier) if item.sender_type == "assistant"), None)
    if asked is None or asked.message_id != message.input.get("ask_id"):
        return None
    for part in asked.draft:
        if part.get("type") != "ask":
            continue
        for option in part.get("options") or []:
            if option.get("id") == message.input.get("option") and isinstance(option.get("read"), Mapping):
                return Choice(str(part["ask"]), str(option["id"]), option["read"])
    return None
