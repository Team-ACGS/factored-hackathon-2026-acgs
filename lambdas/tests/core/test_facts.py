import json
import subprocess
import sys
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from core.facts import Ask, Ledger, Say, View, check, fallback, parse_parts, render, render_text
from core.facts.catalog import LABELS, LOCALES, NOUNS, STATUS_LABELS
from core.facts.lexicon import CATALOG_MERCHANTS, COMMON_WORD_MERCHANTS
from core.facts.render import format_money
from core.facts.values import (
    CaseCode,
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
    Merchant,
    Money,
    Note,
    Period,
    Ratio,
    Ref,
    Refs,
    Status,
    Trace,
)
from crud.catalog import COUNTRIES, SUSPICIOUS_POOL

NOW = datetime(2026, 10, 1, 15, 0, tzinfo=UTC)
NB = "\xa0"

FORMAT_MONEY = {
    ("MXN", "es"): "$1,234,567.50",
    ("MXN", "pt-BR"): f"${NB}1.234.567,50",
    ("MXN", "en"): "$1,234,567.50",
    ("PEN", "es"): f"S/{NB}1,234,567.50",
    ("PEN", "pt-BR"): f"PEN{NB}1.234.567,50",
    ("PEN", "en"): f"PEN{NB}1,234,567.50",
    ("COP", "es"): f"${NB}1.234.568",
    ("COP", "pt-BR"): f"${NB}1.234.568",
    ("COP", "en"): "$1,234,568",
    ("ARS", "es"): f"${NB}1.234.567,50",
    ("ARS", "pt-BR"): f"${NB}1.234.567,50",
    ("ARS", "en"): "$1,234,567.50",
    ("USD", "es"): "$1,234,567.50",
    ("USD", "pt-BR"): f"${NB}1.234.567,50",
    ("USD", "en"): "$1,234,567.50",
    ("BRL", "es"): "R$1,234,567.50",
    ("BRL", "pt-BR"): f"R${NB}1.234.567,50",
    ("BRL", "en"): "R$1,234,567.50",
}


def ledger() -> Ledger:
    return Ledger("PE", NOW)


def codes(
    text: str, book: Ledger | None = None, locale: str = "es", chunks: tuple[str, ...] = ()
) -> list[str]:
    return [error.code for error in check([Say(text)], book or ledger(), locale, chunks)]


@pytest.mark.parametrize(("currency", "locale"), sorted(FORMAT_MONEY))
def test_money_matches_the_apps_format_money_in_every_currency_and_language(
    currency: str, locale: str
) -> None:
    assert format_money(Decimal("1234567.5"), currency, locale) == FORMAT_MONEY[(currency, locale)]


@pytest.mark.parametrize(
    ("amount", "currency", "locale", "expected"),
    [
        ("49.9", "PEN", "es", f"S/{NB}49.90"),
        ("0.05", "BRL", "pt-BR", f"R${NB}0,05"),
        ("999.995", "MXN", "en", "$1,000.00"),
        ("49.9", "COP", "es", f"${NB}50"),
        ("1000", "ARS", "es", f"${NB}1.000,00"),
        ("12.5", "EUR", "en", f"EUR{NB}12.50"),
    ],
)
def test_money_rounds_half_up_and_groups_like_intl(
    amount: str, currency: str, locale: str, expected: str
) -> None:
    assert format_money(Decimal(amount), currency, locale) == expected


