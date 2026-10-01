import calendar
import hashlib
import random
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Any

from core.accounts import transaction_date, transaction_key
from core.ids import format_instant, parse_uuid7, uuid7_at, uuid7_time
from core.ingestion import DECLINE_CODES, Origin
from core.months import add_months
from crud.catalog import MAX_PURCHASE_USD, SUSPICIOUS_POOL, Archetype, Country, Merchant

CARDS_PER_ACCOUNT = 3
TRANSACTIONS_PER_CARD = 100
HISTORY_DAYS = 90
MIN_PER_MERCHANT = 4
RECURRING_CHARGES = 3
LATEST_BILL_DAYS = 20
LAST_BILLING_DAY = 28
SEEDED_CLAIM_MIN_AGE = timedelta(days=7)
SEEDED_CLAIM_OFFSETS = {
    "opened": timedelta(days=1),
    "assigned": timedelta(days=3),
    "review": timedelta(days=7),
}
FRESH_HOLD_DAYS = 7
STATUS_MIX = {"Approved": 92, "Declined": 5, "Pending": 2, "Reversed": 1}
BILLING_CYCLE_DAYS = 30
CENT = Decimal("0.01")
HIGH_SCORE = Decimal(30)
PURCHASING_POWER = 20
DEBIT_FUNDS_IN_PURCHASES = (25, 50)
CREDIT_LIMIT_USD = (15000, 30000)


class CaseKind(StrEnum):
    FRESH_HOLD = "fresh_hold"
    REVERSED_CHARGE = "reversed_charge"
    STALE_PENDING = "stale_pending"


class Score(StrEnum):
    FLAGGED = "flagged"
    MISSED = "missed"
    NONE = "none"


@dataclass(frozen=True)
class Claim:
    customer_id: str
    country: Country
    anchor: datetime

    @property
    def home_city(self) -> str:
        return self.country.cities[
            _seed(self.customer_id, "home", self.anchor.isoformat()) % len(self.country.cities)
        ]


@dataclass(frozen=True)
class Plant:
    kind: CaseKind
    card: int
    archetype: Archetype
    status: str
    days_ago: tuple[int, int]


PLANTS = (
    Plant(CaseKind.FRESH_HOLD, 0, Archetype.FUEL, "Pending", (1, 3)),
    Plant(CaseKind.REVERSED_CHARGE, 1, Archetype.RETAIL, "Reversed", (10, 30)),
    Plant(CaseKind.STALE_PENDING, 2, Archetype.DELIVERY, "Pending", (12, 40)),
)

CARD_TYPES = ("Tarjeta Crédito", "Tarjeta Crédito", "Tarjeta Débito")


@dataclass(frozen=True)
class Account:
    cards: list[dict[str, Any]]
    transactions: list[dict[str, Any]]
    cases: list[tuple[CaseKind, dict[str, Any]]]
    claim: dict[str, Any] | None


@dataclass
class _Row:
    merchant: Merchant
    local_day: date
    status: str = "Approved"
    plant: CaseKind | None = None


def generate(claim: Claim) -> Account:
    rng = random.Random(_seed(claim.customer_id, "account", claim.anchor.isoformat()))  # noqa: S311
    recurring = {
        merchant.archetype: _amount(rng, claim.country, merchant.profile.usd_low, merchant.profile.usd_high)
        for merchant in claim.country.merchants
        if merchant.profile.recurring
    }
    cards: list[dict[str, Any]] = []
    transactions: list[dict[str, Any]] = []
    cases: list[tuple[CaseKind, dict[str, Any]]] = []
    for index, rows in enumerate(_rows(rng, claim)):
        product_id = str(uuid7_at(claim.anchor + timedelta(milliseconds=index), rng.getrandbits(74)))
        items = [_transaction(rng, claim, product_id, row, recurring) for row in rows]
        cards.append(_card(rng, claim, product_id, CARD_TYPES[index], items))
        transactions.extend(items)
        cases.extend(
            (row.plant, item) for row, item in zip(rows, items, strict=True) if row.plant is not None
        )
    return Account(
        cards=cards, transactions=transactions, cases=cases, claim=seeded_claim(claim, cards, transactions)
    )


def seeded_claim(
    claim: Claim, cards: list[dict[str, Any]], transactions: list[dict[str, Any]]
) -> dict[str, Any] | None:
    card = next((card for card in cards if card["product_type"] == "Tarjeta Débito"), cards[0])
    cutoff = uuid7_time(parse_uuid7(card["product_id"])) - SEEDED_CLAIM_MIN_AGE
    candidates = [
        item
        for item in transactions
        if item["product_id"] == card["product_id"]
        and item["transaction_status"] == "Approved"
        and item["channel"] == "POS"
        and item["transaction_country"] == claim.country.code
        and Decimal(item.get("fraud_score", 0)) <= HIGH_SCORE
        and datetime.fromisoformat(item["transaction_date"]) <= cutoff
    ]
    if not candidates:
        return None
    disputed = max(candidates, key=lambda item: item["transaction_date"])
    charged_at = datetime.fromisoformat(disputed["transaction_date"])
    stamps = {stage: format_instant(charged_at + offset) for stage, offset in SEEDED_CLAIM_OFFSETS.items()}
    return {
        "customer_id": claim.customer_id,
        "complaint_id": disputed["transaction_id"],
        "area": "claims",
        "status": "In Process",
        "creation_date": stamps["opened"],
        "assignment_date": stamps["assigned"],
        "first_response_date": stamps["review"],
        "transaction_id": disputed["transaction_id"],
        "product_id": disputed["product_id"],
    }


