from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from core.accounts import Accounts, card_type
from core.facts.values import (
    City,
    Country,
    Instant,
    Label,
    Last4,
    Merchant,
    Money,
    Ref,
    Status,
    Value,
)
from core.tools.context import MAX_CARDS, MAX_ROWS, NotFound, ToolContext, decimal, instant

CARD_FIELDS = (
    "product_id",
    "product_type",
    "product_number",
    "currency",
    "product_status",
)
BALANCE_FIELDS = ("current_balance", "credit_limit", "balance_as_of")

MOVEMENT_FIELDS = (
    "transaction_id",
    "product_id",
    "transaction_date",
    "amount",
    "currency",
    "merchant_name",
    "transaction_status",
    "channel",
    "transaction_country",
    "transaction_city",
    "transaction_category",
)

SPENDING = frozenset({"Approved", "Pending"})


@dataclass(frozen=True)
class Card:
    product_id: str
    type: str
    last4: str
    currency: str
    status: str


@dataclass(frozen=True)
class Movement:
    transaction_id: str
    product_id: str
    at: datetime
    amount: Decimal
    currency: str
    merchant: str
    status: str
    channel: str | None
    country: str | None
    city: str | None
    category: str | None


def to_card(item: dict[str, Any]) -> Card | None:
    kind = card_type(item.get("product_type"))
    if kind is None:
        return None
    digits = "".join(char for char in str(item.get("product_number") or "") if char.isdigit())
    return Card(
        product_id=str(item["product_id"]),
        type=kind,
        last4=digits[-4:],
        currency=str(item.get("currency") or ""),
        status=str(item.get("product_status") or ""),
    )


def to_movement(item: dict[str, Any]) -> Movement:
    return Movement(
        transaction_id=str(item["transaction_id"]),
        product_id=str(item["product_id"]),
        at=instant(item["transaction_date"]),
        amount=decimal(item["amount"]),
        currency=str(item.get("currency") or ""),
        merchant=str(item.get("merchant_name") or ""),
        status=str(item.get("transaction_status") or ""),
        channel=item.get("channel"),
        country=item.get("transaction_country"),
        city=item.get("transaction_city"),
        category=item.get("transaction_category"),
    )


class Reader:
    def __init__(self, context: ToolContext) -> None:
        self.context = context
        self.accounts = Accounts.from_dynamodb(context.dynamodb())

    def cards(self, extra: Sequence[str] = ()) -> list[Card]:
        items = self.accounts.cards(self.context.customer_id, (*CARD_FIELDS, *extra))
        return [card for card in map(to_card, items) if card is not None]

    def cards_for(self, card_ref: str | None) -> list[Card]:
        cards = self.cards()
        if card_ref is None:
            return cards
        chosen = [card for card in cards if card.product_id == card_ref]
        if not chosen:
            raise NotFound(card_ref)
        return chosen

    def movements(
        self,
        cards: Sequence[Card],
        start: date,
        end: date,
        fields: Sequence[str] = MOVEMENT_FIELDS,
    ) -> tuple[list[Movement], bool]:
        lower = self.context.day_start(start)
        upper = self.context.day_start(end + timedelta(days=1))
        truncated = len(cards) > MAX_CARDS
        rows: list[Movement] = []
        for card in cards[:MAX_CARDS]:
            remaining = MAX_ROWS - len(rows)
            if remaining <= 0:
                return rows, True
            items, more = self.accounts.transactions_between(
                self.context.customer_id, card.product_id, lower, upper, fields, remaining
            )
            rows.extend(to_movement(item) for item in items)
            truncated = truncated or more
        return rows, truncated


def movement_fields(movement: Movement, card: Card | None) -> dict[str, Value | None]:
    return {
        "transaction_ref": Ref("transaction", movement.transaction_id),
        "card_ref": Ref("card", movement.product_id),
        "last4": Last4(card.last4) if card else None,
        "date": Instant(movement.at),
        "merchant": Merchant(movement.merchant),
        "amount": Money(movement.amount, movement.currency),
        "status": Status("transaction", movement.status),
        "channel": Label("channel", movement.channel) if movement.channel else None,
        "city": City(movement.city) if movement.city else None,
        "country": Country(movement.country) if movement.country else None,
        "category": Label("category", movement.category) if movement.category else None,
    }


def counts_as_spending(movement: Movement) -> bool:
    return movement.status in SPENDING
