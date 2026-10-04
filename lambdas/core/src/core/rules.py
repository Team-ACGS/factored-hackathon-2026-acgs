from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from core.access import customer_session
from core.accounts import Accounts
from core.facts.targets import MIN_OPTIONS, candidate, recognizable, show_option
from core.facts.values import Fact, Ledger
from core.ids import format_instant
from core.memory import MAX_NOTE, Memory, memory_key
from core.merchants import merchant_key
from core.messaging import Message
from core.router import ShortAnswer, floor, short_answer

RECOGNIZE = "recognize_charge"
MERCHANT_AFTER = 3
MAX_CHARGE_MEMORIES = 500

AnsweredBy = Literal["tap", "lexicon", "floor"]
Closed = Literal["written", "redelivered", "already", "missing"]


@dataclass(frozen=True)
class Choice:
    ask: str
    option: str
    read: Mapping[str, Any]
    recent: bool = False


@dataclass(frozen=True)
class Target:
    product_id: str
    transaction_id: str


@dataclass(frozen=True)
class OpenAsk:
    ask_id: str
    ask: str
    target: Target


@dataclass(frozen=True)
class Answer:
    ask: OpenAsk
    option: ShortAnswer
    note: str | None
    by: AnsweredBy


@dataclass(frozen=True)
class Closing:
    answer: Answer
    outcome: Closed
    merchant_learned: bool = False


@dataclass(frozen=True)
class TurnState:
    choice: str | None = None
    asking: str | None = None


def allowed_asks(state: TurnState, ledger: Ledger) -> frozenset[str]:
    if state.asking is not None:
        return frozenset({state.asking})
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
    charges = [fact for fact in ledger.facts.values() if fact.kind == "charge"]
    if len(charges) == 1 and recognizable(charges[0]):
        allowed.add(RECOGNIZE)
    return frozenset(allowed)


def asks_to_recognize(fact: Fact | None) -> bool:
    return fact is not None and fact.kind == "charge" and recognizable(fact)


def latest_reply(message: Message, history: Sequence[Message]) -> Message | None:
    earlier = [item for item in history if item.message_key < message.message_key]
    return next((item for item in reversed(earlier) if item.sender_type == "assistant"), None)


def resolve_choice(message: Message, asked: Message | None) -> Choice | None:
    if not message.input or asked is None or asked.message_id != message.input.get("ask_id"):
        return None
    for part in asked.draft:
        if part.get("type") != "ask":
            continue
        for option in part.get("options") or []:
            if option.get("id") == message.input.get("option") and isinstance(option.get("read"), Mapping):
                return Choice(str(part["ask"]), str(option["id"]), option["read"], bool(part.get("recent")))
    return None


def open_ask(asked: Message | None) -> OpenAsk | None:
    if asked is None:
        return None
    for part in asked.draft:
        target = part.get("target")
        if part.get("type") == "ask" and part.get("ask") == RECOGNIZE and isinstance(target, Mapping):
            return OpenAsk(
                asked.message_id, RECOGNIZE, Target(str(target["product_id"]), str(target["transaction_id"]))
            )
    return None


def topic_of(message: Message) -> Target | None:
    topic = (message.input or {}).get("topic")
    if isinstance(topic, Mapping) and topic.get("type") == "charge":
        return Target(str(topic["product_id"]), str(topic["transaction_id"]))
    return None


def answer_of(message: Message, asked: OpenAsk | None) -> Answer | None:
    if asked is None:
        return None
    tap = message.input or {}
    if "ask_id" in tap:
        option = tap.get("option")
        if tap["ask_id"] != asked.ask_id or option not in ("yes", "no"):
            return None
        return Answer(asked, option, _note(tap.get("note")), "tap")
    if "topic" in tap:
        return None
    hit = floor(message.text)
    if hit == "not_me":
        return Answer(asked, "no", None, "floor")
    if hit is not None:
        return None
    short = short_answer(message.text)
    return Answer(asked, short[0], _note(short[1]), "lexicon") if short else None


def close_ask(answer: Answer, message: Message, now: datetime, service: str) -> Closing:
    session = customer_session(message.customer_id, service).dynamodb
    target = answer.ask.target
    row = Accounts.from_dynamodb(session).transaction(
        message.customer_id, target.product_id, target.transaction_id
    )
    if row is None:
        return Closing(answer, "missing")
    memory = Memory.from_dynamodb(session)
    earlier = memory.of_charge(message.customer_id, target.transaction_id)
    if earlier is not None and earlier.get("ask_id") != answer.ask.ask_id:
        return Closing(answer, "already")
    kind = "recognized_charge" if answer.option == "yes" else "unrecognized_charge"
    created_at = format_instant(now)
    stored, created = memory.remember(
        message.customer_id,
        {
            "memory_key": memory_key(kind, target.transaction_id),
            "type": kind,
            "subject": target.transaction_id,
            "note": answer.note,
            "source_room_id": message.room_id,
            "created_at": created_at,
            "ask_id": answer.ask.ask_id,
            "merchant": row["merchant_name"],
            "product_id": target.product_id,
            "amount": Decimal(str(row["amount"])),
            "currency": row["currency"],
            "charged_at": row["transaction_date"],
        },
    )
    if not created and stored.get("ask_id") != answer.ask.ask_id:
        return Closing(answer, "already")
    learned = kind == "recognized_charge" and _learn_merchant(
        memory, message, str(row["merchant_name"]), answer.ask.ask_id, created_at
    )
    return Closing(answer, "written" if created else "redelivered", learned)


def _learn_merchant(memory: Memory, message: Message, merchant: str, ask_id: str, created_at: str) -> bool:
    key = merchant_key(merchant)
    charges, _ = memory.memories(
        message.customer_id, "recognized_charge#", MAX_CHARGE_MEMORIES, consistent=True
    )
    if sum(1 for item in charges if merchant_key(str(item.get("merchant") or "")) == key) < MERCHANT_AFTER:
        return False
    _, created = memory.remember(
        message.customer_id,
        {
            "memory_key": memory_key("recognized_merchant", key),
            "type": "recognized_merchant",
            "subject": merchant,
            "source_room_id": message.room_id,
            "created_at": created_at,
            "ask_id": ask_id,
        },
    )
    return created


def _note(value: object) -> str | None:
    text = str(value).strip() if isinstance(value, str) else ""
    return text[:MAX_NOTE] or None
