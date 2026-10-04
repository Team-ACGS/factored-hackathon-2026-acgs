import json
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from core.facts import (
    Ask,
    Ledger,
    Part,
    Say,
    View,
    check,
    fallback,
    parse_parts,
    render,
    render_text,
    render_value,
)
from core.facts.catalog import LABELS, LOCALES, NOUNS, STATUS_LABELS
from core.facts.check import repair_instruction, tidy, tidy_reply
from core.facts.fallback import FIELD, TEMPLATES
from core.facts.lexicon import CATALOG_MERCHANTS, COMMON_WORD_MERCHANTS
from core.facts.render import format_money
from core.facts.values import (
    POLICY_CHUNK,
    CaseCode,
    Channel,
    City,
    Count,
    Country,
    Day,
    Fact,
    FactIds,
    Flag,
    Instant,
    Label,
    Labels,
    Last4,
    Merchant,
    Money,
    Note,
    Passage,
    Percent,
    Period,
    Ratio,
    Ref,
    Refs,
    Status,
    Text,
    Trace,
    Url,
    Value,
)
from core.replies import compose
from core.rules import TurnState, allowed_asks
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


def codes(text: str, book: Ledger | None = None, locale: str = "es") -> list[str]:
    return [error.code for error in check([Say(text)], book or ledger(), locale)]


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
        (
            Day(date(2026, 9, 17)),
            {"es": "el 17 de septiembre", "pt-BR": "em 17 de setembro", "en": "September 17"},
        ),
        (Day(date(2026, 10, 1)), {"es": "hoy", "pt-BR": "hoje", "en": "today"}),
        (Day(date(2026, 9, 30)), {"es": "ayer", "pt-BR": "ontem", "en": "yesterday"}),
        (
            Day(date(2025, 12, 24)),
            {
                "es": "el 24 de diciembre de 2025",
                "pt-BR": "em 24 de dezembro de 2025",
                "en": "December 24, 2025",
            },
        ),
        (
            Instant(datetime(2026, 9, 17, 20, 12, tzinfo=UTC)),
            {
                "es": "el 17 de septiembre a las 15:12",
                "pt-BR": "em 17 de setembro às 15:12",
                "en": "September 17 at 3:12 PM",
            },
        ),
        (
            Instant(datetime(2026, 9, 17, 6, 5, tzinfo=UTC)),
            {
                "es": "el 17 de septiembre a la 01:05",
                "pt-BR": "em 17 de setembro à 01:05",
                "en": "September 17 at 1:05 AM",
            },
        ),
        (
            Instant(datetime(2026, 10, 1, 4, 30, tzinfo=UTC)),
            {"es": "ayer a las 23:30", "pt-BR": "ontem às 23:30", "en": "yesterday at 11:30 PM"},
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


CHUNK = "pe-dispute-lifecycle-v1-f1-s3-c2"


def with_chunk(book: Ledger) -> Ledger:
    book.add(
        POLICY_CHUNK,
        {
            "chunk_id": Trace(CHUNK),
            "title": Text("Ciclo de una aclaración"),
            "text": Passage("La revisión toma hasta 10 días hábiles. Llama al +51 1 600 2000."),
            "figures.claims.review_time": Count(10, "business_day"),
            "figures.channels.phone": Channel("phone", "+51 1 600 2000"),
            "figures.channels.app_claims": Channel("app_path", "Ayuda y aclaraciones > Tus aclaraciones"),
            "figures.fees.foreign_transaction": Percent(Decimal("3.5")),
        },
        prefix="p",
    )
    return book


@pytest.mark.parametrize(
    ("text", "locale", "expected"),
    [
        ("Gastaste {f1.total} en {f1.merchant}.", "es", []),
        ("Gastaste {f9.total}.", "es", ["unresolved_reference"]),
        ("Gastaste {f1.average}.", "es", ["unresolved_reference"]),
        ("Tu tarjeta {f1.card_ref}.", "es", ["trace_only_reference"]),
        ("Según el banco [p:pe-dispute-lifecycle-v1-f1-s3-c2].", "es", []),
        ("Según el banco [p:pe-dispute-lifecycle-v1-f1-s9-c1].", "es", ["unknown_citation"]),
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
        ("Llama al +51 999 888 777.", "es", ["uncited_process", "contact_outside_facts"]),
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
        ("No sé la fecha del desembolso.", "es", ["money_promise"]),
        ("La devolución se procesa luego.", "es", ["money_promise"]),
        ("A devolução depende da análise.", "pt-BR", ["money_promise"]),
        ("No sé cuándo llegará el dinero.", "es", ["money_promise"]),
        ("Lo que ocurra con el dinero depende de la revisión.", "es", ["money_promise"]),
        ("Não sei quando o dinheiro vai chegar.", "pt-BR", ["money_promise"]),
        ("I cannot tell when the money will arrive.", "en", ["money_promise"]),
        ("¿Cuánto dinero gastaste?", "es", []),
        ("You will get a refund.", "en", ["money_promise"]),
        ("Puedes hablar con un abogado.", "es", ["uncited_process", "legal_term"]),
        ("La ley te protege.", "es", ["legal_term"]),
        ("You could go to court.", "en", ["legal_term"]),
        ("Puedes hablar con una persona del banco.", "es", ["uncited_process"]),
        ("No puedo prometerte una fecha exacta.", "es", ["promise_talk"]),
        ("Não posso fazer promessas sobre o prazo.", "pt-BR", ["promise_talk"]),
        ("I cannot promise a date.", "en", ["promise_talk"]),
        ("No puedo decirte una fecha exacta.", "es", ["promise_talk"]),
        ("No puedo anticipar el resultado.", "es", ["promise_talk"]),
        ("Não posso antecipar o resultado.", "pt-BR", ["promise_talk"]),
        ("No pude revisar eso ahora.", "es", []),
        ("Hoy tienes 2 tarjetas.", "es", ["digit_outside_reference"]),
        ("Hoy tienes tus tarjetas activas.", "es", []),
        ("Hoje você tem seus cartões ativos.", "pt-BR", []),
        ("Fue hoy.", "es", ["date_outside_reference"]),
        ("Los más recientes aparecen a continuación.", "es", ["location_talk"]),
        ("Aquí puedes verlos todos.", "es", ["location_talk"]),
        ("As mais recentes estão abaixo.", "pt-BR", ["location_talk"]),
        ("You can see them below.", "en", ["location_talk"]),
        ("Este cargo está por debajo de lo habitual.", "es", []),
        ("A continuación te explico el proceso.", "es", []),
        ("Ese cargo está muy por debajo de tu promedio y aquí no veo otro.", "es", []),
        ("It is below your usual spend.", "en", []),
        ("Here is what I found.", "en", []),
        ("O valor ficou abaixo do habitual.", "pt-BR", []),
        ("El banco le asignó un nivel de riesgo elevado.", "es", ["risk_talk"]),
        ("O nível de risco detectado foi alto.", "pt-BR", ["risk_talk"]),
        ("The bank flagged it as high risk.", "en", ["risk_talk"]),
        ("El banco la revisará y te responderá pronto.", "es", ["told_promise"]),
        ("O banco vai te responder.", "pt-BR", ["told_promise"]),
        ("The bank will get back to you.", "en", ["told_promise"]),
        ("Para hacerlo, comunícate directamente con el banco.", "es", ["uncited_process"]),
        ("Necesitas cancelarlas directamente con cada proveedor.", "es", ["uncited_process"]),
        ("Você precisa cancelar com cada empresa.", "pt-BR", ["uncited_process"]),
        ("You should call the bank.", "en", ["uncited_process"]),
    ],
)
def test_the_check_applies_each_rule_outside_references(text: str, locale: str, expected: list[str]) -> None:
    assert codes(text, with_chunk(spend_ledger()), locale) == expected


def test_the_check_only_reads_number_words_of_the_reply_locale() -> None:
    assert codes("We did this once.", locale="en") == []
    assert codes("Pagaste once.", locale="es") == ["number_word_outside_reference"]


def view_ledger() -> Ledger:
    book = ledger()
    for index, digits in ((1, "4141"), (2, "5555")):
        book.add(
            "card",
            {
                "card_ref": Ref("card", f"card-{index}"),
                "type": Label("card_type", "credit"),
                "last4": Last4(digits),
            },
        )
    rows = [
        book.add(
            "movement",
            {
                "transaction_ref": Ref("transaction", f"tx-{index}"),
                "card_ref": Ref("card", "card-1"),
                "merchant": Merchant("Primax"),
                "amount": Money(Decimal("120"), "PEN"),
                "date": Instant(datetime(2026, 9, 27, 18, 0, tzinfo=UTC)),
            },
        )
        for index in (1, 2)
    ]
    book.add("movements", {"count": Count(2, "movement"), "ids": FactIds(tuple(row.id for row in rows))})
    book.locate("tx-7", "card-2")
    book.add(
        "merchant_history",
        {
            "merchant": Merchant("Primax"),
            "count": Count(1, "purchase"),
            "ids": Refs("transaction", ("tx-7",)),
        },
    )
    book.add("merchant_history", {"merchant": Merchant("Tambo+"), "count": Count(0, "purchase")})
    book.add(
        "case",
        {"case_ref": Ref("case", "case-1"), "transaction_ref": Ref("transaction", "tx-1")},
    )
    return book


def check_codes(
    parts: list[Part], book: Ledger, allowed: frozenset[str] = frozenset()
) -> list[tuple[str, str]]:
    return [(error.code, error.text) for error in check(parts, book, "es", allowed)]


def test_a_view_shows_only_facts_returned_this_turn_that_fit_it() -> None:
    book = view_ledger()

    assert (
        check_codes([View("movements", ("f5",)), View("cards", ("f1", "f2")), View("case", ("f8",))], book)
        == []
    )
    assert check_codes([View("movements", ("f9",))], book) == [("view_fact_unknown", "f9")]
    assert check_codes([View("charge", ("f3",))], book) == [("view_fact_unfit", "f3")]
    assert check_codes([View("card", ("f1", "f2"))], book) == [("view_fact_unfit", "f2")]
    assert check_codes([View("history", ("f7",))], book) == [("view_empty", "f7")]
    assert check_codes([View("ledger", ("f5",))], book) == [("view_unknown", "ledger")]


def test_an_ask_outside_allowed_asks_never_passes_the_check() -> None:
    book = view_ledger()
    allowed = allowed_asks(TurnState(), book)

    assert allowed == {"which_one", "show", "talk_to_person"}
    assert check_codes([Ask("which_one", ("f3", "f4"))], book, allowed) == []
    assert check_codes([Ask("show", ("f8",))], book, allowed) == []
    assert check_codes([Ask("block_card", ("f1",))], book, allowed) == [("ask_not_allowed", "block_card")]
    assert check_codes([Ask("which_one", ("f3", "f4"))], book) == [("ask_not_allowed", "which_one")]
    assert check_codes([Ask("which_one", ("f3",))], book, allowed) == [("ask_options_count", "f3")]
    assert check_codes([Ask("which_one", ("f3", "f1"))], book, allowed) == [("ask_options_mixed", "f1")]
    assert check_codes([Ask("which_one", ("f3", "f3"))], book, allowed) == [("ask_options_repeated", "f3")]
    assert check_codes([Ask("show", ("f6",))], book, allowed) == [("ask_fact_unfit", "f6")]


def test_which_one_is_refused_when_the_search_matched_more_charges_than_its_options() -> None:
    book = view_ledger()
    book.facts["f5"] = Fact("f5", "movements", {**book.facts["f5"].fields, "count": Count(13, "movement")})

    assert check_codes([Ask("which_one", ("f3", "f4"))], book, frozenset({"which_one"})) == [
        ("ask_options_partial", "f3")
    ]


def test_allowed_asks_need_candidates_and_never_repeat_the_choice_just_made() -> None:
    lone = ledger()
    lone.add("card", {"card_ref": Ref("card", "card-1"), "last4": Last4("4141")})

    assert allowed_asks(TurnState(), lone) == {"show", "talk_to_person"}
    assert allowed_asks(TurnState("which_one"), view_ledger()) == {"show", "talk_to_person"}
    assert allowed_asks(TurnState("show"), view_ledger()) == {"which_one", "talk_to_person"}
    assert allowed_asks(TurnState(), ledger()) == {"talk_to_person"}
    assert allowed_asks(TurnState(asking="block_card"), view_ledger()) == {"block_card"}


def test_a_count_reference_followed_by_its_noun_is_a_doubled_noun() -> None:
    book = spend_ledger()

    assert codes("Hiciste {f1.count} compras en tu tarjeta.", book) == ["noun_after_count"]
    assert codes("Tienes {f1.count} cargos.", book) == ["noun_after_count"]
    assert codes("Hiciste {f1.count} en tu tarjeta.", book) == []
    assert codes("Hiciste {f1.count}, compras pequeñas.", book) == []


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
            {
                "type": "say",
                "text": "Gastaste {f1.total} en {f1.count} [p:pe-dispute-lifecycle-v1-f1-s3-c2].",
            },
            {"type": "view", "view": "movements", "facts": ["f2"]},
            {"type": "ask", "ask": "show", "facts": ["f1"]},
        ]
    )

    assert render(parts, with_chunk(spend_ledger()), "es") == [
        {
            "type": "say",
            "text": f"Gastaste S/{NB}240.00 en 2 compras.",
            "facts": ["f1"],
            "citations": ["pe-dispute-lifecycle-v1-f1-s3-c2"],
        },
        {"type": "view", "view": "movements", "facts": ["f2"]},
        {"type": "ask", "ask": "show", "facts": ["f1"]},
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
        "movement",
        {
            "transaction_ref": Ref("transaction", "tx-1"),
            "card_ref": Ref("card", "card-1"),
            "merchant": Merchant("Primax"),
        },
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
    reply = compose(parts, book, locale, "fallback")
    says = [part for part in reply.parts if part["type"] == "say"]
    assert len(says) == 12
    assert all("{" not in say["text"] for say in says)
    assert {
        "type": "view",
        "view": "movements",
        "items": [{"product_id": "card-1", "transaction_id": "tx-1"}],
    } in [{key: value for key, value in part.items() if key != "readings"} for part in reply.parts]


def test_the_fallback_names_each_card_and_period_in_one_sentence_per_kind() -> None:
    book = ledger()
    for card, digits, count in (("card-1", "4141", 32), ("card-2", "5555", 27)):
        book.add(
            "movements",
            {
                "card_ref": Ref("card", card),
                "last4": Last4(digits),
                "count": Count(count, "movement"),
                "ids": FactIds(()),
                "period": Period(date(2026, 9, 1), date(2026, 9, 30)),
            },
        )
    book.add("error", {"tool": Trace("search_movements"), "error": Trace("unavailable")})
    book.add("error", {"tool": Trace("card_status"), "error": Trace("unavailable")})

    reply = compose(fallback("answer", book, "es"), book, "es", "fallback")

    assert [part["text"] for part in reply.parts] == [
        "Encontré 32 movimientos en tu tarjeta terminada en 4141, del 1 al 30 de septiembre "
        "y 27 movimientos en tu tarjeta terminada en 5555, del 1 al 30 de septiembre.",
        "No pude revisar una parte de tu información ahora.",
    ]


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


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (f"La revisión toma hasta {{p1.figures.claims.review_time}} [p:{CHUNK}].", []),
        (f"Según {{p1.title}}, llama al {{p1.figures.channels.phone}} [p:{CHUNK}].", []),
        ("La revisión toma hasta {p1.figures.claims.review_time}.", ["uncited_policy_reference"]),
        (
            f"La revisión toma hasta {{p1.figures.claims.review_time}}. Así lo dice el banco [p:{CHUNK}].",
            ["uncited_policy_reference"],
        ),
        (f"La revisión toma hasta 10 días hábiles [p:{CHUNK}].", ["policy_figure_outside_reference"]),
        (f"Llama al +51 1 600 2000 [p:{CHUNK}].", ["policy_figure_outside_reference"]),
        (
            f"Entra a ayuda y aclaraciones > tus aclaraciones [p:{CHUNK}].",
            ["policy_figure_outside_reference"],
        ),
        (f"El cargo es de 3.5% [p:{CHUNK}].", ["policy_figure_outside_reference"]),
        (f"El texto completo: {{p1.text}} [p:{CHUNK}].", ["trace_only_reference"]),
    ],
)
def test_a_policy_sentence_cites_its_chunk_and_states_figures_only_by_reference(
    text: str, expected: list[str]
) -> None:
    assert codes(text, with_chunk(ledger())) == expected


