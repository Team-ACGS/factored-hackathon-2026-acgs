import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from botocore.exceptions import ClientError
from moto.iam.access_control import IAMPolicy, PermissionResult

from core import access
from core import accounts as accounts_module
from core.access import READ_ONLY_POLICY, customer_session
from core.accounts import transaction_key
from core.cases import case_code
from core.facts import Ledger, Say, check
from core.facts.values import Fact
from core.tools import TOOLS, Decide, ToolContext, Verdict, call
from core.tools import reads as reads_module
from core.tools.reads import Reader
from harness import Aws, uuid7

NOW = datetime(2031, 3, 15, 17, 0, tzinfo=UTC)
ME = "c1"
OTHER = "c2"
FULL_NUMBER = "9999 8888 7777 4821"
RAW_SCORE = Decimal("87.65")
HIDDEN_VALUES = (
    "HIDDEN-ORIGIN",
    "8888 7777",
    "88887777",
    "DNI-55555555",
    "777.77",
    "AGENT-007",
    "SLA-HIDDEN",
    "87.65",
)
HIDDEN_NAMES = (
    "origin",
    "is_fraud",
    "fraud_score",
    "document",
    "product_number",
    "affected_product_id",
    "claimed_amount",
    "compensation",
    "sla",
    "response_code",
    "customer_id",
)
TABLE_HIDDEN: dict[str, Any] = {
    "origin": "HIDDEN-ORIGIN",
    "is_fraud": True,
    "document_number": "DNI-55555555",
    "response_code": "05",
}


def days_ago(days: float, hour: int = 17) -> datetime:
    return NOW.replace(hour=hour) - timedelta(days=days)


@dataclass
class Seed:
    aws: Aws
    customer_id: str = ME
    cards: dict[str, str] = field(default_factory=dict)

    def card(
        self, kind: str = "Tarjeta Crédito", number: str = FULL_NUMBER, currency: str = "PEN", **extra: Any
    ) -> str:
        product_id = uuid7(int(NOW.timestamp() * 1000) - 400 * 86_400_000 + len(self.cards))
        self.aws.products.put_item(
            Item={
                "customer_id": self.customer_id,
                "product_id": product_id,
                "product_type": kind,
                "product_number": number,
                "currency": currency,
                "product_status": "Active",
                "expiration_date": "2033-03-31",
                "current_balance": Decimal("1200.50"),
                "credit_limit": Decimal("5000"),
                **TABLE_HIDDEN,
                **extra,
            }
        )
        self.cards[product_id] = currency
        return product_id

    def charge(
        self,
        product_id: str,
        at: datetime,
        merchant: str = "Primax",
        amount: str = "100.00",
        status: str = "Approved",
        **extra: Any,
    ) -> str:
        transaction_id = uuid7(int(at.timestamp() * 1000))
        self.aws.transactions.put_item(
            Item={
                "customer_id": self.customer_id,
                "transaction_key": transaction_key(product_id, transaction_id),
                "transaction_id": transaction_id,
                "product_id": product_id,
                "transaction_date": at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                "transaction_type": "Purchase",
                "transaction_category": "Transport",
                "merchant_category": "Transport",
                "amount": Decimal(amount),
                "currency": self.cards.get(product_id, "PEN"),
                "channel": "POS",
                "merchant_name": merchant,
                "transaction_country": "PE",
                "transaction_city": "Lima",
                "transaction_status": status,
                "fraud_score": Decimal("12.5"),
                **TABLE_HIDDEN,
                **extra,
            }
        )
        return transaction_id

    def case(self, complaint_id: str, status: str = "In Process", **extra: Any) -> None:
        self.aws.complaints.put_item(
            Item={
                "customer_id": self.customer_id,
                "complaint_id": complaint_id,
                "area": "claims",
                "status": status,
                "creation_date": "2031-03-01T15:00:00.000Z",
                "assignment_date": "2031-03-03T15:00:00.000Z",
                "first_response_date": "2031-03-07T15:00:00.000Z",
                "affected_product_id": "PRODUCT-HIDDEN",
                "claimed_amount": Decimal("777.77"),
                "compensation_granted": Decimal("777.77"),
                "sla_breached": "SLA-HIDDEN",
                "assigned_agent_id": "AGENT-007",
                "description": "AGENT-007 notes",
                **extra,
            }
        )

    def memory(self, key: str, subject: str, created_at: str, note: str = "es mi gasolinera") -> None:
        self.aws.memory.put_item(
            Item={
                "customer_id": self.customer_id,
                "memory_key": key,
                "type": key.split("#")[0],
                "subject": subject,
                "note": note,
                "source_room_id": "room-1",
                "source_message_id": "AGENT-007",
                "created_at": created_at,
            }
        )


