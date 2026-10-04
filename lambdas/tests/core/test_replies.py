from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from core.facts import Ask, Ledger, Say, View
from core.facts.values import (
    Count,
    Day,
    FactIds,
    Instant,
    Label,
    Labels,
    Last4,
    Merchant,
    Money,
    Period,
    Ratio,
    Ref,
    Refs,
)
from core.replies import compose

NOW = datetime(2026, 10, 1, 15, 0, tzinfo=UTC)
NB = "\xa0"


def charge_ledger() -> Ledger:
    book = Ledger("PE", NOW)
    book.add(
        "charge",
        {
            "charge.transaction_ref": Ref("transaction", "tx-1"),
            "charge.card_ref": Ref("card", "card-1"),
            "charge.merchant": Merchant("Primax"),
            "charge.amount": Money(Decimal("120"), "PEN"),
            "charge.date": Instant(datetime(2026, 9, 27, 18, 0, tzinfo=UTC)),
            "verdict.explanation": Label("explanation", "prior_purchases"),
            "verdict.reasons": Labels("reason", ("foreign_country", "unknown_reason")),
            "habit.prior_count": Count(5, "purchase"),
            "habit.median_amount": Money(Decimal("58.5"), "PEN"),
            "habit.ratio_to_typical": Ratio(Decimal("2.05")),
            "similar": FactIds(()),
        },
    )
    book.locate("tx-2", "card-2")
    book.add(
        "similar",
        {
            "transaction_ref": Ref("transaction", "tx-2"),
            "amount": Money(Decimal("120"), "PEN"),
            "date": Instant(datetime(2026, 9, 28, 18, 0, tzinfo=UTC)),
        },
    )
    book.locate("tx-3", "card-1")
    book.add(
        "merchant_history",
        {
            "merchant": Merchant("Primax"),
            "count": Count(1, "purchase"),
            "typical_amount": Money(Decimal("58.5"), "PEN"),
            "period": Period(date(2026, 7, 2), date(2026, 10, 1)),
            "ids": Refs("transaction", ("tx-3",)),
        },
    )
    book.add(
        "card",
        {"card_ref": Ref("card", "card-1"), "type": Label("card_type", "debit"), "last4": Last4("4141")},
    )
    book.add(
        "spend",
        {
            "total": Money(Decimal("240"), "PEN"),
            "period": Period(date(2026, 9, 1), date(2026, 9, 30)),
            "compare_period": Period(date(2026, 8, 1), date(2026, 8, 31)),
            "merchant": Merchant("Primax"),
            "card_ref": Ref("card", "card-1"),
        },
    )
    return book


def test_a_charge_view_carries_clara_s_readings_rendered_in_the_customer_s_locale() -> None:
    reply = compose([Say("Mira."), View("charge", ("f1",))], charge_ledger(), "es", "composed")

    view = reply.parts[1]
    assert view == {
        "type": "view",
        "view": "charge",
        "items": [{"product_id": "card-1", "transaction_id": "tx-1"}],
        "readings": {
            "explanation": "ya habías comprado antes en este comercio",
            "reasons": [{"reason": "foreign_country", "text": "es en otro país"}],
            "habit": f"Hiciste 5 compras antes en este comercio; lo típico es S/{NB}58.50.",
            "compared": "Este cargo es unas 2 veces lo habitual.",
        },
    }
    assert "verdict" not in str(reply.parts)


def test_a_history_view_lists_the_purchases_with_their_card_and_its_readings() -> None:
    reply = compose([View("history", ("f3",))], charge_ledger(), "pt-BR", "composed")

    assert reply.parts == (
        {
            "type": "view",
            "view": "history",
            "items": [{"product_id": "card-1", "transaction_id": "tx-3"}],
            "readings": {
                "merchant": "Primax",
                "count": "1 compra",
                "typical_amount": f"PEN{NB}58,50",
                "period": "de 2 de julho a 1 de outubro",
            },
        },
    )