def test_chunk_facts_number_apart_from_data_facts() -> None:
    book = with_chunk(spend_ledger())

    assert list(book.facts) == ["f1", "f2", "p1"]
    assert book.add("cards", {"count": Count(0, "card")}).id == "f3"
    assert set(book.chunks()) == {CHUNK}


@pytest.mark.parametrize(
    ("value", "country", "locale", "expected"),
    [
        (Percent(Decimal("3.0")), "MX", "es", "3%"),
        (Percent(Decimal("3.5")), "AR", "es", "3,5%"),
        (Percent(Decimal("4.38")), "BR", "pt-BR", "4,38%"),
        (Percent(Decimal("30")), "US", "en", "30%"),
        (Count(1, "business_day"), "PE", "es", "1 día hábil"),
        (Count(10, "business_day"), "BR", "pt-BR", "10 dias úteis"),
        (Count(15, "minute"), "US", "en", "15 minutes"),
        (Channel("app_path", "Help and claims > Your claims"), "US", "en", "Help and claims > Your claims"),
        (Url("https://latambank.example/us/help"), "US", "en", "https://latambank.example/us/help"),
        (Labels("never_asked", ("pin", "cvv")), "MX", "es", "el PIN y el código de seguridad"),
    ],
)
def test_policy_figures_render_in_the_customers_country(
    value: Value, country: str, locale: str, expected: str
) -> None:
    assert render_value(value, Ledger(country, NOW), locale) == expected