@pytest.fixture
def seed(aws: Aws) -> Seed:
    return Seed(aws)


@pytest.fixture
def other(aws: Aws) -> Seed:
    return Seed(aws, OTHER)


def context(decide: Decide | None = None) -> ToolContext:
    return ToolContext(ME, "PE", "es", NOW, "test", decide)


def run(name: str, ledger: Ledger | None = None, **arguments: Any) -> tuple[Ledger, list[Fact]]:
    book = ledger or Ledger("PE", NOW)
    result = call(name, arguments, context(), book)
    return book, [book.facts[fact_id] for fact_id in result.ids]


def plain(fact: Fact) -> dict[str, Any]:
    return {name: value.to_model() for name, value in fact.fields.items()}


def value(fact: Fact, name: str) -> Any:
    model = fact.fields[name].to_model()
    return model.get("value", model)


def error_of(facts: list[Fact]) -> str:
    [fact] = facts
    assert fact.kind == "error"
    return str(value(fact, "error"))


@pytest.fixture
def account(seed: Seed, other: Seed) -> dict[str, str]:
    credit = seed.card()
    debit = seed.card("Tarjeta Débito", "**** 7730")
    seed.card("Cuenta de Ahorros", "**** 0001")
    ids = {
        "credit": credit,
        "debit": debit,
        "primax_charge": seed.charge(credit, days_ago(10), "Primax Av. Arequipa", "120.00"),
        "primax_old_charge": seed.charge(credit, days_ago(40), "Primax", "100.00"),
        "netflix_1": seed.charge(debit, days_ago(65), "NETFLIX.COM", "49.90", channel="Web"),
        "netflix_2": seed.charge(debit, days_ago(35), "NETFLIX.COM", "49.90", channel="Web"),
        "netflix_3": seed.charge(debit, days_ago(5), "Netflix.com", "52.00", channel="Web"),
        "flagged": seed.charge(
            credit, days_ago(1), "GLOBALPAY 1234", "490.00", channel="Web", fraud_score=RAW_SCORE
        ),
        "other_card": other.card(),
    }
    ids["other_charge"] = other.charge(ids["other_card"], days_ago(3), "SECRET SHOP", "999.00")
    seed.case(ids["primax_charge"], transaction_id=ids["primax_charge"], product_id=credit)
    other.case(ids["other_charge"])
    seed.memory(f"recognized_charge#{ids['primax_charge']}", ids["primax_charge"], "2031-03-10T12:00:00.000Z")
    return ids


EVERY_CALL: dict[str, dict[str, Any]] = {
    "list_cards": {},
    "card_status": {"card_ref": "credit"},
    "search_movements": {"date_from": "2031-01-01", "date_to": "2031-03-15", "limit": 25},
    "merchant_history": {"merchant": "primax"},
    "spend_summary": {
        "period": {"from": "2031-03-01", "to": "2031-03-15"},
        "compare_period": {"from": "2031-02-01", "to": "2031-02-28"},
    },
    "recurring_charges": {},
    "charge_facts": {"transaction_ref": "flagged"},
    "case_status": {},
    "recall": {},
}


def resolved(arguments: dict[str, Any], account: dict[str, str]) -> dict[str, Any]:
    return {
        key: account.get(item, item) if isinstance(item, str) else item for key, item in arguments.items()
    }


def test_the_nine_data_tools_are_registered_and_no_schema_takes_a_customer_id(aws: Aws) -> None:
    assert set(TOOLS) == {*EVERY_CALL, "search_policies"}
    assert "customer_id" not in json.dumps(TOOLS["search_policies"].input_schema())
    for name in EVERY_CALL:
        assert "customer_id" not in json.dumps(TOOLS[name].input_schema())
        _, facts = run(name, customer_id=OTHER, **EVERY_CALL[name])
        assert error_of(facts) == "invalid_argument"