@pytest.mark.parametrize(
    ("value", "rendered"),
    [
        (Day(date(2026, 9, 17)), {"es": "17 de septiembre", "pt-BR": "17 de setembro", "en": "September 17"}),
        (Day(date(2026, 10, 1)), {"es": "hoy", "pt-BR": "hoje", "en": "today"}),
        (Day(date(2026, 9, 30)), {"es": "ayer", "pt-BR": "ontem", "en": "yesterday"}),
        (
            Day(date(2025, 12, 24)),
            {"es": "24 de diciembre de 2025", "pt-BR": "24 de dezembro de 2025", "en": "December 24, 2025"},
        ),
        (
            Instant(datetime(2026, 9, 17, 20, 12, tzinfo=UTC)),
            {
                "es": "17 de septiembre, 15:12",
                "pt-BR": "17 de setembro, 15:12",
                "en": "September 17, 3:12 PM",
            },
        ),
        (
            Instant(datetime(2026, 10, 1, 4, 30, tzinfo=UTC)),
            {"es": "ayer, 23:30", "pt-BR": "ontem, 23:30", "en": "yesterday, 11:30 PM"},
        ),
        (
            Period(date(2026, 9, 1), date(2026, 9, 30)),
            {"es": "del 1 al 30 de septiembre", "pt-BR": "de 1 a 30 de setembro", "en": "September 1 to 30"},
        ),
        (
            Period(date(2026, 8, 30), date(2026, 9, 5)),
            {
                "es": "del 30 de agosto al 5 de septiembre",
                "pt-BR": "de 30 de agosto a 5 de setembro",
                "en": "August 30 to September 5",
            },
        ),
        (
            Period(date(2026, 9, 30), date(2026, 10, 1)),
            {
                "es": "del 30 de septiembre al 1 de octubre",
                "pt-BR": "de 30 de setembro a 1 de outubro",
                "en": "September 30 to October 1",
            },
        ),
        (Last4("4821"), {"es": "terminada en 4821", "pt-BR": "final 4821", "en": "ending in 4821"}),
        (Status("card", "Blocked"), {"es": "bloqueada", "pt-BR": "bloqueado", "en": "blocked"}),
        (Status("transaction", "Reversed"), {"es": "revertida", "pt-BR": "estornada", "en": "reversed"}),
        (Status("stage", "in_review"), {"es": "en revisión", "pt-BR": "em análise", "en": "in review"}),
        (Label("cadence", "monthly"), {"es": "mensual", "pt-BR": "mensal", "en": "monthly"}),
        (
            Labels("reason", ("foreign_country", "new_merchant")),
            {
                "es": "es en otro país y es tu primera compra en este comercio",
                "pt-BR": "é em outro país e é a sua primeira compra neste estabelecimento",
                "en": "it is in another country and it is your first purchase at this merchant",
            },
        ),
        (
            Ratio(Decimal("3.1")),
            {
                "es": "unas 3 veces lo habitual",
                "pt-BR": "cerca de 3 vezes o habitual",
                "en": "about 3 times the usual",
            },
        ),
        (Ratio(Decimal("1.05")), {"es": "lo habitual", "pt-BR": "o habitual", "en": "about the usual"}),
        (
            Ratio(Decimal("9")),
            {
                "es": "más de 5 veces lo habitual",
                "pt-BR": "mais de 5 vezes o habitual",
                "en": "more than 5 times the usual",
            },
        ),
        (Country("BR"), {"es": "Brasil", "pt-BR": "Brasil", "en": "Brazil"}),
        (Country("CL"), {"es": "CL", "pt-BR": "CL", "en": "CL"}),
        (
            Note("es mi gasolinera"),
            {"es": "«es mi gasolinera»", "pt-BR": "“es mi gasolinera”", "en": "“es mi gasolinera”"},
        ),
        (
            Merchant("Primax Av. Arequipa"),
            {"es": "Primax Av. Arequipa", "pt-BR": "Primax Av. Arequipa", "en": "Primax Av. Arequipa"},
        ),
        (Label("category", "Gaming"), {"es": "Gaming", "pt-BR": "Gaming", "en": "Gaming"}),
    ],
)
def test_one_fact_renders_in_each_locale(value: object, rendered: dict[str, str]) -> None:
    book = ledger()
    fact = book.add("probe", {"value": value})  # type: ignore[dict-item]

    for locale, expected in rendered.items():
        assert render_text(f"{{{fact.id}.value}}", book, locale) == expected


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (0, {"es": "0 compras", "pt-BR": "0 compra", "en": "0 purchases"}),
        (1, {"es": "1 compra", "pt-BR": "1 compra", "en": "1 purchase"}),
        (3, {"es": "3 compras", "pt-BR": "3 compras", "en": "3 purchases"}),
    ],
)
def test_counts_follow_the_plural_table_of_each_locale(count: int, expected: dict[str, str]) -> None:
    book = ledger()
    fact = book.add("probe", {"count": Count(count, "purchase")})

    for locale, text in expected.items():
        assert render_text(f"{{{fact.id}.count}}", book, locale) == text