def test_a_noun_doubled_after_a_count_and_dashes_are_tidied_and_counted_before_the_check() -> None:
    book = spend_ledger()

    assert tidy("Gastaste {f1.total} \u2014 con {f1.count} \u2013 en total.", book, "es") == (
        "Gastaste {f1.total}, con {f1.count}, en total.",
        {"dash": 2},
    )
    assert tidy("Hiciste {f1.count} en {f1.period}.", book, "es") == (
        "Hiciste {f1.count} {f1.period}.",
        {"period_preposition": 1},
    )
    fixed, edits = tidy(
        "Hiciste {f1.count} compras en {f1.merchant} y {f1.count}, compras pequeñas.", book, "es"
    )

    assert fixed == "Hiciste {f1.count} en {f1.merchant} y {f1.count}, compras pequeñas."
    assert edits == {"doubled_noun": 1}
    assert check([Say(fixed)], book, "es") == []


@pytest.mark.parametrize(
    ("locale", "text", "kept"),
    [
        ("es", "Tienes {f1.credit} de crédito activas.", "Tienes {f1.credit} activas."),
        ("es", "Tienes {f1.credit} tarjetas de crédito.", "Tienes {f1.credit}."),
        ("pt-BR", "Você tem {f1.credit} de crédito ativos.", "Você tem {f1.credit} ativos."),
        ("pt-BR", "Você tem {f1.credit} cartões de crédito.", "Você tem {f1.credit}."),
    ],
)
def test_a_multi_word_noun_doubled_after_a_count_is_caught_and_tidied(
    locale: str, text: str, kept: str
) -> None:
    book = ledger()
    book.add("cards", {"credit": Count(2, "credit_card")})

    assert [error.code for error in check([Say(text)], book, locale)] == ["noun_after_count"]
    assert tidy(text, book, locale) == (kept, {"doubled_noun": 1})


