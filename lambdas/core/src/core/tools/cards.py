from datetime import date

from pydantic import Field

from core.facts.values import (
    Count,
    Day,
    FactIds,
    Flag,
    Instant,
    Label,
    Last4,
    Ledger,
    Money,
    Ref,
    Status,
    Trace,
    Value,
)
from core.ids import InvalidId, parse_uuid7
from core.tools.context import NotFound, ToolContext, decimal, instant
from core.tools.inputs import Input
from core.tools.reads import BALANCE_FIELDS, CARD_FIELDS, Card, Reader, to_card

MAX_CARDS_LISTED = 10


class ListCardsInput(Input):
    pass


class CardStatusInput(Input):
    card_ref: str = Field(description="product_id of one of the customer's cards")


def list_cards(context: ToolContext, ledger: Ledger, args: ListCardsInput) -> list[str]:
    cards = Reader(context).cards()
    rows = [ledger.add("card", card_fields(card)) for card in cards[:MAX_CARDS_LISTED]]
    aggregate = ledger.add(
        "cards",
        {
            "count": Count(len(rows), "card"),
            "credit": Count(sum(card.type == "credit" for card in cards), "credit_card"),
            "debit": Count(sum(card.type == "debit" for card in cards), "debit_card"),
            "ids": FactIds(tuple(row.id for row in rows)),
            "truncated": Flag(len(cards) > MAX_CARDS_LISTED),
        },
    )
    return [*(row.id for row in rows), aggregate.id]


def card_status(context: ToolContext, ledger: Ledger, args: CardStatusInput) -> list[str]:
    try:
        parse_uuid7(args.card_ref)
    except InvalidId as error:
        raise NotFound(args.card_ref) from error
    reader = Reader(context)
    item = reader.accounts.card(
        context.customer_id, args.card_ref, (*CARD_FIELDS, *BALANCE_FIELDS, "blocked_at")
    )
    card = to_card(item) if item else None
    if card is None:
        raise NotFound(args.card_ref)
    fields = card_fields(card)
    if card.status == "Blocked":
        fields["blocked_by_clara"] = Flag(bool(item and item.get("blocked_at")))
    as_of = item.get("balance_as_of") if item else None
    fields["balance_available"] = Flag(as_of is not None)
    if as_of is not None and item is not None:
        balance = decimal(item.get("current_balance") or 0)
        fields["current_balance"] = Money(balance, card.currency)
        fields["balance_as_of"] = Instant(instant(as_of))
        if card.type == "credit" and item.get("credit_limit") is not None:
            limit = decimal(item["credit_limit"])
            fields["credit_limit"] = Money(limit, card.currency)
            fields["available"] = Money(limit - balance, card.currency)
    return [ledger.add("card", fields).id]


def card_fields(card: Card) -> dict[str, Value | None]:
    return {
        "card_ref": Ref("card", card.product_id),
        "type": Label("card_type", card.type),
        "last4": Last4(card.last4),
        "currency": Trace(card.currency),
        "status": Status("card", card.status),
        "expiration_date": Day(date.fromisoformat(card.expiration_date)) if card.expiration_date else None,
    }