def test_every_catalog_entry_has_all_three_locales() -> None:
    locales = [
        *(set(entry) for entry in NOUNS.values()),
        *(set(labels) for domain in STATUS_LABELS.values() for labels in domain.values()),
        *(set(labels) for domain in LABELS.values() for labels in domain.values()),
    ]
    assert all(entry == set(LOCALES) for entry in locales)


def test_every_renderable_type_renders_and_every_trace_only_type_is_refused_by_the_check() -> None:
    book = ledger()
    renderable = book.add(
        "probe",
        {
            "money": Money(Decimal(1), "PEN"),
            "date": Day(date(2026, 9, 1)),
            "datetime": Instant(NOW),
            "period": Period(date(2026, 9, 1), date(2026, 9, 2)),
            "count": Count(2, "day"),
            "last4": Last4("1234"),
            "status": Status("card", "Active"),
            "enum": Label("direction", "more"),
            "enum_list": Labels("reason", ("score_high",)),
            "merchant": Merchant("Primax"),
            "city": City("Lima"),
            "country": Country("PE"),
            "case_id": CaseCode("CLR-2026-000001"),
            "ratio": Ratio(Decimal(2)),
            "note": Note("hola"),
        },
    )
    trace_only = book.add(
        "probe",
        {
            "ref": Ref("card", "c1"),
            "refs": Refs("transaction", ("t1",)),
            "ids": FactIds(("f1",)),
            "flag": Flag(True),
            "trace": Trace("x"),
        },
    )

    for locale in LOCALES:
        for field in renderable.fields:
            text = f"{{{renderable.id}.{field}}}"
            assert check([Say(text)], book, locale) == []
            assert render_text(text, book, locale)
        for field in trace_only.fields:
            assert codes(f"{{{trace_only.id}.{field}}}", book, locale) == ["trace_only_reference"]


def test_the_merchant_lexicon_mirrors_the_crud_catalog() -> None:
    catalog = {merchant.name for country in COUNTRIES.values() for merchant in country.merchants}

    assert catalog | {merchant.name for merchant in SUSPICIOUS_POOL} == CATALOG_MERCHANTS
    assert COMMON_WORD_MERCHANTS <= CATALOG_MERCHANTS


def spend_ledger() -> Ledger:
    book = ledger()
    book.add(
        "spend",
        {
            "total": Money(Decimal("240"), "PEN"),
            "count": Count(2, "purchase"),
            "period": Period(date(2026, 9, 1), date(2026, 9, 30)),
            "merchant": Merchant("Primax"),
            "card_ref": Ref("card", "card-1"),
        },
    )
    book.add("movement", {"merchant": Merchant("7-Eleven"), "transaction_ref": Ref("transaction", "tx-1")})
    return book


