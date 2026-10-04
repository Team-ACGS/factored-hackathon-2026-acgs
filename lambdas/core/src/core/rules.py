from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from core.access import customer_session
from core.accounts import Accounts
from core.facts.targets import ANSWER_OPTIONS, MIN_OPTIONS, candidate, recognizable, show_option
from core.facts.values import Fact, Labels, Ledger, Ref, Status
from core.ids import format_instant
from core.memory import MAX_NOTE, Memory, memory_key
from core.merchants import merchant_key
from core.messaging import Message
from core.router import floor, short_answer

RECOGNIZE = "recognize_charge"
WAS_IT_YOU = "was_it_you"
HAVE_CARD = "have_card"
BLOCK = "block_card"
CLAIM = "open_claim"
PERSON = "talk_to_person"
SAY_KEY = "say_key"
STORY_ASKS = frozenset({RECOGNIZE, WAS_IT_YOU, HAVE_CARD, BLOCK, CLAIM, PERSON})
ABOUT_THE_CHARGE = frozenset({RECOGNIZE, WAS_IT_YOU})
WRITES = frozenset({BLOCK, CLAIM, PERSON})
PROTECT_REASONS = frozenset({"foreign_country", "unusual_channel"})
MERCHANT_AFTER = 3
MAX_CHARGE_MEMORIES = 500

AnsweredBy = Literal["tap", "lexicon", "floor", "graph"]
Closed = Literal["written", "redelivered", "already", "missing"]
Purpose = Literal["lost", "not_me"]


@dataclass(frozen=True)
class Choice:
    ask: str
    option: str
    read: Mapping[str, Any]
    recent: bool = False
    purpose: str | None = None


@dataclass(frozen=True)
class Target:
    product_id: str | None
    transaction_id: str | None = None
    reason: str | None = None
    area: str | None = None
    complaint_id: str | None = None

    def to_wire(self) -> dict[str, str]:
        return {name: value for name, value in self.__dict__.items() if value is not None}


@dataclass(frozen=True)
class OpenAsk:
    ask_id: str
    ask: str
    target: Target


@dataclass(frozen=True)
class Answer:
    ask: OpenAsk
    option: str
    note: str | None
    by: AnsweredBy


@dataclass(frozen=True)
class Closing:
    answer: Answer
    outcome: Closed
    merchant_learned: bool = False
    earlier: str | None = None


@dataclass(frozen=True)
class TurnState:
    choice: str | None = None
    asking: str | None = None
    open_cases: frozenset[str] = frozenset()
    said_key: str | None = None
    open_charge: str | None = None
    answerable: bool = False


def allowed_asks(state: TurnState, ledger: Ledger) -> frozenset[str]:
    if state.asking is not None:
        return frozenset({state.asking})
    allowed: set[str] = {PERSON}
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
    if len(charges) == 1:
        asked = story_ask(charges[0])
        if asked is not None:
            allowed.add(asked)
        if claimable(charges[0], state.open_cases):
            allowed.add(CLAIM)
    return frozenset(allowed)


def flagged(fact: Fact) -> bool:
    reasons = fact.fields.get("verdict.reasons")
    return isinstance(reasons, Labels) and "score_high" in reasons.values


def card_active(fact: Fact) -> bool:
    return fact.fields.get("card.status") == Status("card", "Active")


def story_ask(fact: Fact | None) -> str | None:
    if fact is None or fact.kind != "charge" or "memory.type" in fact.fields:
        return None
    if recognizable(fact):
        return RECOGNIZE
    return WAS_IT_YOU if flagged(fact) and card_active(fact) else None


def claimable(fact: Fact, open_cases: frozenset[str]) -> bool:
    transaction = fact.fields.get("charge.transaction_ref")
    return (
        fact.kind == "charge"
        and not flagged(fact)
        and card_active(fact)
        and isinstance(transaction, Ref)
        and transaction.value not in open_cases
    )


def protect_signals(fact: Fact) -> bool:
    reasons = fact.fields.get("verdict.reasons")
    named = isinstance(reasons, Labels) and bool(PROTECT_REASONS & set(reasons.values))
    return named or flagged(fact) or fact.fields.get("charge.status") == Status("transaction", "Declined")


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
                return Choice(
                    str(part["ask"]),
                    str(option["id"]),
                    option["read"],
                    bool(part.get("recent")),
                    str(part["purpose"]) if part.get("purpose") else None,
                )
    return None