def test_a_repair_error_carries_the_words_around_it() -> None:
    text = "Tienes ambas tarjetas activas y quieres saber, ¿cuál de las dos quieres ver ahora mismo, Ana?"

    [error] = check([Say(text)], ledger(), "es")

    start = text.index(" dos ") + 1
    assert error.to_repair() == {
        "code": "number_word_outside_reference",
        "text": "dos",
        "instruction": error.instruction,
        "in": text[start - 30 : start + 33],
    }


def test_a_date_after_a_preposition_renders_without_its_article() -> None:
    book = ledger()
    book.add("day", {"date": Day(date(2026, 9, 18)), "today": Day(date(2026, 10, 1))})

    assert render_text("Pendente desde {f1.date}, a última foi {f1.date}.", book, "pt-BR") == (
        "Pendente desde 18 de setembro, a última foi em 18 de setembro."
    )
    assert render_text("Desde {f1.date}, fue el {f1.date}; desde {f1.today}.", book, "es") == (
        "Desde el 18 de septiembre, fue el 18 de septiembre; desde hoy."
    )


def test_a_claim_about_all_rows_fails_only_when_the_search_matched_more_than_were_shown() -> None:
    many, few = ledger(), ledger()
    many.add("movements", {"count": Count(13, "movement")})
    few.add("movements", {"count": Count(3, "movement")})
    text = "Encontrei {f1.count}, todas feitas na loja."

    assert [error.code for error in check([Say(text)], many, "pt-BR")] == ["unseen_rows_claim"]
    assert check([Say(text)], few, "pt-BR") == []
    assert check([Say("Tienes {f1.count} en todas tus tarjetas.")], many, "es") == []


def test_a_number_word_naming_a_counted_noun_becomes_its_reference() -> None:
    book = ledger()
    book.add("cards", {"count": Count(3, "card"), "credit": Count(2, "credit_card")})

    assert tidy("Tienes dos tarjetas de crédito Visa; ¿cuál de las dos?", book, "es") == (
        "Tienes {f1.credit} Visa; ¿cuál de las dos?",
        {"number_word": 1},
    )
    assert (
        tidy("Você tem três cartões e dois meses.", book, "pt-BR")[0] == "Você tem {f1.count} e dois meses."
    )
    assert tidy("Tienes cuatro tarjetas.", book, "es") == ("Tienes cuatro tarjetas.", {})


def test_a_citation_written_after_the_period_moves_into_its_sentence() -> None:
    book = with_chunk(ledger())
    text = "La revisión toma {p1.figures.claims.review_time}. [p:pe-dispute-lifecycle-v1-f1-s3-c2] Listo."

    fixed, edits = tidy(text, book, "es")

    assert (
        fixed
        == "La revisión toma {p1.figures.claims.review_time} [p:pe-dispute-lifecycle-v1-f1-s3-c2]. Listo."
    )
    assert edits == {"citation_placement": 1}
    assert check([Say(fixed)], book, "es") == []
    assert [error.code for error in check([Say(text)], book, "es")] == ["uncited_policy_reference"]


def test_a_portuguese_question_about_one_of_several_gets_its_preposition() -> None:
    book = ledger()

    assert tidy("Qual delas você quer saber mais?", book, "pt-BR") == (
        "Sobre qual delas você quer saber mais?",
        {"grammar": 1},
    )
    assert tidy("Sobre qual delas você quer saber mais?", book, "pt-BR") == (
        "Sobre qual delas você quer saber mais?",
        {},
    )
    assert tidy("Qual delas você quer entender melhor?", book, "pt-BR")[1] == {}