@pytest.mark.parametrize(
    ("text", "locale", "expected"),
    [
        ("Gastaste {f1.total} en {f1.merchant}.", "es", []),
        ("Gastaste {f9.total}.", "es", ["unresolved_reference"]),
        ("Gastaste {f1.average}.", "es", ["unresolved_reference"]),
        ("Tu tarjeta {f1.card_ref}.", "es", ["trace_only_reference"]),
        ("Según el banco [p:pe-claims-03#2].", "es", []),
        ("Según el banco [p:pe-claims-09#1].", "es", ["unknown_citation"]),
        ("Gastaste 240 en Primax.", "es", ["digit_outside_reference"]),
        ("Gastaste S/ {f1.total}.", "es", ["currency_outside_reference"]),
        ("Son {f1.total} USD.", "es", ["currency_outside_reference"]),
        ("Pagaste en dólares $ hoy.", "es", ["currency_outside_reference", "date_outside_reference"]),
        ("Fue en septiembre.", "es", ["date_outside_reference"]),
        ("Fue el lunes.", "es", ["date_outside_reference"]),
        ("Lo compraste ayer.", "es", ["date_outside_reference"]),
        ("Este mes llevas {f1.total}; el mes pasado y esta semana también.", "es", []),
        ("Foi ontem.", "pt-BR", ["date_outside_reference"]),
        ("Neste mês e no mês passado.", "pt-BR", []),
        ("It was in September.", "en", ["date_outside_reference"]),
        ("You may see it this month or last month.", "en", []),
        ("Es tu primera compra en {f1.merchant}.", "es", []),
        ("Es tu segunda compra en {f1.merchant}.", "es", ["number_word_outside_reference"]),
        ("Uno de tus cargos y una compra.", "es", []),
        ("Hiciste tres compras.", "es", ["number_word_outside_reference"]),
        ("Hiciste once compras.", "es", ["number_word_outside_reference"]),
        ("You did this once.", "en", []),
        ("You made two purchases.", "en", ["number_word_outside_reference"]),
        ("One of them is your first purchase.", "en", []),
        ("Segundo o banco, é a sua primeira compra.", "pt-BR", []),
        ("É a sua segunda compra.", "pt-BR", ["number_word_outside_reference"]),
        ("Você fez duas compras.", "pt-BR", ["number_word_outside_reference"]),
        ("Compraste en 7-Eleven.", "es", []),
        ("Compraste en primax.", "es", ["merchant_outside_reference"]),
        ("Compraste en Netflix.", "es", ["merchant_outside_reference"]),
        ("Claro, te ayudo.", "es", []),
        ("Llama al +51 999 888 777.", "es", ["contact_outside_facts"]),
        ("Entra a www.banco.pe/ayuda.", "es", ["contact_outside_facts"]),
        ("Escribe a ayuda@banco.pe.", "es", ["contact_outside_facts"]),
        ("Revisa bancolatam.com.", "es", ["contact_outside_facts"]),
        ("Parece un fraude.", "es", ["fraud_word"]),
        ("That looks fraudulent.", "en", ["fraud_word"]),
        ("Tranquilo, es seguro.", "es", ["safety_claim"]),
        ("Fique tranquilo, é seguro.", "pt-BR", ["safety_claim"]),
        ("Don't worry, it's safe.", "en", ["safety_claim"]),
        ("Te vamos a devolver el dinero.", "es", ["money_promise"]),
        ("Te devolveremos la compra.", "es", ["money_promise"]),
        ("Vamos devolver o valor.", "pt-BR", ["money_promise"]),
        ("You will get a refund.", "en", ["money_promise"]),
        ("Puedes hablar con un abogado.", "es", ["legal_term"]),
        ("La ley te protege.", "es", ["legal_term"]),
        ("You could go to court.", "en", ["legal_term"]),
        ("Puedes hablar con una persona del banco.", "es", []),
    ],
)
def test_the_check_applies_each_rule_outside_references(text: str, locale: str, expected: list[str]) -> None:
    assert codes(text, spend_ledger(), locale, ("pe-claims-03#2",)) == expected


def test_the_check_only_reads_number_words_of_the_reply_locale() -> None:
    assert codes("We did this once.", locale="en") == []
    assert codes("Pagaste once.", locale="es") == ["number_word_outside_reference"]


def test_views_and_asks_may_point_only_at_ids_returned_this_turn() -> None:
    book = spend_ledger()

    assert check([View("movements", ("tx-1",)), Ask("block_card", "card-1")], book, "es") == []
    errors = check([View("movements", ("tx-1", "tx-9")), Ask("block_card", "card-9")], book, "es")
    assert [(error.code, error.text) for error in errors] == [
        ("view_id_unknown", "tx-9"),
        ("ask_target_unknown", "card-9"),
    ]


def test_check_errors_carry_the_span_and_a_repair_instruction_and_serialize() -> None:
    [error] = check([Say("Hola."), Say("Gastaste 240 de {f1.total}.")], spend_ledger(), "es")

    assert (error.part, error.span, error.text) == (1, (9, 12), "240")
    assert json.loads(json.dumps(error.to_dict())) == {
        "code": "digit_outside_reference",
        "part": 1,
        "span": [9, 12],
        "text": "240",
        "instruction": error.instruction,
    }
    assert error.instruction


def test_parts_parse_from_the_wire_and_render_every_reference() -> None:
    parts = parse_parts(
        [
            {"type": "say", "text": "Gastaste {f1.total} en {f1.count} [p:pe-claims-03#2]."},
            {"type": "view", "view": "movements", "ids": ["tx-1"]},
            {"type": "ask", "ask": "block_card", "target": "card-1"},
        ]
    )

    assert render(parts, spend_ledger(), "es") == [
        {
            "type": "say",
            "text": f"Gastaste S/{NB}240.00 en 2 compras.",
            "facts": ["f1"],
            "citations": ["pe-claims-03#2"],
        },
        {"type": "view", "view": "movements", "ids": ["tx-1"]},
        {"type": "ask", "ask": "block_card", "target": "card-1"},
    ]