def test_ask_options_carry_a_label_by_code_and_keep_their_reads_in_the_draft_only() -> None:
    book = charge_ledger()

    reply = compose([Ask("which_one", ("f1", "f2")), Ask("show", ("f5",))], book, "es", "composed")

    which, show = reply.parts
    assert which == {
        "type": "ask",
        "ask": "which_one",
        "prompt": "¿Cuál es?",
        "options": [
            {"id": "tx-1", "label": f"Primax · S/{NB}120.00 · 27 de septiembre"},
            {"id": "tx-2", "label": f"S/{NB}120.00 · 28 de septiembre"},
        ],
    }
    assert show == {
        "type": "ask",
        "ask": "show",
        "options": [{"id": "movements", "label": "Ver esos movimientos"}],
    }
    assert reply.draft[-1] == {
        "type": "ask",
        "ask": "show",
        "facts": ["f5"],
        "options": [
            {
                "id": "movements",
                "read": {
                    "tool": "search_movements",
                    "args": {
                        "date_from": "2026-08-01",
                        "date_to": "2026-09-30",
                        "limit": 25,
                        "merchant": "Primax",
                        "card_ref": "card-1",
                    },
                },
            }
        ],
    }
    assert "read" not in str(reply.parts)
    assert [fact["id"] for fact in reply.facts] == ["f1", "f2", "f5"]


def test_a_card_option_names_the_card_by_type_and_last_digits() -> None:
    book = charge_ledger()
    book.add(
        "card",
        {"card_ref": Ref("card", "card-2"), "type": Label("card_type", "credit"), "last4": Last4("5555")},
    )

    [ask] = compose([Ask("which_one", ("f4", "f6"))], book, "en", "composed").parts

    assert [option["label"] for option in ask["options"]] == [
        "Debit card ending in 4141",
        "Credit card ending in 5555",
    ]


def test_a_part_that_no_longer_fits_is_left_out_of_the_reply() -> None:
    reply = compose([Say("Hola."), View("charge", ("f9",))], charge_ledger(), "es", "composed")

    assert [part["type"] for part in reply.parts] == ["say"]
    assert reply.draft == ({"type": "say", "text": "Hola."},)


def test_a_date_in_a_label_has_no_article_but_a_standalone_one_does() -> None:
    book = charge_ledger()
    book.add("day", {"date": Day(date(2026, 9, 2))})

    reply = compose([Say("Fue {f6.date}.")], book, "es", "composed")

    assert reply.text == "Fue el 2 de septiembre."


@pytest.mark.parametrize(
    ("locale", "days"),
    [("es", ("hoy", "ayer")), ("pt-BR", ("hoje", "ontem")), ("en", ("today", "yesterday"))],
)
def test_an_option_of_today_or_yesterday_says_so_like_the_answer_does(
    locale: str, days: tuple[str, str]
) -> None:
    book = Ledger("PE", NOW)
    for index, hours in ((1, 2), (2, 26)):
        book.add(
            "movement",
            {
                "transaction_ref": Ref("transaction", f"tx-{index}"),
                "card_ref": Ref("card", "card-1"),
                "merchant": Merchant("Primax"),
                "amount": Money(Decimal("120"), "PEN"),
                "date": Instant(NOW - timedelta(hours=hours)),
            },
        )

    [ask] = [part for part in compose([Ask("which_one", ("f1", "f2"))], book, locale, "composed").parts]

    assert [option["label"].rsplit(" · ", 1)[1] for option in ask["options"]] == list(days)


def test_a_view_of_the_series_says_it_lists_them_and_counts_them() -> None:
    book = Ledger("PE", NOW)
    book.locate("tx-1", "card-1")
    series = book.add("recurring", {"merchant": Merchant("Movistar"), "ids": Refs("transaction", ("tx-1",))})
    book.add("recurring_list", {"count": Count(1, "subscription"), "ids": FactIds((series.id,))})

    [view] = compose([View("movements", ("f2",))], book, "es", "composed").parts

    assert view["readings"] == {"kind": "series", "count": "1 cargo recurrente"}
