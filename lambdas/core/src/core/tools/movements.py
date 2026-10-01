import base64
import binascii
import hashlib
import json
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from itertools import pairwise
from typing import Literal

from pydantic import Field

from core.facts.lexicon import CATALOG_MERCHANTS
from core.facts.values import (
    Count,
    Day,
    FactIds,
    Flag,
    Label,
    Last4,
    Ledger,
    Merchant,
    Money,
    Period,
    Ref,
    Refs,
    Trace,
    Value,
)
from core.merchants import matches_merchant, merchant_key
from core.months import add_months
from core.tools.context import HISTORY_DAYS, InvalidArgument, ToolContext, median
from core.tools.inputs import Input, PeriodInput
from core.tools.reads import Card, Movement, Reader, counts_as_spending, movement_fields

DEFAULT_DAYS = 30
MAX_RESULTS = 25
MAX_SERIES = 20
CENT = Decimal("0.01")
AMOUNT_BAND = Decimal("0.15")
CADENCES = {"monthly": (26, 35), "weekly": (6, 8)}


class SearchMovementsInput(Input):
    card_ref: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    merchant: str | None = Field(None, min_length=1, max_length=80)
    status: Literal["Approved", "Pending", "Declined", "Reversed"] | None = None
    channel: Literal["POS", "Web", "App"] | None = None
    country: str | None = Field(None, min_length=2, max_length=2)
    category: str | None = Field(None, max_length=40)
    amount_min: Decimal | None = Field(None, ge=0)
    amount_max: Decimal | None = Field(None, ge=0)
    sort: Literal["date_desc", "amount_desc", "amount_asc"] = "date_desc"
    limit: int = Field(10, ge=1, le=MAX_RESULTS)
    cursor: str | None = Field(None, max_length=200)


class MerchantHistoryInput(Input):
    merchant: str = Field(min_length=1, max_length=80)
    card_ref: str | None = None
    months: int = Field(3, ge=1, le=3)


class SpendSummaryInput(Input):
    period: PeriodInput
    compare_period: PeriodInput | None = None
    card_ref: str | None = None
    merchant: str | None = Field(None, min_length=1, max_length=80)


class RecurringChargesInput(Input):
    card_ref: str | None = None


def search_movements(context: ToolContext, ledger: Ledger, args: SearchMovementsInput) -> list[str]:
    end = args.date_to or context.today
    start = args.date_from or end - timedelta(days=DEFAULT_DAYS - 1)
    start, end, clamped_from = _window(context, start, end)
    offset = _decode_cursor(args.cursor, args) if args.cursor else 0
    reader = Reader(context)
    cards = reader.cards_for(args.card_ref)
    rows, scan_truncated = reader.movements(cards, start, end)
    matched = _sorted([row for row in rows if _matches(row, args)], args.sort)
    page = matched[offset : offset + args.limit]
    more = offset + len(page) < len(matched)
    by_id = {card.product_id: card for card in cards}
    facts = [ledger.add("movement", movement_fields(row, by_id.get(row.product_id))) for row in page]
    aggregate = ledger.add(
        "movements",
        {
            "count": Count(len(matched), "movement"),
            "ids": FactIds(tuple(fact.id for fact in facts)),
            "truncated": Flag(more or scan_truncated),
            "cursor": Trace(_encode_cursor(offset + len(page), args)) if more else None,
            "period": Period(start, end),
            "merchant": echoed_merchant(args.merchant, rows),
            "clamped_from": Day(clamped_from) if clamped_from else None,
        },
    )
    return [*(fact.id for fact in facts), aggregate.id]


def merchant_history(context: ToolContext, ledger: Ledger, args: MerchantHistoryInput) -> list[str]:
    start = max(context.window_start, add_months(context.today, -args.months) + timedelta(days=1))
    end = context.today
    reader = Reader(context)
    rows, truncated = reader.movements(reader.cards_for(args.card_ref), start, end)
    bought = [
        row for row in rows if counts_as_spending(row) and matches_merchant(args.merchant, row.merchant)
    ]
    if not bought:
        fact = ledger.add(
            "merchant_history",
            {
                "merchant": echoed_merchant(args.merchant, rows),
                "count": Count(0, "purchase"),
                "period": Period(start, end),
                "truncated": Flag(truncated),
            },
        )
        return [fact.id]
    ids = []
    for currency, group in sorted(_by_currency(bought).items()):
        group.sort(key=lambda row: row.at)
        fact = ledger.add(
            "merchant_history",
            {
                "merchant": Merchant(group[-1].merchant),
                "count": Count(len(group), "purchase"),
                "first_date": Day(context.local_day(group[0].at)),
                "last_date": Day(context.local_day(group[-1].at)),
                "typical_amount": Money(median([row.amount for row in group]).quantize(CENT), currency),
                "ids": Refs("transaction", tuple(row.transaction_id for row in group)),
                "period": Period(start, end),
                "truncated": Flag(truncated),
            },
        )
        ids.append(fact.id)
    return ids