def manual_transaction(
    rng: random.Random,
    claim: Claim,
    product_id: str,
    transaction_id: str,
    suspicious_suffix: int | None = None,
    score: Score = Score.MISSED,
) -> dict[str, Any]:
    row: dict[str, Any]
    if suspicious_suffix is None:
        merchant = rng.choice(claim.country.merchants)
        row = _merchant_fields(merchant, rng, claim)
        row["amount"] = _amount(rng, claim.country, merchant.profile.usd_low, merchant.profile.usd_high)
        row["fraud_score"] = _low_score(rng)
        origin = Origin.MANUAL_NORMAL
    else:
        online = rng.choice(SUSPICIOUS_POOL)
        row = {
            "merchant_name": f"{online.name} {suspicious_suffix:04d}",
            "merchant_category": online.category,
            "transaction_category": online.category,
            "channel": "Web",
            "transaction_city": claim.home_city,
            "amount": _amount(rng, claim.country, online.usd_low, online.usd_high),
            "fraud_score": _score(rng, score),
        }
        origin = Origin.MANUAL_SUSPICIOUS
    return _item(claim, product_id, transaction_id, row, "Approved", "00", origin)


def _rows(rng: random.Random, claim: Claim) -> list[list[_Row]]:
    merchants = list(claim.country.merchants)
    today = _local(claim.anchor, claim.country).date()
    billed = _billed(rng, merchants, today)
    per_card = TRANSACTIONS_PER_CARD - 1
    occasional = [merchant for merchant in merchants if not merchant.profile.recurring]
    picks = [merchant for merchant in occasional for _ in range(MIN_PER_MERCHANT)]
    picks += rng.choices(
        occasional,
        weights=[merchant.profile.weight for merchant in occasional],
        k=CARDS_PER_ACCOUNT * per_card - sum(map(len, billed)) - len(picks),
    )
    rng.shuffle(picks)
    cards: list[list[_Row]] = []
    taken = 0
    for index in range(CARDS_PER_ACCOUNT):
        count = per_card - len(billed[index])
        rows = [
            _Row(merchant, today - timedelta(days=rng.randint(1, HISTORY_DAYS - 1)))
            for merchant in picks[taken : taken + count]
        ]
        taken += count
        plant = next(p for p in PLANTS if p.card == index)
        merchant = next(m for m in merchants if m.archetype is plant.archetype)
        planted = _Row(
            merchant, today - timedelta(days=rng.randint(*plant.days_ago)), plant.status, plant.kind
        )
        _assign_statuses(rng, rows, planted.status, today)
        cards.append([*rows, *billed[index], planted])
    return cards


def _billed(rng: random.Random, merchants: list[Merchant], today: date) -> list[list[_Row]]:
    billed: list[list[_Row]] = [[] for _ in range(CARDS_PER_ACCOUNT)]
    for merchant in merchants:
        if not merchant.profile.recurring:
            continue
        card = rng.randrange(CARDS_PER_ACCOUNT)
        latest = today - timedelta(days=rng.randint(1, LATEST_BILL_DAYS))
        latest = latest.replace(day=min(latest.day, LAST_BILLING_DAY))
        billed[card].extend(
            _Row(merchant, add_months(latest, -months)) for months in range(RECURRING_CHARGES)
        )
    return billed


def _assign_statuses(rng: random.Random, rows: list[_Row], planted_status: str, today: date) -> None:
    wanted = Counter(STATUS_MIX)
    wanted[planted_status] -= 1
    stale = [row for row in rows if (today - row.local_day).days > FRESH_HOLD_DAYS + 1]
    for row in rng.sample(stale, wanted["Pending"]):
        row.status = "Pending"
    approved = [row for row in rows if row.status == "Approved"]
    others = rng.sample(approved, wanted["Declined"] + wanted["Reversed"])
    for position, row in enumerate(others):
        row.status = "Declined" if position < wanted["Declined"] else "Reversed"