def test_every_tool_returns_only_typed_facts_and_never_a_hidden_attribute(account: dict[str, str]) -> None:
    for name, arguments in EVERY_CALL.items():
        book, facts = run(name, **resolved(arguments, account))
        assert facts
        assert all(fact.kind != "error" for fact in facts), name
        payload = book.payload()
        for fact in payload:
            assert set(fact) == {"id", "kind", "fields"}
            assert all(isinstance(typed, dict) and "type" in typed for typed in fact["fields"].values())
        text = json.dumps(payload)
        assert not [hidden for hidden in HIDDEN_VALUES if hidden in text], name
        assert not [
            hidden
            for fact in payload
            for field_name in fact["fields"]
            for hidden in HIDDEN_NAMES
            if hidden in field_name
        ], name
        assert "SECRET SHOP" not in text


def test_the_read_only_session_policy_allows_only_reads() -> None:
    policy = IAMPolicy(READ_ONLY_POLICY)
    table = "arn:aws:dynamodb:us-east-1:123456789012:table/clara-test-transactions"

    for action in ("dynamodb:GetItem", "dynamodb:BatchGetItem", "dynamodb:Query"):
        assert policy.is_action_permitted(action, table) == PermissionResult.PERMITTED
    for action in (
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:BatchWriteItem",
        "dynamodb:TransactWriteItems",
        "dynamodb:Scan",
    ):
        assert policy.is_action_permitted(action, table) != PermissionResult.PERMITTED


@pytest.fixture
def assumed(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    assume_role = access._sts.assume_role

    def recording(**request: Any) -> Any:
        requests.append(request)
        return assume_role(**request)

    monkeypatch.setattr(access._sts, "assume_role", recording)
    return requests


def test_every_tool_assumes_the_customer_role_with_the_read_only_policy(
    account: dict[str, str], assumed: list[dict[str, Any]]
) -> None:
    for name, arguments in EVERY_CALL.items():
        access._sessions.clear()
        assumed.clear()
        run(name, **resolved(arguments, account))
        assert assumed, name
        assert all(request["Policy"] == READ_ONLY_POLICY for request in assumed), name
        assert all(request["Tags"] == [{"Key": "customer_id", "Value": ME}] for request in assumed), name


def test_the_read_only_flag_is_part_of_the_session_cache_key(aws: Aws, assumed: list[dict[str, Any]]) -> None:
    writer = customer_session(ME, "test")
    reader = customer_session(ME, "test", read_only=True)

    assert reader is not writer
    assert customer_session(ME, "test", read_only=True) is reader
    assert ["Policy" in request for request in assumed] == [False, True]


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("card_status", {"card_ref": "other_card"}),
        ("card_status", {"card_ref": "not-a-uuid"}),
        ("charge_facts", {"transaction_ref": "other_charge"}),
        ("charge_facts", {"transaction_ref": "not-a-uuid"}),
        ("case_status", {"case_ref": "other_charge"}),
        ("search_movements", {"card_ref": "other_card"}),
        ("recurring_charges", {"card_ref": "other_card"}),
    ],
)
def test_a_ref_the_customer_does_not_own_is_not_found_and_reveals_nothing(
    account: dict[str, str], name: str, arguments: dict[str, Any]
) -> None:
    book, facts = run(name, **resolved(arguments, account))

    assert error_of(facts) == "not_found"
    assert "SECRET SHOP" not in json.dumps(book.payload())
    assert "999.00" not in json.dumps(book.payload())


def test_list_cards_returns_cards_only_with_their_last_four_digits(account: dict[str, str]) -> None:
    _, facts = run("list_cards")

    *cards, aggregate = facts
    assert [value(card, "last4") for card in cards] == ["4821", "7730"]
    assert [plain(card)["type"]["value"] for card in cards] == ["credit", "debit"]
    assert value(aggregate, "count") == 2


def test_card_status_without_a_moving_balance_says_the_balance_is_unavailable(
    account: dict[str, str],
) -> None:
    _, [card] = run("card_status", card_ref=account["credit"])

    assert value(card, "balance_available") is False
    assert not {"current_balance", "credit_limit", "available"} & set(card.fields)