def spend_summary(context: ToolContext, ledger: Ledger, args: SpendSummaryInput) -> list[str]:
    start, end, clamped_from = _window(context, args.period.start, args.period.end)
    reader = Reader(context)
    cards = reader.cards_for(args.card_ref)
    read, truncated = reader.movements(cards, start, end)
    compare_read: list[Movement] = []
    compare_window = None
    if args.compare_period is not None:
        compare_window = _window(context, args.compare_period.start, args.compare_period.end)
        compare_read, compare_truncated = reader.movements(cards, compare_window[0], compare_window[1])
        truncated = truncated or compare_truncated
    current = _spending(read, args.merchant)
    compare = _spending(compare_read, args.merchant)
    echo = echoed_merchant(args.merchant, read + compare_read)
    currencies = {row.currency for row in current + compare} or {card.currency for card in cards}
    ids = []
    for currency in sorted(currencies):
        rows = [row for row in current if row.currency == currency]
        total = sum((row.amount for row in rows), Decimal(0))
        fields: dict[str, Value | None] = {
            "period": Period(start, end),
            "total": Money(total, currency),
            "count": Count(len(rows), "purchase"),
            "pending_total": Money(
                sum((row.amount for row in rows if row.status == "Pending"), Decimal(0)), currency
            ),
            "counted": Label("counted", "approved_and_pending"),
            "partial": Flag(end >= context.today),
            "merchant": echo,
            "clamped_from": Day(clamped_from) if clamped_from else None,
            "truncated": Flag(truncated),
        }
        if compare_window is not None:
            compare_total = sum((row.amount for row in compare if row.currency == currency), Decimal(0))
            fields["compare_period"] = Period(compare_window[0], compare_window[1])
            fields["compare_total"] = Money(compare_total, currency)
            fields["delta"] = Money(abs(total - compare_total), currency)
            fields["direction"] = Label("direction", _direction(total, compare_total))
        ids.append(ledger.add("spend", fields).id)
    return ids


def recurring_charges(context: ToolContext, ledger: Ledger, args: RecurringChargesInput) -> list[str]:
    reader = Reader(context)
    cards = reader.cards_for(args.card_ref)
    rows, scan_truncated = reader.movements(cards, context.window_start, context.today)
    by_id = {card.product_id: card for card in cards}
    series = sorted(
        (found for found in _series(rows, context) if found is not None),
        key=lambda found: found[2][-1].at,
        reverse=True,
    )
    facts = [
        ledger.add("recurring", _series_fields(context, cadence, group, by_id[group[0].product_id]))
        for cadence, _, group in series[:MAX_SERIES]
    ]
    aggregate = ledger.add(
        "recurring_list",
        {
            "count": Count(len(facts), "subscription"),
            "ids": FactIds(tuple(fact.id for fact in facts)),
            "truncated": Flag(scan_truncated or len(series) > MAX_SERIES),
        },
    )
    return [*(fact.id for fact in facts), aggregate.id]


def cadence_of(days: list[date]) -> str | None:
    gaps = [(later - earlier).days for earlier, later in pairwise(days)]
    for cadence, (low, high) in CADENCES.items():
        if gaps and all(low <= gap <= high for gap in gaps):
            return cadence
    return None


def steady_amounts(amounts: list[Decimal]) -> bool:
    middle = median(amounts)
    return all(abs(amount - middle) <= middle * AMOUNT_BAND for amount in amounts)