def said_key(asked: Message | None) -> str | None:
    for part in asked.draft if asked else ():
        if part.get("type") == SAY_KEY:
            return str(part.get("key"))
    return None


def open_ask(asked: Message | None) -> OpenAsk | None:
    if asked is None:
        return None
    for part in asked.draft:
        target = part.get("target")
        if part.get("type") == "ask" and part.get("ask") in STORY_ASKS and isinstance(target, Mapping):
            return OpenAsk(asked.message_id, str(part["ask"]), _target(target))
    return None


def _target(value: Mapping[str, Any]) -> Target:
    def text(name: str) -> str | None:
        return str(value[name]) if value.get(name) else None

    return Target(
        text("product_id"), text("transaction_id"), text("reason"), text("area"), text("complaint_id")
    )


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
        if tap["ask_id"] != asked.ask_id or option not in ANSWER_OPTIONS[asked.ask]:
            return None
        return Answer(asked, str(option), _note(tap.get("note")), "tap")
    if "topic" in tap:
        return None
    hit = floor(message.text)
    if hit == "not_me" and asked.ask in ABOUT_THE_CHARGE:
        return Answer(asked, "no", None, "floor")
    if hit is not None:
        return None
    short = short_answer(message.text)
    if short is None or (asked.ask in WRITES and short[1]):
        return None
    return Answer(asked, short[0], _note(short[1]), "lexicon")


def remember_answer(
    customer_id: str,
    ask_id: str,
    target: Target,
    recognized: bool,
    note: str | None,
    room_id: str,
    now: datetime,
) -> tuple[Closed, bool, str | None]:
    if target.product_id is None or target.transaction_id is None:
        return "missing", False, None
    session = customer_session(customer_id, "chatbot").dynamodb
    row = Accounts.from_dynamodb(session).transaction(customer_id, target.product_id, target.transaction_id)
    if row is None:
        return "missing", False, None
    memory = Memory.from_dynamodb(session)
    earlier = memory.of_charge(customer_id, target.transaction_id)
    if earlier is not None and earlier.get("ask_id") != ask_id:
        return "already", False, str(earlier.get("type"))
    kind = "recognized_charge" if recognized else "unrecognized_charge"
    created_at = format_instant(now)
    stored, created = memory.remember(
        customer_id,
        {
            "memory_key": memory_key(kind, target.transaction_id),
            "type": kind,
            "subject": target.transaction_id,
            "note": note,
            "source_room_id": room_id,
            "created_at": created_at,
            "ask_id": ask_id,
            "merchant": row["merchant_name"],
            "product_id": target.product_id,
            "amount": Decimal(str(row["amount"])),
            "currency": row["currency"],
            "charged_at": row["transaction_date"],
        },
    )
    if not created and stored.get("ask_id") != ask_id:
        return "already", False, str(stored.get("type"))
    learned = recognized and _learn_merchant(
        memory, customer_id, room_id, str(row["merchant_name"]), ask_id, created_at
    )
    return ("written" if created else "redelivered"), learned, None


def close_ask(answer: Answer, message: Message, now: datetime) -> Closing:
    outcome, learned, earlier = remember_answer(
        message.customer_id,
        answer.ask.ask_id,
        answer.ask.target,
        answer.option == "yes",
        answer.note,
        message.room_id,
        now,
    )
    return Closing(answer, outcome, learned, earlier)


def _learn_merchant(
    memory: Memory, customer_id: str, room_id: str, merchant: str, ask_id: str, created_at: str
) -> bool:
    key = merchant_key(merchant)
    charges, _ = memory.memories(customer_id, "recognized_charge#", MAX_CHARGE_MEMORIES, consistent=True)
    if sum(1 for item in charges if merchant_key(str(item.get("merchant") or "")) == key) < MERCHANT_AFTER:
        return False
    _, created = memory.remember(
        customer_id,
        {
            "memory_key": memory_key("recognized_merchant", key),
            "type": "recognized_merchant",
            "subject": merchant,
            "source_room_id": room_id,
            "created_at": created_at,
            "ask_id": ask_id,
        },
    )
    return created


def answerable(message: Message, asked: OpenAsk | None, abstained: bool) -> bool:
    return asked is not None and asked.ask == RECOGNIZE and "?" not in message.text and not abstained


def graph_answer(message: Message, asked: OpenAsk, option: str) -> Answer:
    return Answer(asked, option, _note(message.text) if option == "yes" else None, "graph")


def _note(value: object) -> str | None:
    text = str(value).strip() if isinstance(value, str) else ""
    return text[:MAX_NOTE] or None