def test_a_number_word_stays_for_the_check_when_several_counts_share_its_noun() -> None:
    book = ledger()
    book.add("movements", {"count": Count(2, "movement")})
    book.add("movements", {"count": Count(5, "movement")})

    text = "Encontré dos movimientos."
    assert tidy(text, book, "es") == (text, {})
    assert [error.code for error in check([Say(text)], book, "es")] == ["number_word_outside_reference"]


def test_a_preposition_before_a_date_reference_is_dropped_in_spanish_and_portuguese() -> None:
    book = ledger()
    book.add("day", {"date": Day(date(2026, 9, 18))})

    assert tidy("La compra fue en {f1.date}.", book, "es") == (
        "La compra fue {f1.date}.",
        {"date_preposition": 1},
    )
    assert tidy("A compra foi em {f1.date}.", book, "pt-BR")[0] == "A compra foi {f1.date}."


def test_a_rendered_sentence_starts_with_a_capital() -> None:
    book = ledger()
    book.add("period", {"period": Period(date(2026, 9, 1), date(2026, 9, 30))})

    [said] = render([Say("{f1.period} gastaste poco. ¿todo bien? sí.")], book, "es")

    assert said["text"] == "Del 1 al 30 de septiembre gastaste poco. ¿todo bien? Sí."


def test_a_comparison_direction_reads_with_its_preposition_in_portuguese() -> None:
    book = ledger()
    book.add("spend", {"delta": Money(Decimal("145.31"), "BRL"), "direction": Label("direction", "less")})

    assert render_text("Você gastou {f1.delta} {f1.direction} do que no mês passado.", book, "pt-BR") == (
        f"Você gastou R${NB}145,31 a menos do que no mês passado."
    )
    assert render_text("Gastaste {f1.delta} {f1.direction} que el mes pasado.", book, "es") == (
        f"Gastaste {format_money(Decimal('145.31'), 'BRL', 'es')} menos que el mes pasado."
    )


DAY = date(2026, 9, 14)
TEMPLATE_VALUES: dict[str, Value] = {
    "count": Count(1, "movement"),
    "last4": Last4("4141"),
    "merchant": Merchant("Primax"),
    "total": Money(Decimal(240), "PEN"),
    "compare_total": Money(Decimal(180), "PEN"),
    "period": Period(DAY, DAY),
    "compare_period": Period(DAY, DAY),
    "last_date": Day(DAY),
}
DATED = [
    (key, locale, text)
    for key, texts in TEMPLATES.items()
    for locale, text in texts.items()
    if locale != "en" and {"period", "compare_period", "last_date"} & set(FIELD.findall(text))
]


@pytest.mark.parametrize(("key", "locale", "template"), DATED, ids=[f"{k}-{loc}" for k, loc, _ in DATED])
def test_every_template_renders_its_dates_with_the_article(key: str, locale: str, template: str) -> None:
    book = ledger()
    book.add(key, {name: TEMPLATE_VALUES[name] for name in FIELD.findall(template)})

    rendered = render_text(FIELD.sub(lambda match: f"{{f1.{match.group(1)}}}", template), book, locale)

    day = {"es": "14 de septiembre", "pt-BR": "14 de setembro"}[locale]
    article = {"es": "el ", "pt-BR": "em "}[locale]
    assert day in rendered
    assert rendered.count(day) == rendered.count(article + day)


def recent_ledger(matched: int = 12) -> Ledger:
    book = ledger()
    rows = [
        book.add(
            "movement",
            {
                "transaction_ref": Ref("transaction", f"tx-{index}"),
                "card_ref": Ref("card", "card-1" if index % 2 else "card-2"),
                "merchant": Merchant(f"Shop {index}"),
            },
        )
        for index in range(1, 11)
    ]
    book.add(
        "movements",
        {
            "count": Count(matched, "movement"),
            "ids": FactIds(tuple(row.id for row in rows)),
            "recent": Flag(True),
        },
    )
    return book


def test_which_one_over_the_newest_rows_of_a_recent_search_passes_though_more_matched() -> None:
    allowed = frozenset({"which_one"})

    assert check_codes([Ask("which_one", ("f1", "f2", "f3", "f4", "f5"))], recent_ledger(), allowed) == []
    assert check_codes([Ask("which_one", ("f2", "f3", "f4", "f5", "f6"))], recent_ledger(), allowed) == [
        ("ask_options_partial", "f2")
    ]
    assert check_codes([Ask("which_one", ("f1", "f2"))], recent_ledger(), allowed) == [
        ("ask_options_partial", "f1")
    ]
    filtered = recent_ledger()
    filtered.facts["f11"] = Fact("f11", "movements", {**filtered.facts["f11"].fields, "recent": Flag(False)})
    assert check_codes([Ask("which_one", ("f1", "f2", "f3", "f4", "f5"))], filtered, allowed) == [
        ("ask_options_partial", "f1")
    ]


@pytest.mark.parametrize(
    ("locale", "noun", "value", "text", "expected"),
    [
        ("es", "subscription", 2, "Veo {f1.count} detectadas.", "Veo 2 cargos recurrentes detectados."),
        ("es", "purchase", 1, "Hay {f1.count} registrado.", "Hay 1 compra registrada."),
        ("es", "movement", 3, "Hay {f1.count} aprobadas.", "Hay 3 movimientos aprobados."),
        ("es", "subscription", 2, "Tienes {f1.count} activas.", "Tienes 2 cargos recurrentes activos."),
        (
            "pt-BR",
            "subscription",
            2,
            "Vejo {f1.count} detectados.",
            "Vejo 2 cobranças recorrentes detectadas.",
        ),
        ("pt-BR", "card", 2, "Você tem {f1.count} bloqueadas.", "Você tem 2 cartões bloqueados."),
    ],
)
def test_a_participle_after_a_count_agrees_with_the_counted_noun(
    locale: str, noun: str, value: int, text: str, expected: str
) -> None:
    book = ledger()
    book.add("recurring_list", {"count": Count(value, noun)})

    tidied, edits = tidy(text, book, locale)

    assert render_text(tidied, book, locale) == expected
    assert edits == {"agreement": 1}
    assert tidy("Hay {f1.count} cada mes.", book, locale)[1] == {}


