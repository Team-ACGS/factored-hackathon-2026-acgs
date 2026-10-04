import re
import unicodedata
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from core.countries import zone
from core.facts.catalog import (
    ARTICLE_DROPPED_AFTER,
    CLOCK_AT,
    COUNTRY_NAMES,
    DATE_ARTICLE,
    DECIMAL_COMMA_COUNTRIES,
    FEMININE_CHARGE_NOUNS,
    LABELS,
    LAST4,
    LIST_JOIN,
    MASCULINE_CHARGE_NOUNS,
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
    Channel,
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
    Percent,
    Period,
    Ratio,
    Status,
    Text,
    Url,
    Value,
)

REFERENCE = re.compile(r"\{([fp]\d+)\.([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)*)\}")
CITATION = re.compile(r"\[p:([^\[\]\s]+)\]")
PREVIOUS_WORD = re.compile(r"(\w+)\s+$")
SENTENCE_END = re.compile(r"[.!?]+\s")
WORD = re.compile(r"\w+")
SENTENCE_START = re.compile(r"(^|[.!?]\s+)([a-záéíóúñãõâêôç])")


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


def format_date(day: date, ledger: Ledger, locale: str, standalone: bool = True, article: bool = True) -> str:
    today = ledger.today
    if standalone and day == today:
        return RELATIVE_DAYS[locale][0]
    if standalone and day == today - timedelta(days=1):
        return RELATIVE_DAYS[locale][1]
    month = MONTHS[locale][day.month - 1]
    if locale == "en":
        text = f"{month} {day.day}"
        return text if day.year == today.year else f"{text}, {day.year}"
    text = f"{day.day} de {month}"
    text = text if day.year == today.year else f"{text} de {day.year}"
    return DATE_ARTICLE[locale] + text if standalone and article else text


def format_datetime(instant: datetime, ledger: Ledger, locale: str, article: bool = True) -> str:
    local = instant.astimezone(zone(ledger.country))
    if locale == "en":
        clock = f"{(local.hour - 1) % 12 + 1}:{local.minute:02d} {'AM' if local.hour < 12 else 'PM'}"
    else:
        clock = f"{local.hour:02d}:{local.minute:02d}"
    at = CLOCK_AT[locale][0 if local.hour == 1 else 1]
    return f"{format_date(local.date(), ledger, locale, article=article)} {at} {clock}"


def format_period(start: date, end: date, ledger: Ledger, locale: str, article: bool = True) -> str:
    if start == end:
        return format_date(start, ledger, locale, article=article)
    same_month = (start.year, start.month) == (end.year, end.month)
    last = format_date(end, ledger, locale, standalone=False)
    if locale == "en":
        if same_month:
            month, _, rest = last.partition(" ")
            return f"{month} {start.day} to {rest}"
        return f"{format_date(start, ledger, locale, standalone=False)} to {last}"
    first = str(start.day) if same_month else format_date(start, ledger, locale, standalone=False)
    if locale == "es":
        return f"del {first} al {last}"
    return f"de {first} a {last}"


def format_count(count: int, noun: str, locale: str) -> str:
    singular, plural = NOUNS[noun][locale]
    return f"{count} {singular if is_singular(count, locale) else plural}"


def is_singular(count: int, locale: str) -> bool:
    return count in (0, 1) if locale == "pt-BR" else count == 1


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


def format_percent(percent: Decimal, country: str) -> str:
    number = format(percent.normalize(), "f")
    if "." in number:
        number = number.rstrip("0").rstrip(".")
    if country in DECIMAL_COMMA_COUNTRIES:
        number = number.replace(".", ",")
    return f"{number}%"


def label(domain: str, value: str, locale: str) -> str:
    return LABELS.get(domain, {}).get(value, {}).get(locale, value)


def render_value(value: Value, ledger: Ledger, locale: str, article: bool = True) -> str:
    match value:
        case Money(amount, currency):
            return format_money(amount, currency, locale)
        case Day(day):
            return format_date(day, ledger, locale, article=article)
        case Instant(instant):
            return format_datetime(instant, ledger, locale, article=article)
        case Period(start, end):
            return format_period(start, end, ledger, locale, article)
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
        case Merchant(text) | City(text) | CaseCode(text) | Channel(_, text) | Url(text) | Text(text):
            return text
        case Percent(percent):
            return format_percent(percent, ledger.country)
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
        before = PREVIOUS_WORD.search(match.string, 0, match.start())
        article = before is None or before.group(1).lower() not in ARTICLE_DROPPED_AFTER[locale]
        rendered = render_value(value, ledger, locale, article)
        if isinstance(value, Status) and value.domain == "transaction":
            return _agreeing(rendered, match.string[: match.start()], locale)
        return rendered

    without_citations = re.sub(r"\s*" + CITATION.pattern, "", text)
    return REFERENCE.sub(replace, without_citations)


def _agreeing(status: str, before: str, locale: str) -> str:
    masculine, feminine = MASCULINE_CHARGE_NOUNS.get(locale), FEMININE_CHARGE_NOUNS.get(locale)
    if masculine is None or feminine is None or not status.endswith("a"):
        return status
    sentence = SENTENCE_END.split(before)[-1]
    for word in reversed(WORD.findall(_folded(sentence))):
        if word in masculine:
            return status[:-1] + "o"
        if word in feminine:
            return status
    return status


def _folded(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if not unicodedata.combining(c))


def sentence_case(text: str) -> str:
    return SENTENCE_START.sub(lambda match: match.group(1) + match.group(2).upper(), text)


def render(parts: Sequence[Part], ledger: Ledger, locale: str) -> list[Json]:
    rendered: list[Json] = []
    for part in parts:
        match part:
            case Say(text):
                rendered.append(
                    {
                        "type": "say",
                        "text": sentence_case(render_text(text, ledger, locale)),
                        "facts": list(dict.fromkeys(match.group(1) for match in REFERENCE.finditer(text))),
                        "citations": [match.group(1) for match in CITATION.finditer(text)],
                    }
                )
            case View() | Ask():
                rendered.append(part.to_wire())
    return rendered