def test_card_status_computes_available_from_a_dated_balance(seed: Seed) -> None:
    credit = seed.card(balance_as_of="2031-03-15T10:00:00.000Z", product_status="Blocked")

    _, [card] = run("card_status", card_ref=credit)

    assert plain(card)["available"] == {"type": "money", "amount": "3799.50", "currency": "PEN"}
    assert value(card, "balance_available") is True
    assert value(card, "blocked_by_clara") is False
    assert "blocked_at" not in card.fields


def movements(**arguments: Any) -> tuple[list[Fact], Fact]:
    _, facts = run("search_movements", **arguments)
    *rows, aggregate = facts
    return rows, aggregate


@pytest.fixture
def busy(seed: Seed) -> str:
    card = seed.card()
    for day in range(30):
        seed.charge(card, days_ago(day, hour=12), "Tambo+", f"{day + 1}.00")
    return card


def test_search_movements_returns_ten_newest_by_default_and_pages_with_an_opaque_cursor(busy: str) -> None:
    rows, aggregate = movements()

    assert len(rows) == 10
    assert value(aggregate, "count") == 30
    assert value(aggregate, "truncated") is True
    seen = [value(row, "transaction_ref") for row in rows]
    cursor = value(aggregate, "cursor")
    while cursor:
        rows, aggregate = movements(cursor=cursor)
        seen += [value(row, "transaction_ref") for row in rows]
        cursor = aggregate.fields["cursor"].to_model()["value"] if "cursor" in aggregate.fields else None
    assert len(seen) == len(set(seen)) == 30
    assert value(aggregate, "truncated") is False


def test_search_movements_returns_at_most_twenty_five_rows(busy: str) -> None:
    rows, _ = movements(limit=25)

    assert len(rows) == 25
    assert error_of(run("search_movements", limit=26)[1]) == "invalid_argument"


def test_a_cursor_from_other_filters_is_rejected(busy: str) -> None:
    _, aggregate = movements()

    _, facts = run("search_movements", cursor=value(aggregate, "cursor"), merchant="tambo")
    assert error_of(facts) == "invalid_argument"


def test_search_movements_filters_and_sorts_in_code(busy: str, seed: Seed) -> None:
    seed.charge(busy, days_ago(2), "Primax", "300.00", status="Pending")

    rows, aggregate = movements(amount_min=25, sort="amount_desc", limit=3)

    assert [plain(row)["amount"]["amount"] for row in rows] == ["300.00", "30.00", "29.00"]
    assert value(aggregate, "count") == 7
    pending, _ = movements(status="Pending", merchant="PRIMAX")
    assert [value(row, "merchant") for row in pending] == ["Primax"]


def test_a_period_before_the_history_is_clamped_to_it_and_says_so(busy: str) -> None:
    _, aggregate = movements(date_from="2030-12-01", date_to="2031-03-15")

    assert value(aggregate, "clamped_from") == "2030-12-01"
    assert plain(aggregate)["period"] == {"type": "period", "from": "2030-12-14", "to": "2031-03-15"}
    assert value(aggregate, "count") == 30


def test_a_period_ending_after_today_stops_today_and_one_starting_after_today_is_invalid(busy: str) -> None:
    _, aggregate = movements(date_from="2031-03-01", date_to="2031-06-30")

    assert plain(aggregate)["period"] == {"type": "period", "from": "2031-03-01", "to": "2031-03-15"}
    assert error_of(run("search_movements", date_from="2031-03-16")[1]) == "invalid_argument"


def test_a_scan_past_the_row_budget_says_truncated(busy: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reads_module, "MAX_ROWS", 5)

    rows, aggregate = movements(limit=25)

    assert len(rows) == 5
    assert value(aggregate, "truncated") is True


def test_at_most_four_cards_are_read_per_call(seed: Seed) -> None:
    for _ in range(5):
        seed.charge(seed.card(), days_ago(1))

    rows, aggregate = movements()

    assert len(rows) == 4
    assert value(aggregate, "truncated") is True


