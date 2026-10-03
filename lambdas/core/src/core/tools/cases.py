from typing import Any

from core.accounts import Accounts
from core.cases import OPEN_STAGES, Cases, case_code, case_type, stage
from core.facts.values import (
    CaseCode,
    Count,
    Day,
    FactIds,
    Flag,
    Instant,
    Label,
    Last4,
    Ledger,
    Merchant,
    Money,
    Note,
    Ref,
    Status,
    Trace,
    Value,
)
from core.tools.context import NotFound, ToolContext, decimal, instant
from core.tools.inputs import Input
from core.tools.reads import CARD_FIELDS, to_card

MAX_CASES = 10
MAX_READ = 100
CHARGE_FIELDS = ("transaction_id", "product_id", "amount", "currency", "merchant_name")
REACHED_AT = {"in_review": ("in_review", "resolved", "closed"), "resolved": ("resolved", "closed")}


class CaseStatusInput(Input):
    case_ref: str | None = None
    transaction_ref: str | None = None


def case_status(context: ToolContext, ledger: Ledger, args: CaseStatusInput) -> list[str]:
    dynamodb = context.dynamodb()
    cases = Cases.from_dynamodb(dynamodb)
    if args.case_ref is not None:
        found = cases.case(context.customer_id, args.case_ref)
        if found is None:
            raise NotFound(args.case_ref)
        selected, more = [found], False
    else:
        items, more = cases.cases(context.customer_id, MAX_READ)
        if args.transaction_ref is not None:
            selected = [item for item in items if item.get("transaction_id") == args.transaction_ref]
        else:
            selected = [item for item in items if stage(item) in OPEN_STAGES]
    selected.sort(key=lambda item: str(item.get("creation_date") or ""), reverse=True)
    accounts = Accounts.from_dynamodb(dynamodb)
    rows = [_case_fields(context, accounts, item) for item in selected[:MAX_CASES]]
    for item in selected[:MAX_CASES]:
        if item.get("transaction_id") and item.get("product_id"):
            ledger.locate(str(item["transaction_id"]), str(item["product_id"]))
    facts = [ledger.add("case", fields) for fields in rows]
    aggregate = ledger.add(
        "cases",
        {
            "count": Count(len(facts), "case"),
            "ids": FactIds(tuple(fact.id for fact in facts)),
            "truncated": Flag(more or len(selected) > MAX_CASES),
        },
    )
    return [*(fact.id for fact in facts), aggregate.id]


def next_step(kind: str, current: str) -> str:
    if current in ("resolved", "closed"):
        return "resolution_sent"
    if kind == "fraud" and current in ("opened", "assigned"):
        return "fraud_team_contacts_you"
    return "review_in_progress"


def _case_fields(context: ToolContext, accounts: Accounts, item: dict[str, Any]) -> dict[str, Value | None]:
    opened = str(item.get("creation_date") or "")
    kind = case_type(item.get("area"))
    current = stage(item)
    fields: dict[str, Value | None] = {
        "case_ref": Ref("case", str(item["complaint_id"])),
        "case_id": CaseCode(case_code(str(item["complaint_id"]), opened)),
        "type": Label("case_type", kind),
        "stage": Status("stage", current),
        "opened_at": _day(context, opened),
        "assigned_at": _day(context, item.get("assignment_date")),
        "in_review_at": _day(context, item.get("first_response_date"))
        if current in REACHED_AT["in_review"]
        else None,
        "resolved_at": _day(context, item.get("resolution_date"))
        if current in REACHED_AT["resolved"]
        else None,
        "next_step": Label("next_step", next_step(kind, current)),
        "summary": Note(str(item["summary"])) if item.get("summary") else None,
        "summary_points": (
            Trace(tuple(map(str, item["summary_points"]))) if item.get("summary_points") else None
        ),
        "summary_language": Trace(str(item["summary_language"])) if item.get("summary_language") else None,
        "summary_generated_at": Instant(instant(item["summary_generated_at"]))
        if item.get("summary_generated_at")
        else None,
        "summary_source": Trace(str(item["summary_source"])) if item.get("summary_source") else None,
    }
    fields.update(_disputed(context, accounts, item))
    return fields


def _disputed(context: ToolContext, accounts: Accounts, item: dict[str, Any]) -> dict[str, Value | None]:
    transaction_id, product_id = item.get("transaction_id"), item.get("product_id")
    if not transaction_id or not product_id:
        return {}
    charge = accounts.transaction(context.customer_id, str(product_id), str(transaction_id), CHARGE_FIELDS)
    if charge is None:
        return {"transaction_ref": Ref("transaction", str(transaction_id))}
    card_item = accounts.card(context.customer_id, str(product_id), CARD_FIELDS)
    card = to_card(card_item) if card_item else None
    return {
        "transaction_ref": Ref("transaction", str(transaction_id)),
        "merchant": Merchant(str(charge["merchant_name"])),
        "amount": Money(decimal(charge["amount"]), str(charge["currency"])),
        "last4": Last4(card.last4) if card else None,
    }


def _day(context: ToolContext, value: object) -> Day | None:
    return Day(context.local_day(instant(value))) if value else None
