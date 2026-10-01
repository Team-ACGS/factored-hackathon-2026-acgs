from datetime import timedelta
from decimal import Decimal

from pydantic import Field

from core.facts.values import (
    City,
    Count,
    Country,
    Day,
    FactIds,
    Flag,
    Instant,
    Label,
    Labels,
    Last4,
    Ledger,
    Merchant,
    Money,
    Ratio,
    Ref,
    Status,
    Trace,
    Value,
)
from core.ids import InvalidId, parse_uuid7
from core.memory import Memory, memory_key
from core.merchants import merchant_key
from core.tools.context import HISTORY_DAYS, NotFound, ToolContext, decimal, median
from core.tools.inputs import Input
from core.tools.reads import MOVEMENT_FIELDS, Movement, Reader, to_movement

CHARGE_FIELDS = (*MOVEMENT_FIELDS, "merchant_category", "fraud_score")
HIGH_SCORE = Decimal(30)
FRESH_HOLD_DAYS = 7
SIMILAR_WINDOW = timedelta(days=3)
MAX_SIMILAR = 3
RATIO_PLACES = Decimal("0.01")


class ChargeFactsInput(Input):
    transaction_ref: str = Field(description="transaction_id of one of the customer's charges")


def charge_facts(context: ToolContext, ledger: Ledger, args: ChargeFactsInput) -> list[str]:
    try:
        parse_uuid7(args.transaction_ref)
    except InvalidId as error:
        raise NotFound(args.transaction_ref) from error
    reader = Reader(context)
    cards = reader.cards()
    item = reader.accounts.transaction_on_any_card(
        context.customer_id, [card.product_id for card in cards], args.transaction_ref, CHARGE_FIELDS
    )
    if item is None:
        raise NotFound(args.transaction_ref)
    charge = to_movement(item)
    card = next(card for card in cards if card.product_id == charge.product_id)
    charge_day = context.local_day(charge.at)
    rows, _ = reader.movements(
        cards, charge_day - timedelta(days=HISTORY_DAYS - 1), min(context.today, charge_day + SIMILAR_WINDOW)
    )
    key = merchant_key(charge.merchant)
    others = [row for row in rows if row.transaction_id != charge.transaction_id]
    prior = sorted(
        (
            row
            for row in others
            if row.status == "Approved" and row.at < charge.at and merchant_key(row.merchant) == key
        ),
        key=lambda row: row.at,
        reverse=True,
    )
    similar = [
        row
        for row in others
        if merchant_key(row.merchant) == key
        and row.amount == charge.amount
        and abs(row.at - charge.at) <= SIMILAR_WINDOW
    ][:MAX_SIMILAR]
    approved = [row for row in others if row.status == "Approved"]
    hold_age = (context.now - charge.at) // timedelta(days=1)
    score_band = _score_band(item.get("fraud_score"))
    reasons = [
        reason
        for reason, present in (
            ("score_high", score_band == "high"),
            ("foreign_country", charge.country is not None and charge.country != context.country),
            (
                "unusual_channel",
                charge.channel != "POS" and bool(approved) and all(row.channel == "POS" for row in approved),
            ),
            ("new_merchant", not prior),
        )
        if present
    ]
    explanation = _explanation(charge, hold_age, bool(prior))
    recognized = (
        Memory.from_dynamodb(context.dynamodb()).memory(
            context.customer_id, memory_key("recognized_charge", charge.transaction_id)
        )
        is not None
    )
    verdict = (
        context.decide(
            {
                "transaction_id": charge.transaction_id,
                "status": charge.status,
                "card_status": card.status,
                "explanation": explanation,
                "score_band": score_band,
                "reasons": tuple(reasons),
                "prior_count": len(prior),
                "recognized": recognized,
            }
        )
        if context.decide
        else None
    )
    similar_facts = [ledger.add("similar", _similar_fields(row)) for row in similar]
    same_currency = [row.amount for row in prior if row.currency == charge.currency]
    typical = median(same_currency) if same_currency else None
    fields: dict[str, Value | None] = {
        "charge.transaction_ref": Ref("transaction", charge.transaction_id),
        "charge.card_ref": Ref("card", charge.product_id),
        "charge.date": Instant(charge.at),
        "charge.amount": Money(charge.amount, charge.currency),
        "charge.merchant": Merchant(charge.merchant),
        "charge.merchant_category": _label("category", item.get("merchant_category")),
        "charge.channel": _label("channel", charge.channel),
        "charge.country": Country(charge.country) if charge.country else None,
        "charge.city": City(charge.city) if charge.city else None,
        "charge.status": Status("transaction", charge.status),
        "card.last4": Last4(card.last4),
        "card.type": Label("card_type", card.type),
        "card.status": Status("card", card.status),
        "verdict.decision": Trace(verdict.decision) if verdict else None,
        "verdict.rule_ids": Trace(verdict.rule_ids) if verdict else None,
        "verdict.explanation": Label("explanation", explanation),
        "verdict.hold_age_days": Count(hold_age, "day") if charge.status == "Pending" else None,
        "verdict.score_band": Label("score_band", score_band),
        "verdict.reasons": Labels("reason", tuple(reasons)),
        "habit.prior_count": Count(len(prior), "purchase"),
        "habit.median_amount": Money(typical.quantize(RATIO_PLACES), charge.currency) if typical else None,
        "habit.last_prior_date": Day(context.local_day(prior[0].at)) if prior else None,
        "habit.ratio_to_typical": (
            Ratio((charge.amount / typical).quantize(RATIO_PLACES)) if typical else None
        ),
        "similar": FactIds(tuple(fact.id for fact in similar_facts)),
        "recognized": Flag(recognized),
    }
    main = ledger.add("charge", fields)
    return [main.id, *(fact.id for fact in similar_facts)]


def _score_band(score: object) -> str:
    if score is None:
        return "none"
    return "high" if decimal(score) > HIGH_SCORE else "low"


def _explanation(charge: Movement, hold_age: int, has_prior: bool) -> str:
    if charge.status == "Reversed":
        return "reversed"
    if charge.status == "Declined":
        return "declined_attempted"
    if charge.status == "Pending":
        return "fresh_hold" if hold_age <= FRESH_HOLD_DAYS else "stale_pending"
    return "prior_purchases" if has_prior else "none"


def _similar_fields(row: Movement) -> dict[str, Value | None]:
    return {
        "transaction_ref": Ref("transaction", row.transaction_id),
        "date": Instant(row.at),
        "amount": Money(row.amount, row.currency),
        "status": Status("transaction", row.status),
    }


def _label(domain: str, value: object) -> Label | None:
    return Label(domain, str(value)) if value else None