def test_an_empty_search_echoes_the_filter_so_it_can_be_said(account: dict[str, str]) -> None:
    rows, aggregate = movements(merchant="Rappi")

    assert rows == []
    assert value(aggregate, "count") == 0
    assert value(aggregate, "merchant") == "Rappi"


def test_an_echoed_merchant_is_code_owned_or_trace_only(account: dict[str, str]) -> None:
    book, facts = run("search_movements", merchant="0800 123 4567")
    aggregate = facts[-1]

    assert plain(aggregate)["merchant"]["type"] == "trace"
    errors = check([Say("Llama al 0800 123 4567."), Say(f"{{{aggregate.id}.merchant}}")], book, "es")
    assert {error.code for error in errors if error.part == 0} >= {"contact_outside_facts"}
    assert [error.code for error in errors if error.part == 1] == ["trace_only_reference"]
    _, facts = run("search_movements", merchant="PRIMAX", date_from="2031-03-14")
    assert plain(facts[-1])["merchant"] == {"type": "merchant", "value": "Primax"}
    _, facts = run("search_movements", merchant="primax av. arequipa")
    assert plain(facts[-1])["merchant"] == {"type": "merchant", "value": "Primax Av. Arequipa"}


def test_merchant_history_counts_purchases_and_takes_the_median(account: dict[str, str], seed: Seed) -> None:
    seed.charge(account["debit"], days_ago(20), "PRIMAX", "500.00", status="Declined")

    _, [history] = run("merchant_history", merchant="primax")

    assert value(history, "count") == 2
    assert value(history, "merchant") == "Primax Av. Arequipa"
    assert plain(history)["typical_amount"]["amount"] == "110.00"
    assert value(history, "first_date") == "2031-02-03"
    assert value(history, "last_date") == "2031-03-05"


def test_merchant_history_with_no_purchase_is_a_count_of_zero(account: dict[str, str]) -> None:
    _, [history] = run("merchant_history", merchant="Inkafarma")

    assert value(history, "count") == 0
    assert value(history, "merchant") == "Inkafarma"


def test_spend_summary_counts_approved_and_pending_and_breaks_out_pending(seed: Seed) -> None:
    card = seed.card()
    for status, amount in (("Approved", "100"), ("Pending", "40"), ("Declined", "500"), ("Reversed", "70")):
        seed.charge(card, days_ago(3), "Primax", amount, status=status)
    seed.charge(card, days_ago(20), "Primax", "60")
    seed.charge(card, days_ago(3), "Tambo+", "9")

    _, [spend] = run(
        "spend_summary",
        merchant="primax",
        period={"from": "2031-03-01", "to": "2031-03-15"},
        compare_period={"from": "2031-02-01", "to": "2031-02-28"},
    )

    model = plain(spend)
    assert Decimal(model["total"]["amount"]) == Decimal(140)
    assert value(spend, "count") == 2
    assert Decimal(model["pending_total"]["amount"]) == Decimal(40)
    assert Decimal(model["compare_total"]["amount"]) == Decimal(60)
    assert Decimal(model["delta"]["amount"]) == Decimal(80)
    assert value(spend, "direction") == "more"
    assert value(spend, "counted") == "approved_and_pending"
    assert value(spend, "partial") is True


def test_spend_summary_never_sums_across_currencies(seed: Seed) -> None:
    soles = seed.card()
    dollars = seed.card(currency="USD")
    seed.charge(soles, days_ago(2), amount="340")
    seed.charge(dollars, days_ago(2), amount="120")

    _, facts = run("spend_summary", period={"from": "2031-03-01", "to": "2031-03-15"})

    assert sorted(
        (plain(fact)["total"]["currency"], Decimal(plain(fact)["total"]["amount"])) for fact in facts
    ) == [
        ("PEN", Decimal(340)),
        ("USD", Decimal(120)),
    ]


def test_spend_summary_with_no_spending_is_zero_in_the_card_currency(seed: Seed) -> None:
    seed.card()

    _, [spend] = run("spend_summary", period={"from": "2031-02-01", "to": "2031-02-10"})

    assert Decimal(plain(spend)["total"]["amount"]) == 0
    assert value(spend, "count") == 0
    assert value(spend, "partial") is False