@pytest.mark.parametrize(
    ("locale", "text", "expected"),
    [
        ("pt-BR", "Seus {f1.count} estão atualmente {f2.status}.", "Seus 3 cartões estão atualmente ativos."),
        (
            "pt-BR",
            "Ambos {f2.status}, o cartão {f2.last4} também.",
            "Ambos ativos, o cartão final 4141 também.",
        ),
        ("es", "Tus {f1.count} están {f2.status}.", "Tus 3 tarjetas están activas."),
    ],
)
def test_a_card_status_after_a_plural_in_its_clause_is_written_in_the_plural(
    locale: str, text: str, expected: str
) -> None:
    book = ledger()
    book.add("cards", {"count": Count(3, "card")})
    book.add("card", {"status": Status("card", "Active"), "last4": Last4("4141")})

    tidied, edits = tidy(text, book, locale)

    assert render_text(tidied, book, locale) == expected
    assert edits == {"agreement": 1}
    assert tidy("Tu tarjeta {f2.last4} está {f2.status}. Son tuyas.", book, "es")[1] == {}


def test_a_relative_day_never_follows_a_contracted_article() -> None:
    book = ledger()
    book.add("movement", {"date": Instant(NOW - timedelta(hours=1)), "day": Day(date(2026, 9, 14))})

    tidied, edits = tidy("Es el cargo correspondiente al {f1.date}.", book, "es")

    assert render_text(tidied, book, "es") == "Es el cargo correspondiente hoy a las 09:00."
    assert edits == {"relative_day": 1}
    assert tidy("Desde el 1 hasta el día al {f1.day}.", book, "es")[1] == {}


def test_a_repair_names_every_kind_of_error_and_the_part_each_part_error_is_in() -> None:
    book = view_ledger()
    parts: list[Part] = [
        Say("Fue ayer."),
        View("movements", ("f5",)),
        Ask("show", ("f8",)),
    ]

    errors = check(parts, book, "es", frozenset({"show", "which_one"}))

    assert [error.code for error in errors] == ["date_outside_reference", "show_with_view"]
    assert errors[1].to_repair()["in"] == "ask show with facts f8"
    assert "date_outside_reference, show_with_view" in repair_instruction(errors)


def spend_and_search() -> Ledger:
    book = spend_ledger()
    book.add(
        "movements",
        {"count": Count(14, "movement"), "ids": FactIds(("f2",)), "period": Period(date(2026, 8, 1), DAY)},
    )
    return book


def test_an_answer_about_a_spend_never_adds_the_count_of_the_movements_search() -> None:
    book = spend_and_search()

    assert check_codes([Say("Gastaste {f1.total}."), Say("En total hay {f3.count} {f3.period}.")], book) == [
        ("movements_beside_spend", "{f3.count}"),
        ("movements_beside_spend", "{f3.period}"),
    ]
    assert check_codes([Say("Encontré {f3.count} {f3.period}.")], book) == []
    assert tidy_reply(
        ["Gastaste {f1.total}. En total hay {f3.count}.", "Hay {f3.count} {f3.period}."], book
    ) == (
        ["Gastaste {f1.total}."],
        {"movements_beside_spend": 2},
    )
    assert tidy_reply(["Encontré {f3.count}."], book) == (["Encontré {f3.count}."], {})
    assert tidy_reply(
        ["Gastaste {f1.total}.", "Hay {f3.count} en {f1.merchant} en esos dos meses."], book
    ) == (
        ["Gastaste {f1.total}."],
        {"movements_beside_spend": 1},
    )

    reply = compose(fallback("answer", book, "es"), book, "es", "fallback")
    assert [part["text"][:9] for part in reply.parts if part["type"] == "say"] == ["Gastaste "]


def test_a_process_sentence_passes_with_its_citation_and_a_card_beside_the_series_needs_a_series() -> None:
    book = with_chunk(ledger())
    cited = f"Puedes abrir una aclaración llamando al banco [p:{CHUNK}]."
    assert codes(cited, book) == []

    for index, digits in ((1, "5529"), (2, "0355")):
        book.add(
            "card",
            {
                "card_ref": Ref("card", f"card-{index}"),
                "last4": Last4(digits),
                "status": Status("card", "Active"),
            },
        )
    book.add(
        "recurring",
        {"merchant": Merchant("Movistar"), "card_ref": Ref("card", "card-1"), "last4": Last4("5529")},
    )

    assert check_codes(
        [
            Say("Si bloqueas tu tarjeta {f2.last4}, se rechaza."),
            Say("Tienes {f3.merchant} en tu tarjeta {f3.last4}."),
        ],
        book,
    ) == [("card_without_series", "{f2.last4}")]
    assert check_codes(
        [Say("Tu tarjeta {f1.last4} y tu tarjeta {f2.last4}."), Say("Tienes {f3.merchant}.")], book
    ) == [("card_without_series", "{f2.last4}")]
    assert (
        check_codes([Say("Tu tarjeta {f2.last4} está {f2.status}."), Say("Tienes {f3.merchant}.")], book)
        == []
    )