def full_ledger() -> Ledger:
    book = ledger()
    card = book.add(
        "card",
        {
            "card_ref": Ref("card", "card-1"),
            "type": Label("card_type", "credit"),
            "last4": Last4("4821"),
            "status": Status("card", "Active"),
        },
    )
    book.add("cards", {"count": Count(1, "card"), "ids": FactIds((card.id,))})
    row = book.add(
        "movement", {"transaction_ref": Ref("transaction", "tx-1"), "merchant": Merchant("Primax")}
    )
    book.add(
        "movements",
        {
            "count": Count(1, "movement"),
            "ids": FactIds((row.id,)),
            "period": Period(date(2026, 9, 1), date(2026, 9, 30)),
        },
    )
    book.add(
        "movements",
        {
            "count": Count(0, "movement"),
            "ids": FactIds(()),
            "period": Period(date(2026, 9, 1), date(2026, 9, 2)),
        },
    )
    book.add(
        "merchant_history",
        {"merchant": Merchant("Primax"), "count": Count(3, "purchase"), "last_date": Day(date(2026, 9, 14))},
    )
    book.add("merchant_history", {"merchant": Merchant("Tambo+"), "count": Count(0, "purchase")})
    book.add(
        "spend",
        {
            "total": Money(Decimal(240), "PEN"),
            "count": Count(2, "purchase"),
            "period": Period(date(2026, 9, 1), date(2026, 9, 30)),
            "compare_total": Money(Decimal(180), "PEN"),
            "compare_period": Period(date(2026, 8, 1), date(2026, 8, 31)),
        },
    )
    book.add(
        "recurring",
        {
            "merchant": Merchant("Netflix"),
            "cadence": Label("cadence", "monthly"),
            "typical_amount": Money(Decimal("49.9"), "PEN"),
            "last4": Last4("4821"),
        },
    )
    book.add("recurring_list", {"count": Count(0, "subscription")})
    book.add(
        "charge",
        {
            "charge.merchant": Merchant("GLOBALPAY 1234"),
            "charge.amount": Money(Decimal(49), "PEN"),
            "charge.status": Status("transaction", "Approved"),
        },
    )
    book.add(
        "case",
        {
            "case_id": CaseCode("CLR-2026-821217"),
            "type": Label("case_type", "claim"),
            "stage": Status("stage", "in_review"),
        },
    )
    book.add("cases", {"count": Count(0, "case")})
    book.add("memory", {"note": Note("es mi gasolinera")})
    book.add("memory", {"merchant": Merchant("Primax")})
    book.add("memories", {"count": Count(0, "memory")})
    book.add("error", {"tool": Trace("recall"), "error": Trace("unavailable")})
    return book


@pytest.mark.parametrize("locale", LOCALES)
def test_the_fallback_answers_from_the_same_ledger_and_passes_the_check(locale: str) -> None:
    book = full_ledger()

    parts = fallback("answer", book, locale)

    assert check(parts, book, locale) == []
    says = [part for part in render(parts, book, locale) if part["type"] == "say"]
    assert len(says) == 16
    assert all("{" not in say["text"] for say in says)
    assert {"type": "view", "view": "movements", "ids": ["tx-1"]} in render(parts, book, locale)


@pytest.mark.parametrize("locale", LOCALES)
def test_the_unavailable_fallback_passes_the_check(locale: str) -> None:
    for key in ("unavailable", "answer"):
        parts = fallback(key, ledger(), locale)
        assert len(parts) == 1
        assert check(parts, ledger(), locale) == []


def test_facts_check_render_and_fallback_never_load_an_aws_client() -> None:
    probe = (
        "import sys; import core.facts; "
        "assert not [m for m in sys.modules if m.split('.')[0] in ('boto3', 'botocore')], 'aws loaded'"
    )

    subprocess.run([sys.executable, "-c", probe], check=True)  # noqa: S603