def series(
    seed: Seed, card: str, merchant: str, gaps: list[int], amounts: list[str], start: int = 80
) -> None:
    day = start
    for gap, amount in zip([0, *gaps], amounts, strict=True):
        day -= gap
        seed.charge(card, days_ago(day), merchant, amount)


def recurring(**arguments: Any) -> list[dict[str, Any]]:
    _, facts = run("recurring_charges", **arguments)
    return [plain(fact) for fact in facts[:-1]]


def test_recurring_charges_finds_monthly_and_weekly_series_by_normalized_merchant(
    account: dict[str, str], seed: Seed
) -> None:
    series(seed, account["credit"], "Gym Club", [7, 6, 8], ["30", "30", "31", "29"], start=30)

    found = {(entry["merchant"]["value"], entry["cadence"]["value"]) for entry in recurring()}

    assert found == {("Netflix.com", "monthly"), ("Gym Club", "weekly")}
    netflix = next(entry for entry in recurring(card_ref=account["debit"]))
    assert netflix["typical_amount"] == {"type": "money", "amount": "49.90", "currency": "PEN"}
    assert netflix["last_date"]["value"] == "2031-03-10"
    assert netflix["next_expected"]["value"] == "2031-04-10"


@pytest.mark.parametrize(
    ("gaps", "amounts", "found"),
    [
        ([30, 31], ["10", "10", "11.5"], True),
        ([30, 31], ["10", "10", "11.6"], False),
        ([30, 40], ["10", "10", "10"], False),
        ([25], ["10", "10"], False),
        ([35], ["10", "10"], True),
        ([7, 30], ["10", "10", "10"], False),
        ([0], ["10", "10"], False),
    ],
)
def test_recurring_needs_every_gap_in_one_band_and_every_amount_within_fifteen_percent(
    seed: Seed, gaps: list[int], amounts: list[str], found: bool
) -> None:
    series(seed, seed.card(), "Spotify", gaps, amounts)

    assert bool(recurring()) is found


def test_recurring_charges_says_truncated_when_the_scan_was_cut(
    seed: Seed, monkeypatch: pytest.MonkeyPatch
) -> None:
    series(seed, seed.card(), "Spotify", [30], ["10", "10"])
    monkeypatch.setattr(reads_module, "MAX_ROWS", 1)

    _, [aggregate] = run("recurring_charges")

    assert value(aggregate, "truncated") is True


def test_declined_and_reversed_charges_are_not_part_of_a_series(seed: Seed) -> None:
    card = seed.card()
    seed.charge(card, days_ago(70), "Spotify", "10")
    seed.charge(card, days_ago(40), "Spotify", "10", status="Declined")
    seed.charge(card, days_ago(10), "Spotify", "10", status="Reversed")

    assert recurring() == []


def test_recurring_charges_returns_at_most_twenty_series(seed: Seed) -> None:
    card = seed.card()
    for index in range(21):
        series(seed, card, f"Service {chr(65 + index)}", [30], ["10", "10"], start=60 - index)

    _, facts = run("recurring_charges")

    assert len(facts) == 21
    assert value(facts[-1], "truncated") is True


def test_charge_facts_reads_the_charge_its_card_the_habit_and_the_signals(
    account: dict[str, str], seed: Seed
) -> None:
    seed.charge(account["credit"], days_ago(30), "GLOBALPAY 1234", "100.00")
    similar = seed.charge(
        account["debit"], days_ago(1, hour=19), "GLOBALPAY 1234", "490.00", status="Pending"
    )

    _, [charge, twin] = run("charge_facts", transaction_ref=account["flagged"])

    model = plain(charge)
    assert model["charge.amount"] == {"type": "money", "amount": "490.00", "currency": "PEN"}
    assert model["card.last4"]["value"] == "4821"
    assert model["verdict.score_band"]["value"] == "high"
    assert model["verdict.reasons"]["values"] == ["score_high"]
    assert model["verdict.explanation"]["value"] == "prior_purchases"
    assert model["habit.prior_count"]["value"] == 1
    assert model["habit.ratio_to_typical"]["value"] == "4.90"
    assert model["similar"]["values"] == [twin.id]
    assert value(twin, "transaction_ref") == similar
    assert model["recognized"]["value"] is False
    assert "verdict.decision" not in model