def _series(rows: list[Movement], context: ToolContext) -> list[tuple[str, str, list[Movement]] | None]:
    groups: dict[tuple[str, str], list[Movement]] = defaultdict(list)
    for row in rows:
        if counts_as_spending(row):
            groups[(row.product_id, merchant_key(row.merchant))].append(row)
    found: list[tuple[str, str, list[Movement]] | None] = []
    for (_, key), group in groups.items():
        group.sort(key=lambda row: row.at)
        cadence = cadence_of([context.local_day(row.at) for row in group])
        if len(group) >= 2 and cadence and steady_amounts([row.amount for row in group]):
            found.append((cadence, key, group))
    return found


def _series_fields(
    context: ToolContext, cadence: str, group: list[Movement], card: Card
) -> dict[str, Value | None]:
    last_day = context.local_day(group[-1].at)
    next_expected = add_months(last_day, 1) if cadence == "monthly" else last_day + timedelta(days=7)
    return {
        "merchant": Merchant(group[-1].merchant),
        "card_ref": Ref("card", card.product_id),
        "last4": Last4(card.last4),
        "cadence": Label("cadence", cadence),
        "typical_amount": Money(median([row.amount for row in group]).quantize(CENT), group[-1].currency),
        "last_date": Day(last_day),
        "next_expected": Day(next_expected),
        "ids": Refs("transaction", tuple(row.transaction_id for row in group)),
    }


def _window(context: ToolContext, start: date, end: date) -> tuple[date, date, date | None]:
    end = min(end, context.today)
    clamped_from = start if start < context.window_start else None
    start = max(start, context.window_start)
    if end < start:
        raise InvalidArgument(f"the period must fall inside the last {HISTORY_DAYS} days, up to today")
    return start, end, clamped_from


def _spending(rows: list[Movement], merchant: str | None) -> list[Movement]:
    return [
        row
        for row in rows
        if counts_as_spending(row) and (merchant is None or matches_merchant(merchant, row.merchant))
    ]


def echoed_merchant(query: str | None, rows: list[Movement]) -> Merchant | Trace | None:
    if query is None:
        return None
    key = merchant_key(query)
    read = [row for row in rows if merchant_key(row.merchant) == key]
    if read:
        return Merchant(max(read, key=lambda row: row.at).merchant)
    known = next((name for name in sorted(CATALOG_MERCHANTS) if merchant_key(name) == key), None)
    return Merchant(known) if known else Trace(query)


def _direction(total: Decimal, compare_total: Decimal) -> str:
    if total > compare_total:
        return "more"
    return "less" if total < compare_total else "same"


def _by_currency(rows: list[Movement]) -> dict[str, list[Movement]]:
    groups: dict[str, list[Movement]] = defaultdict(list)
    for row in rows:
        groups[row.currency].append(row)
    return groups


def _matches(row: Movement, args: SearchMovementsInput) -> bool:
    return (
        (args.merchant is None or matches_merchant(args.merchant, row.merchant))
        and (args.status is None or row.status == args.status)
        and (args.channel is None or row.channel == args.channel)
        and (args.country is None or (row.country or "").upper() == args.country.upper())
        and (args.category is None or (row.category or "").lower() == args.category.lower())
        and (args.amount_min is None or row.amount >= args.amount_min)
        and (args.amount_max is None or row.amount <= args.amount_max)
    )


def _sorted(rows: list[Movement], order: str) -> list[Movement]:
    newest = sorted(rows, key=lambda row: (row.at, row.transaction_id), reverse=True)
    if order == "date_desc":
        return newest
    return sorted(newest, key=lambda row: row.amount, reverse=order == "amount_desc")


def _filters_digest(args: SearchMovementsInput) -> str:
    filters = args.model_dump(mode="json", exclude={"cursor", "limit"})
    return hashlib.sha256(json.dumps(filters, sort_keys=True).encode()).hexdigest()[:16]


def _encode_cursor(offset: int, args: SearchMovementsInput) -> str:
    raw = json.dumps({"o": offset, "f": _filters_digest(args)}, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode_cursor(cursor: str, args: SearchMovementsInput) -> int:
    try:
        decoded = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InvalidArgument("cursor is not readable") from error
    if not isinstance(decoded, dict) or decoded.get("f") != _filters_digest(args):
        raise InvalidArgument("cursor belongs to other filters")
    offset = decoded.get("o")
    if not isinstance(offset, int) or offset < 0:
        raise InvalidArgument("cursor is not readable")
    return offset