def _transaction(
    rng: random.Random,
    claim: Claim,
    product_id: str,
    row: _Row,
    recurring: dict[Archetype, Decimal],
) -> dict[str, Any]:
    local_time = time(rng.randint(8, 21), rng.randint(0, 59), rng.randint(0, 59), rng.randint(0, 999) * 1000)
    instant = datetime.combine(row.local_day, local_time, tzinfo=_zone(claim.country))
    transaction_id = str(uuid7_at(instant, rng.getrandbits(74)))
    fields = _merchant_fields(row.merchant, rng, claim)
    profile = row.merchant.profile
    fields["amount"] = recurring.get(row.merchant.archetype) or _amount(
        rng, claim.country, profile.usd_low, profile.usd_high
    )
    fields["fraud_score"] = _low_score(rng)
    code = "00" if row.status in ("Approved", "Reversed") else rng.choice(sorted(DECLINE_CODES))
    return _item(claim, product_id, transaction_id, fields, row.status, code, Origin.SETUP)


def _merchant_fields(merchant: Merchant, rng: random.Random, claim: Claim) -> dict[str, Any]:
    profile = merchant.profile
    in_person = profile.channel == "POS"
    away = in_person and rng.random() < 0.15
    city = rng.choice([c for c in claim.country.cities if c != claim.home_city]) if away else claim.home_city
    return {
        "merchant_name": merchant.name,
        "merchant_category": profile.category,
        "transaction_category": profile.category,
        "channel": profile.channel,
        "transaction_city": city,
    }


def _item(
    claim: Claim,
    product_id: str,
    transaction_id: str,
    fields: dict[str, Any],
    status: str,
    response_code: str,
    origin: Origin,
) -> dict[str, Any]:
    return {
        "customer_id": claim.customer_id,
        "transaction_key": transaction_key(product_id, transaction_id),
        "transaction_id": transaction_id,
        "product_id": product_id,
        "transaction_date": transaction_date(transaction_id),
        "transaction_type": "Purchase",
        "currency": claim.country.currency,
        "transaction_country": claim.country.code,
        "transaction_status": status,
        "response_code": response_code,
        "origin": origin.value,
        **{name: value for name, value in fields.items() if value is not None},
    }


def _card(
    rng: random.Random, claim: Claim, product_id: str, product_type: str, items: list[dict[str, Any]]
) -> dict[str, Any]:
    country = claim.country
    expires = claim.anchor.date().replace(day=1) + timedelta(days=365 * rng.randint(2, 5))
    card: dict[str, Any] = {
        "customer_id": claim.customer_id,
        "product_id": product_id,
        "product_type": product_type,
        "product_number": f"**** {rng.randint(0, 9999):04d}",
        "currency": country.currency,
        "product_status": "Active",
        "expiration_date": expires.replace(
            day=calendar.monthrange(expires.year, expires.month)[1]
        ).isoformat(),
        "balance_as_of": format_instant(claim.anchor),
    }
    if product_type == "Tarjeta Débito":
        low, high = (MAX_PURCHASE_USD * purchases for purchases in DEBIT_FUNDS_IN_PURCHASES)
        card["current_balance"] = _amount(rng, country, low, high)
        return card
    cycle_start = claim.anchor - timedelta(days=BILLING_CYCLE_DAYS)
    balance = sum(
        (
            item["amount"]
            for item in items
            if item["transaction_status"] in ("Approved", "Pending")
            and datetime.fromisoformat(item["transaction_date"]) >= cycle_start
        ),
        start=Decimal(0),
    )
    step = max(country.rounding, Decimal(1)) * 100
    limit = _round(Decimal(str(rng.uniform(*CREDIT_LIMIT_USD))) * country.usd_rate, step)
    floor = balance + PURCHASING_POWER * max_purchase(country)
    if limit < floor:
        limit = (floor / step).to_integral_value(ROUND_CEILING) * step
    card["credit_limit"] = limit.quantize(CENT)
    card["current_balance"] = balance.quantize(CENT)
    return card


def max_purchase(country: Country) -> Decimal:
    return _round(Decimal(str(MAX_PURCHASE_USD)) * country.usd_rate, country.rounding)


def _amount(rng: random.Random, country: Country, usd_low: float, usd_high: float) -> Decimal:
    usd = Decimal(str(round(rng.uniform(usd_low, usd_high), 2)))
    return max(_round(usd * country.usd_rate, country.rounding), country.rounding).quantize(CENT)


def _round(value: Decimal, step: Decimal) -> Decimal:
    return (value / step).to_integral_value(ROUND_HALF_UP) * step


def _low_score(rng: random.Random) -> Decimal:
    return Decimal(str(round(rng.uniform(0, 30), 2)))


def _score(rng: random.Random, score: Score) -> Decimal | None:
    if score is Score.NONE:
        return None
    if score is Score.FLAGGED:
        return Decimal(str(round(rng.uniform(31, 100), 2)))
    return _low_score(rng)


def _local(instant: datetime, country: Country) -> datetime:
    return instant.astimezone(_zone(country))


def _zone(country: Country) -> timezone:
    return country.zone


def _seed(*parts: str) -> int:
    return int.from_bytes(hashlib.sha256("|".join(parts).encode()).digest()[:8], "big")