@pytest.mark.parametrize(
    ("locale", "text", "expected"),
    [
        ("es", "Tu cargo en {f1.merchant} está {f1.status}.", "Tu cargo en Primax está aprobado."),
        ("es", "Tu compra está {f1.status}.", "Tu compra está aprobada."),
        ("es", "Es un cargo. La compra está {f1.status}.", "Es un cargo. La compra está aprobada."),
        ("pt-BR", "O pagamento está {f1.status}.", "O pagamento está aprovado."),
        ("pt-BR", "A cobrança está {f1.status}.", "A cobrança está aprovada."),
    ],
)
def test_a_charge_status_agrees_with_the_noun_that_names_the_charge(
    locale: str, text: str, expected: str
) -> None:
    book = ledger()
    book.add("movement", {"merchant": Merchant("Primax"), "status": Status("transaction", "Approved")})

    assert render_text(text, book, locale) == expected


def test_a_bare_pointer_or_uncited_advice_is_dropped_before_the_check_and_counted() -> None:
    book = with_chunk(spend_ledger())

    texts, edits = tidy_reply(
        [
            "Gastaste {f1.total}. Aquí puedes ver los más recientes.",
            "Si no lo reconoces, puedes llamar al banco para abrir una aclaración.",
            f"Puedes abrir una aclaración llamando al banco [p:{CHUNK}].",
        ],
        book,
    )

    assert texts == ["Gastaste {f1.total}.", f"Puedes abrir una aclaración llamando al banco [p:{CHUNK}]."]
    assert edits == {"location_talk": 1, "uncited_process": 1}
    ordinary = ["Gastaste {f1.total}.", "Es un monto por debajo de lo habitual."]
    assert tidy_reply(ordinary, book) == (ordinary, {})
    assert tidy_reply(["Puedes cancelar {f1.merchant} con el comercio."], book) == (
        ["Puedes cancelar {f1.merchant} con el comercio."],
        {},
    )


def test_a_voseo_form_becomes_its_tu_form_in_spanish_only() -> None:
    assert tidy("Este mes llevás {f1.total}. ¿Querés verlos?", spend_ledger(), "es") == (
        "Este mes llevas {f1.total}. ¿Quieres verlos?",
        {"voseo": 2},
    )
    assert tidy("Você tem {f1.total}.", spend_ledger(), "pt-BR")[1] == {}


def test_a_say_with_no_word_but_a_citation_fails_and_a_cited_sentence_after_its_period_is_kept() -> None:
    book = with_chunk(ledger())

    assert check_codes([Say(f"[p:{CHUNK}]")], book) == [("empty_say", f"[p:{CHUNK}]")]
    assert check_codes([Say(" . ")], book) == [("empty_say", " . ")]
    assert check_codes([Say("Gastaste {f1.total}.")], spend_ledger()) == []
    assert tidy_reply([f"Puedes llamar al banco para abrir una aclaración. [p:{CHUNK}]"], book) == (
        [f"Puedes llamar al banco para abrir una aclaración [p:{CHUNK}]."],
        {"citation_placement": 1},
    )


def test_the_policy_fallback_quotes_the_cited_section_as_plain_text_with_its_title() -> None:
    book = ledger()
    for index, title in ((1, "Plazos"), (2, "Escalamiento")):
        book.add(
            "policy_chunk",
            {
                "chunk_id": Trace(f"pe-doc-s{index}-c1"),
                "title": Text(title),
                "text": Passage(f"## {title}\n\n- **Paso:** escribe a la defensoría.\n- Llama al banco."),
            },
            prefix="p",
        )

    cited = compose(fallback("answer", book, "es", ["pe-doc-s2-c1"]), book, "es", "fallback")
    top = compose(fallback("answer", book, "es"), book, "es", "fallback")

    assert cited.text == (
        "Esto dice el banco en «Escalamiento»: Escalamiento Paso: escribe a la defensoría. Llama al banco."
    )
    assert [entry["chunk_id"] for entry in cited.parts[0]["citations"]] == ["pe-doc-s2-c1"]
    assert top.text.startswith("Esto dice el banco en «Plazos»")


@pytest.mark.parametrize(
    ("locale", "text", "failed"),
    [
        ("pt-BR", "Tu tarjeta {f1.last4} está {f1.status} y no tiene cargos pendientes.", True),
        ("pt-BR", "Seu cartão {f1.last4} está {f1.status} e não tem cobranças pendentes.", False),
        ("pt-BR", "Your card {f1.last4} is {f1.status} and has no pending charges.", True),
        ("es", "Seu cartão {f1.last4} está {f1.status} e não tem cobranças pendentes.", True),
        ("es", "Tu tarjeta {f1.last4} está {f1.status}.", False),
        ("pt-BR", "A compra em Tienda de la Esquina y los Amigos foi no seu cartão {f1.last4}.", False),
        ("pt-BR", "Segundo «Ciclo de una aclaración y los pasos del banco», é isso [p:pe-doc-s1-c1].", False),
        ("pt-BR", "Beleza!", False),
        (
            "es",
            "Este mes gastaste {f1.last4} en {f2.merchant}, comparado con el mes pasado. "
            "Eso es que el mes pasado.",
            False,
        ),
    ],
)
def test_a_say_in_another_language_than_the_account_s_fails_but_names_and_titles_do_not_count(
    locale: str, text: str, failed: bool
) -> None:
    book = Ledger("BR", NOW)
    book.add(
        "card", {"card_ref": Ref("card", "c1"), "last4": Last4("1234"), "status": Status("card", "Active")}
    )
    book.add("movement", {"merchant": Merchant("Tienda de la Esquina y los Amigos")})
    book.add("policy_chunk", {"chunk_id": Trace("pe-doc-s1-c1"), "title": Text("Ciclo")}, prefix="p")

    assert ("wrong_language" in [error.code for error in check([Say(text)], book, locale)]) is failed


