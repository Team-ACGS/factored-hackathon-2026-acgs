import re
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from core.countries import zone
from core.facts.catalog import (
    COUNTRY_NAMES,
    LABELS,
    LAST4,
    LIST_JOIN,
    MONEY_STYLES,
    MONTHS,
    NBSP,
    NOUNS,
    QUOTES,
    RATIO,
    RELATIVE_DAYS,
    STATUS_LABELS,
    WHOLE_CURRENCIES,
)
from core.facts.parts import Ask, Part, Say, View
from core.facts.values import (
    TRACE_ONLY,
    CaseCode,
    City,
    Count,
    Country,
    Day,
    Instant,
    Json,
    Label,
    Labels,
    Last4,
    Ledger,
    Merchant,
    Money,
    Note,
    Period,
    Ratio,
    Status,
    Value,
)

REFERENCE = re.compile(r"\{(f\d+)\.([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)*)\}")
CITATION = re.compile(r"\[p:([^\[\]\s]+)\]")


class TraceOnly(ValueError):
    pass


def resolve(ledger: Ledger, fact_id: str, field: str) -> Value | None:
    fact = ledger.get(fact_id)
    return None if fact is None else fact.fields.get(field)


def format_money(amount: Decimal, currency: str, locale: str) -> str:
    symbol, gap, group, decimal = MONEY_STYLES[locale].get(currency, (currency, NBSP, ",", "."))
    step = Decimal(1) if currency in WHOLE_CURRENCIES else Decimal("0.01")
    rounded = abs(amount).quantize(step, ROUND_HALF_UP)
    integer, _, fraction = format(rounded, "f").partition(".")
    groups: list[str] = []
    while len(integer) > 3:
        groups.insert(0, integer[-3:])
        integer = integer[:-3]
    number = group.join([integer, *groups]) + (decimal + fraction if fraction else "")
    sign = "-" if amount < 0 and rounded else ""
    return f"{sign}{symbol}{gap}{number}"


def format_date(day: date, ledger: Ledger, locale: str, relative: bool = True) -> str:
    today = ledger.today
    if relative and day == today:
        return RELATIVE_DAYS[locale][0]
    if relative and day == today - timedelta(days=1):
        return RELATIVE_DAYS[locale][1]
    month = MONTHS[locale][day.month - 1]
    if locale == "en":
        text = f"{month} {day.day}"
        return text if day.year == today.year else f"{text}, {day.year}"
    text = f"{day.day} de {month}"
    return text if day.year == today.year else f"{text} de {day.year}"


def format_datetime(instant: datetime, ledger: Ledger, locale: str) -> str:
    local = instant.astimezone(zone(ledger.country))
    if locale == "en":
        clock = f"{(local.hour - 1) % 12 + 1}:{local.minute:02d} {'AM' if local.hour < 12 else 'PM'}"
    else:
        clock = f"{local.hour:02d}:{local.minute:02d}"
    return f"{format_date(local.date(), ledger, locale)}, {clock}"


def format_period(start: date, end: date, ledger: Ledger, locale: str) -> str:
    if start == end:
        return format_date(start, ledger, locale, relative=False)
    same_month = (start.year, start.month) == (end.year, end.month)
    last = format_date(end, ledger, locale, relative=False)
    if locale == "en":
        if same_month:
            month, _, rest = last.partition(" ")
            return f"{month} {start.day} to {rest}"
        return f"{format_date(start, ledger, locale, relative=False)} to {last}"
    first = str(start.day) if same_month else format_date(start, ledger, locale, relative=False)
    if locale == "es":
        return f"del {first} al {last}"
    return f"de {first} a {last}"


def format_count(count: int, noun: str, locale: str) -> str:
    singular, plural = NOUNS[noun][locale]
    one = count in (0, 1) if locale == "pt-BR" else count == 1
    return f"{count} {singular if one else plural}"


def format_ratio(ratio: Decimal, locale: str) -> str:
    texts = RATIO[locale]
    if ratio < Decimal("0.5"):
        return texts["far_below"]
    if ratio < Decimal("0.8"):
        return texts["below"]
    if ratio <= Decimal("1.25"):
        return texts["usual"]
    if ratio < Decimal("1.75"):
        return texts["above"]
    times = int(ratio.quantize(Decimal(1), ROUND_HALF_UP))
    return texts["times"].format(times) if times <= 5 else texts["far_above"].format(5)


def label(domain: str, value: str, locale: str) -> str:
    return LABELS.get(domain, {}).get(value, {}).get(locale, value)


def render_value(value: Value, ledger: Ledger, locale: str) -> str:
    match value:
        case Money(amount, currency):
            return format_money(amount, currency, locale)
        case Day(day):
            return format_date(day, ledger, locale)
        case Instant(instant):
            return format_datetime(instant, ledger, locale)
        case Period(start, end):
            return format_period(start, end, ledger, locale)
        case Count(count, noun):
            return format_count(count, noun, locale)
        case Last4(digits):
            return LAST4[locale].format(digits)
        case Status(domain, status):
            return STATUS_LABELS.get(domain, {}).get(status, {}).get(locale, status)
        case Label(domain, entry):
            return label(domain, entry, locale)
        case Labels(domain, entries):
            rendered = [label(domain, entry, locale) for entry in entries]
            if len(rendered) <= 1:
                return "".join(rendered)
            return ", ".join(rendered[:-1]) + LIST_JOIN[locale] + rendered[-1]
        case Merchant(text) | City(text) | CaseCode(text):
            return text
        case Country(code):
            return COUNTRY_NAMES.get(code, {}).get(locale, code)
        case Ratio(ratio):
            return format_ratio(ratio, locale)
        case Note(text):
            opening, closing = QUOTES[locale]
            return f"{opening}{text}{closing}"
    raise TraceOnly(type(value).__name__)


def is_renderable(value: Value) -> bool:
    return not isinstance(value, TRACE_ONLY)


def render_text(text: str, ledger: Ledger, locale: str) -> str:
    def replace(match: re.Match[str]) -> str:
        value = resolve(ledger, match.group(1), match.group(2))
        if value is None:
            raise KeyError(match.group(0))
        return render_value(value, ledger, locale)

    without_citations = re.sub(r"\s*" + CITATION.pattern, "", text)
    return REFERENCE.sub(replace, without_citations)


def render(parts: Sequence[Part], ledger: Ledger, locale: str) -> list[Json]:
    rendered: list[Json] = []
    for part in parts:
        match part:
            case Say(text):
                rendered.append(
                    {
                        "type": "say",
                        "text": render_text(text, ledger, locale),
                        "facts": list(dict.fromkeys(match.group(1) for match in REFERENCE.finditer(text))),
                        "citations": [match.group(1) for match in CITATION.finditer(text)],
                    }
                )
            case View() | Ask():
                rendered.append(part.to_wire())
    return rendered
