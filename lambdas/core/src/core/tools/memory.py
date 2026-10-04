from typing import Literal

from pydantic import Field

from core.facts.values import (
    Count,
    Day,
    Fact,
    FactIds,
    Flag,
    Instant,
    Label,
    Ledger,
    Merchant,
    Money,
    Note,
    Ref,
    Trace,
    Value,
)
from core.memory import MAX_NOTE, Memory
from core.merchants import matches_merchant
from core.tools.context import ToolContext, decimal, instant
from core.tools.inputs import Input

MAX_MEMORIES = 10
MAX_READ = 200


class RecallInput(Input):
    transaction_ref: str | None = None
    merchant: str | None = Field(None, min_length=1, max_length=80)
    type: Literal["recognized_charge", "unrecognized_charge", "recognized_merchant"] | None = None


def recall(context: ToolContext, ledger: Ledger, args: RecallInput) -> list[str]:
    memory = Memory.from_dynamodb(context.dynamodb())
    more = False
    if args.transaction_ref is not None:
        found = memory.of_charge(context.customer_id, args.transaction_ref)
        items = [found] if found else []
    else:
        kind = args.type or ("recognized_merchant" if args.merchant else None)
        items, more = memory.memories(context.customer_id, f"{kind}#" if kind else "", MAX_READ)
        if args.merchant is not None:
            wanted = args.merchant
            items = [item for item in items if matches_merchant(wanted, merchant_of(item))]
    facts = [remember_fact(context, ledger, item) for item in newest(items)[:MAX_MEMORIES]]
    aggregate = ledger.add(
        "memories",
        {
            "count": Count(len(facts), "memory"),
            "ids": FactIds(tuple(fact.id for fact in facts)),
            "truncated": Flag(more or len(items) > MAX_MEMORIES),
        },
    )
    return [*(fact.id for fact in facts), aggregate.id]


def newest(items: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(items, key=lambda item: str(item.get("created_at") or ""), reverse=True)


def merchant_of(item: dict[str, object]) -> str:
    field = "subject" if item.get("type") == "recognized_merchant" else "merchant"
    return str(item.get(field) or "")


def remember_fact(context: ToolContext, ledger: Ledger, item: dict[str, object]) -> Fact:
    charge = item.get("type") != "recognized_merchant"
    if charge and item.get("product_id"):
        ledger.locate(str(item["subject"]), str(item["product_id"]))
    return ledger.add("memory", _memory_fields(context, item, charge))


def _memory_fields(context: ToolContext, item: dict[str, object], charge: bool) -> dict[str, Value | None]:
    subject = str(item.get("subject") or "")
    merchant = item.get("merchant") if charge else subject
    amount, currency = item.get("amount"), item.get("currency")
    return {
        "type": Label("memory_type", str(item.get("type") or "")),
        "transaction_ref": Ref("transaction", subject) if charge else None,
        "merchant": Merchant(str(merchant)) if merchant else None,
        "amount": Money(decimal(amount), str(currency)) if charge and amount and currency else None,
        "date": Instant(instant(item["charged_at"])) if charge and item.get("charged_at") else None,
        "note": Note(str(item["note"])[:MAX_NOTE]) if item.get("note") else None,
        "created_at": Day(context.local_day(instant(item["created_at"]))) if item.get("created_at") else None,
        "source_room_id": Trace(str(item["source_room_id"])) if item.get("source_room_id") else None,
    }