def test_a_charge_ask_without_its_charge_view_is_sent_back_but_code_views_need_none() -> None:
    book = ledger()
    charge = book.add(
        "charge",
        {"charge.transaction_ref": Ref("transaction", "tx-1"), "charge.card_ref": Ref("card", "card-1")},
    )
    asked = Ask("recognize_charge", (charge.id,))
    allowed = frozenset({"recognize_charge", "talk_to_person"})

    assert check_codes([asked], book, allowed) == [("ask_without_view", "recognize_charge")]
    assert check_codes([View("charge", (charge.id,)), asked], book, allowed) == []
    assert check_codes([Ask("talk_to_person", (charge.id,))], book, allowed) == []


@pytest.mark.parametrize(
    ("locale", "text", "expected"),
    [
        ("pt-BR", "Você tem {f1.credit} e ambas estão ativas.", "Você tem {f1.credit} e ambos estão ativos."),
        ("es", "Tienes {f1.credit} y ambos están activos.", "Tienes {f1.credit} y ambas están activas."),
        ("es", "Tienes {f1.credit} y ambas están activas.", "Tienes {f1.credit} y ambas están activas."),
    ],
)
def test_both_agrees_with_the_counted_noun_of_its_clause(locale: str, text: str, expected: str) -> None:
    book = Ledger("BR", NOW)
    book.add("cards", {"credit": Count(2, "credit_card")})

    tidied, edits = tidy(text, book, locale)

    assert tidied == expected
    assert edits.get("agreement", 0) == (0 if text == expected else 2)


def test_the_first_purchase_said_again_beside_the_bank_s_reasons_is_sent_back() -> None:
    book = Ledger("BR", NOW)
    book.add("charge", {"verdict.reasons": Labels("reason", ("score_high", "new_merchant"))})
    quiet = Ledger("BR", NOW)
    quiet.add("charge", {"verdict.reasons": Labels("reason", ("score_high",))})
    repeated = "É a sua primeira compra nesse estabelecimento e o que o banco notou: {f1.verdict.reasons}."

    assert codes(repeated, book, "pt-BR") == ["repeated_reason"]
    assert codes("O que o banco notou: {f1.verdict.reasons}.", book, "pt-BR") == []
    assert codes("Es tu primera compra ahí. Lo que notó el banco: {f1.verdict.reasons}.", book) == [
        "repeated_reason"
    ]
    assert codes(repeated, quiet, "pt-BR") == []


@pytest.mark.parametrize(
    ("locale", "text"),
    [
        ("es", "Para gestionar un desbloqueo necesitarás hablar con el equipo de atención."),
        ("es", "Tendrás que llamar al banco para eso."),
        ("es", "Para cualquier gestión de desbloqueo necesitas hablar con alguien del equipo."),
        ("pt-BR", "Para isso você vai precisar falar com o banco."),
        ("en", "You will need to talk to the bank about that."),
    ],
)
def test_future_and_obligation_advice_is_uncited_process(locale: str, text: str) -> None:
    assert "uncited_process" in codes(text, ledger(), locale)


def test_an_adjective_that_guesses_the_customer_s_gender_is_sent_back() -> None:
    assert codes("Se ainda assim não ficar satisfeita, o passo seguinte é o Procon.", ledger(), "pt-BR") == [
        "gendered_customer"
    ]
    assert (
        codes("Si no quedas satisfecho con la respuesta, puedes reclamar.", ledger())[0]
        == "gendered_customer"
    )
    assert codes("Se a resposta não resolver, o passo seguinte é o Procon.", ledger(), "pt-BR") == []


@pytest.mark.parametrize(
    ("locale", "text", "offered"),
    [
        ("es", "Te puedo conectar con alguien que lo gestione.", True),
        ("es", "Puedo pasarte con una persona del banco.", True),
        ("es", "Puedo revisar el estado de tus tarjetas si quieres.", True),
        ("pt-BR", "Posso verificar o status dos seus cartões se quiser.", True),
        ("pt-BR", "Posso te passar para um atendente.", True),
        ("en", "I can connect you with someone at the bank.", True),
        ("pt-BR", "Posso verificar o status dos seus cartões enquanto isso.", True),
        ("es", "Puedo ayudarte a conectarte con ellos.", True),
        ("es", "Si necesitas gestionar el desbloqueo, un representante puede ayudarte.", True),
        ("es", "Para desbloquear tu tarjeta, una persona en el banco puede ayudarte con eso.", True),
        ("pt-BR", "Posso colocar você em contato com alguém que possa desbloqueá-lo.", True),
        ("pt-BR", "Se você precisa desbloqueá-lo, uma pessoa do banco pode ajudar com isso.", True),
        ("es", "Desbloquear una tarjeta lo hace una persona del banco.", False),
        ("pt-BR", "Seus cartões estão ativos.", False),
    ],
)
def test_an_offer_in_prose_is_sent_back(locale: str, text: str, offered: bool) -> None:
    assert ("offer_talk" in codes(text, ledger(), locale)) is offered


@pytest.mark.parametrize(
    ("locale", "text", "expected"),
    [
        (
            "es",
            "Tus tarjetas {f1.last4}, {f2.last4} y {f3.last4} están activas.",
            "Tu tarjeta {f1.last4}, tu tarjeta {f2.last4} y tu tarjeta {f3.last4} están activas.",
        ),
        (
            "pt-BR",
            "Seus cartões {f1.last4} e {f2.last4} estão ativos.",
            "Seu cartão {f1.last4} e seu cartão {f2.last4} estão ativos.",
        ),
        (
            "en",
            "Your cards {f1.last4} and {f2.last4} are active.",
            "Your card {f1.last4} and your card {f2.last4} are active.",
        ),
    ],
)
def test_a_plural_card_noun_before_a_list_of_last_digits_becomes_one_noun_per_card(
    locale: str, text: str, expected: str
) -> None:
    book = ledger()
    for digits in ("8101", "2322", "5943"):
        book.add("card", {"last4": Last4(digits)})

    assert tidy(text, book, locale) == (expected, {"agreement": 1})
    assert tidy("Tus tarjetas {f1.last4} están activas.", book, "es")[1] == {}