@pytest.mark.parametrize(
    ("status", "age", "explanation"),
    [
        ("Reversed", 10, "reversed"),
        ("Declined", 10, "declined_attempted"),
        ("Pending", 2, "fresh_hold"),
        ("Pending", 12, "stale_pending"),
        ("Approved", 10, "none"),
    ],
)
def test_charge_facts_explains_from_the_status_and_age(
    seed: Seed, status: str, age: int, explanation: str
) -> None:
    card = seed.card()
    charge = seed.charge(card, days_ago(age), "Primax", status=status)

    _, [fact] = run("charge_facts", transaction_ref=charge)

    assert value(fact, "verdict.explanation") == explanation
    assert ("verdict.hold_age_days" in fact.fields) is (status == "Pending")
    assert value(fact, "verdict.reasons") == {
        "type": "enum_list",
        "domain": "reason",
        "values": ["new_merchant"],
    }


def test_charge_facts_knows_a_recognized_charge_and_takes_the_injected_verdict(
    account: dict[str, str],
) -> None:
    seen: list[dict[str, Any]] = []

    def decide(evidence: Any) -> Verdict:
        seen.append(dict(evidence))
        return Verdict("explain", ("history_explains",))

    book = Ledger("PE", NOW)
    result = call("charge_facts", {"transaction_ref": account["primax_charge"]}, context(decide=decide), book)

    fact = book.facts[result.ids[0]]
    assert value(fact, "recognized") is True
    assert value(fact, "verdict.decision") == "explain"
    assert seen[0]["recognized"] is True
    assert seen[0]["score_band"] == "low"


def test_a_charge_abroad_through_an_unusual_channel_at_a_new_merchant_says_so(seed: Seed) -> None:
    card = seed.card()
    for day in (20, 15, 10):
        seed.charge(card, days_ago(day), "Plaza Vea")
    charge = seed.charge(card, days_ago(1), "SHEIN.COM 4821", channel="Web", transaction_country="US")

    _, [fact] = run("charge_facts", transaction_ref=charge)

    assert plain(fact)["verdict.reasons"]["values"] == ["foreign_country", "unusual_channel", "new_merchant"]
    assert value(fact, "verdict.score_band") == "low"
    assert value(fact, "charge.country") == "US"


def test_a_charge_without_a_score_has_no_band(seed: Seed) -> None:
    card = seed.card()
    charge = seed.charge(card, days_ago(3))
    seed.aws.transactions.update_item(
        Key={"customer_id": ME, "transaction_key": transaction_key(card, charge)},
        UpdateExpression="REMOVE fraud_score",
    )

    _, [fact] = run("charge_facts", transaction_ref=charge)

    assert value(fact, "verdict.score_band") == "none"


def test_case_status_lists_open_cases_with_their_code_stage_and_charge(
    account: dict[str, str], seed: Seed
) -> None:
    seed.case(uuid7(), status="Closed")

    _, facts = run("case_status")

    [case, aggregate] = facts
    model = plain(case)
    assert model["case_id"]["value"] == case_code(account["primax_charge"], "2031-03-01T15:00:00.000Z")
    assert model["stage"]["value"] == "in_review"
    assert model["opened_at"]["value"] == "2031-03-01"
    assert model["in_review_at"]["value"] == "2031-03-07"
    assert model["merchant"]["value"] == "Primax Av. Arequipa"
    assert model["last4"]["value"] == "4821"
    assert model["next_step"]["value"] == "review_in_progress"
    assert value(aggregate, "count") == 1


