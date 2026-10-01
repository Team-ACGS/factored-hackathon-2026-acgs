from typing import Literal

from pydantic import Field

from core.facts.values import Count, Day, FactIds, Flag, Label, Ledger, Merchant, Note, Ref, Trace, Value
from core.memory import Memory, memory_key
from core.merchants import matches_merchant
from core.tools.context import ToolContext, instant
from core.tools.inputs import Input

MAX_MEMORIES = 10
MAX_READ = 200


class RecallInput(Input):
    transaction_ref: str | None = None
    merchant: str | None = Field(None, min_length=1, max_length=80)
    type: Literal["recognized_charge", "recognized_merchant"] | None = None


def recall(context: ToolContext, ledger: Ledger, args: RecallInput) -> list[str]:
    memory = Memory.from_dynamodb(context.dynamodb())
    more = False
    if args.transaction_ref is not None:
        found = memory.memory(context.customer_id, memory_key("recognized_charge", args.transaction_ref))
        items = [found] if found else []
    else:
        kind = args.type or ("recognized_merchant" if args.merchant else None)
        items, more = memory.memories(context.customer_id, f"{kind}#" if kind else "", MAX_READ)
        if args.merchant is not None:
            wanted = args.merchant
            items = [item for item in items if matches_merchant(wanted, str(item.get("subject") or ""))]
    items.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    facts = [ledger.add("memory", _memory_fields(context, item)) for item in items[:MAX_MEMORIES]]
    aggregate = ledger.add(
        "memories",
        {
            "count": Count(len(facts), "memory"),
            "ids": FactIds(tuple(fact.id for fact in facts)),
            "truncated": Flag(more or len(items) > MAX_MEMORIES),
        },
    )
    return [*(fact.id for fact in facts), aggregate.id]


def _memory_fields(context: ToolContext, item: dict[str, object]) -> dict[str, Value | None]:
    kind = str(item.get("type") or "")
    subject = str(item.get("subject") or "")
    return {
        "type": Label("memory_type", kind),
        "transaction_ref": Ref("transaction", subject) if kind == "recognized_charge" else None,
        "merchant": Merchant(subject) if kind == "recognized_merchant" else None,
        "note": Note(str(item["note"])[:140]) if item.get("note") else None,
        "created_at": Day(context.local_day(instant(item["created_at"]))) if item.get("created_at") else None,
        "source_room_id": Trace(str(item["source_room_id"])) if item.get("source_room_id") else None,
    }