@pytest.mark.parametrize(
    ("status", "extra", "stage", "next_step"),
    [
        ("Open", {"assignment_date": None}, "opened", "fraud_team_contacts_you"),
        ("Open", {}, "assigned", "fraud_team_contacts_you"),
        ("Escalated", {}, "in_review", "review_in_progress"),
        ("Rejected", {"resolution_date": "2031-03-10T15:00:00.000Z"}, "resolved", "resolution_sent"),
        ("Closed", {}, "closed", "resolution_sent"),
    ],
)
def test_case_stages_map_from_the_dataset_status(
    seed: Seed, status: str, extra: dict[str, Any], stage: str, next_step: str
) -> None:
    complaint_id = uuid7()
    seed.case(complaint_id, status=status, area="fraud", **{k: v for k, v in extra.items() if v})
    if "assignment_date" in extra:
        seed.aws.complaints.update_item(
            Key={"customer_id": ME, "complaint_id": complaint_id}, UpdateExpression="REMOVE assignment_date"
        )

    _, [case, _] = run("case_status", case_ref=complaint_id)

    assert value(case, "stage") == stage
    assert value(case, "next_step") == next_step
    assert value(case, "type") == "fraud"
    assert ("resolved_at" in case.fields) is (stage == "resolved")


def test_case_status_returns_at_most_ten_newest_first(seed: Seed) -> None:
    for day in range(1, 13):
        seed.case(uuid7(), creation_date=f"2031-03-{day:02d}T15:00:00.000Z")

    _, facts = run("case_status")

    *cases, aggregate = facts
    assert [value(case, "opened_at") for case in cases][:2] == ["2031-03-12", "2031-03-11"]
    assert len(cases) == 10
    assert value(aggregate, "truncated") is True


def test_case_status_for_a_charge_without_a_case_is_empty(account: dict[str, str]) -> None:
    _, [aggregate] = run("case_status", transaction_ref=account["flagged"])

    assert value(aggregate, "count") == 0


def test_recall_reads_memory_newest_first_at_most_ten(seed: Seed) -> None:
    for day in range(1, 13):
        seed.memory(
            f"recognized_merchant#merchant {day}", f"Merchant {day}", f"2031-03-{day:02d}T12:00:00.000Z"
        )

    _, facts = run("recall")

    *memories, aggregate = facts
    assert len(memories) == 10
    assert value(memories[0], "merchant") == "Merchant 12"
    assert plain(memories[0])["note"] == {"type": "note", "value": "es mi gasolinera", "untrusted": True}
    assert value(aggregate, "truncated") is True


def test_recall_filters_by_merchant_and_by_charge(account: dict[str, str], seed: Seed) -> None:
    seed.memory("recognized_merchant#primax", "Primax", "2031-03-11T12:00:00.000Z", "cargo cada semana")

    _, by_merchant = run("recall", merchant="PRIMAX")
    _, by_charge = run("recall", transaction_ref=account["primax_charge"])
    _, nothing = run("recall", merchant="Tambo")

    assert [value(fact, "note") for fact in by_merchant[:-1]] == ["cargo cada semana"]
    assert [value(fact, "transaction_ref") for fact in by_charge[:-1]] == [account["primax_charge"]]
    assert value(nothing[-1], "count") == 0


def test_unprocessed_keys_are_retried_with_backoff_then_the_tool_is_unavailable(
    account: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, Any]] = []
    pauses: list[float] = []

    def never_drains(**request: Any) -> Any:
        calls.append(request)
        return {"Responses": {}, "UnprocessedKeys": request["RequestItems"]}

    monkeypatch.setattr("core.accounts.time.sleep", pauses.append)
    reader = Reader(context())
    monkeypatch.setattr(reader.accounts._transactions.meta.client, "batch_get_item", never_drains)

    _, facts = run("charge_facts", transaction_ref=account["flagged"])

    assert error_of(facts) == "unavailable"
    assert len(calls) == accounts_module.BATCH_ATTEMPTS * 3
    assert pauses[:3] == [0.05, 0.1, 0.2]


@pytest.fixture
def flaky(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    failures = [0]
    original = Reader.cards

    def cards(self: Reader, extra: Any = ()) -> Any:
        if failures[0] > 0:
            failures[0] -= 1
            raise ClientError({"Error": {"Code": "ProvisionedThroughputExceededException"}}, "Query")
        return original(self, extra)

    monkeypatch.setattr(Reader, "cards", cards)
    return failures


def test_a_dynamodb_error_is_retried_twice_then_becomes_an_unavailable_fact(
    account: dict[str, str], flaky: list[int]
) -> None:
    flaky[0] = 2
    _, facts = run("list_cards")
    assert facts[-1].kind == "cards"

    flaky[0] = 3
    _, facts = run("list_cards")
    assert error_of(facts) == "unavailable"
