import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import cache

from core.facts.catalog import (
    CARDINALS,
    COUNT_NOUNS,
    DATE_HOMONYMS,
    DATE_WORDS,
    FORBIDDEN,
    INSTRUCTIONS,
    MONTHS,
    NUMBER_HOMONYMS,
    ORDINALS,
    PERIOD_PREPOSITIONS,
    WEEKDAYS,
)
from core.facts.lexicon import CATALOG_MERCHANTS, COMMON_WORD_MERCHANTS
from core.facts.parts import Ask, Part, Say, View
from core.facts.render import CITATION, REFERENCE, is_renderable, render_value, resolve
from core.facts.targets import Unfit, ask_options, view_items
from core.facts.values import Channel, Count, Json, Ledger, Money, Percent, Period, Url

POLICY_FIGURES = (Count, Money, Percent, Channel, Url)
SENTENCE_END = re.compile(r"[.!?]+(?=\s|$)")

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
URL = re.compile(
    r"(?i)(?:https?://|www\.)\S+"
    r"|(?<![\w.-])[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|net|org|io|app|pe|mx|co|ar|br|us)(?![a-z0-9])(?:/\S*)?"
)
PHONE = re.compile(r"\+?\d[\d\s().-]{6,}\d")
DIGITS = re.compile(r"\d+")
NEXT_WORD = re.compile(r"\s+(\w+)")
WORD_BEFORE = re.compile(r"(?<!\w)(\w+)\s+$")
CONTEXT_CHARS = 30
DASH = re.compile(r"\s*[\u2014\u2013]\s*")
CURRENCY = re.compile(r"US\$|R\$|S/|[$€£¥]|(?<![A-Za-z])(?:USD|PEN|MXN|COP|ARS|BRL|EUR)(?![A-Za-z])")


@dataclass(frozen=True)
class CheckError:
    code: str
    part: int
    span: tuple[int, int]
    text: str
    instruction: str
    context: str = ""

    def to_dict(self) -> Json:
        return {
            "code": self.code,
            "part": self.part,
            "span": list(self.span),
            "text": self.text,
            "instruction": self.instruction,
        }

    def to_repair(self) -> Json:
        repair = {"code": self.code, "text": self.text, "instruction": self.instruction}
        return {**repair, "in": self.context} if self.context else repair


def check(
    parts: Sequence[Part], ledger: Ledger, locale: str, allowed_asks: frozenset[str] = frozenset()
) -> list[CheckError]:
    errors: list[CheckError] = []
    for index, part in enumerate(parts):
        match part:
            case Say(text):
                errors.extend(_SayCheck(index, text, ledger, locale).run())
            case View():
                try:
                    view_items(part, ledger)
                except Unfit as unfit:
                    errors.append(_error(unfit.code, index, (0, 0), unfit.fact_id))
            case Ask(ask) if ask not in allowed_asks:
                errors.append(_error("ask_not_allowed", index, (0, 0), ask))
            case Ask("show") if any(isinstance(other, View) for other in parts):
                errors.append(_error("show_with_view", index, (0, 0), "show"))
            case Ask():
                try:
                    ask_options(part, ledger)
                except Unfit as unfit:
                    errors.append(_error(unfit.code, index, (0, 0), unfit.fact_id))
    return sorted(errors, key=lambda error: (error.part, error.span))


def tidy(text: str, ledger: Ledger, locale: str) -> str:
    return DASH.sub(
        ", ", _drop_period_prepositions(_drop_doubled_nouns(text, ledger, locale), ledger, locale)
    )


def _drop_period_prepositions(text: str, ledger: Ledger, locale: str) -> str:
    cuts = []
    for match in REFERENCE.finditer(text):
        before = WORD_BEFORE.search(text, 0, match.start())
        is_period = isinstance(resolve(ledger, match.group(1), match.group(2)), Period)
        if is_period and before and fold(before.group(1)) in PERIOD_PREPOSITIONS[locale]:
            cuts.append(before.span())
    for start, end in reversed(cuts):
        text = text[:start] + text[end:]
    return text


def _drop_doubled_nouns(text: str, ledger: Ledger, locale: str) -> str:
    cuts = []
    for match in REFERENCE.finditer(text):
        following = NEXT_WORD.match(text, match.end())
        counted = isinstance(resolve(ledger, match.group(1), match.group(2)), Count)
        if counted and following and fold(following.group(1)) in _count_nouns(locale):
            cuts.append(following.span())
    for start, end in reversed(cuts):
        text = text[:start] + text[end:]
    return text


def fold(text: str) -> str:
    return "".join(_fold_char(char) for char in text)


def _fold_char(char: str) -> str:
    if char in "\u2018\u2019":
        return "'"
    stripped = "".join(c for c in unicodedata.normalize("NFD", char) if not unicodedata.combining(c)).lower()
    if len(stripped) == 1:
        return stripped
    lowered = char.lower()
    return lowered if len(lowered) == 1 else char


def _error(code: str, part: int, span: tuple[int, int], text: str) -> CheckError:
    return CheckError(code, part, span, text, INSTRUCTIONS[code])


def bounded(alternatives: Iterable[str]) -> re.Pattern[str]:
    ordered = sorted(set(alternatives), key=len, reverse=True)
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(ordered) + r")(?![a-z0-9])")


@cache
def _date_words(locale: str) -> re.Pattern[str]:
    homonyms = set(DATE_HOMONYMS.get(locale, ()))
    months = [fold(month) for month in MONTHS[locale] if fold(month) not in homonyms]
    words = [*months, *WEEKDAYS[locale].split(), *DATE_WORDS[locale].split()]
    return bounded(re.escape(word) for word in words)


@cache
def number_words(locale: str) -> re.Pattern[str]:
    return bounded(re.escape(word) for word in (CARDINALS[locale] + " " + ORDINALS[locale]).split())


@cache
def number_homonyms(locale: str) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(r"(?<![a-z0-9])" + pattern) for pattern in NUMBER_HOMONYMS[locale])


@cache
def _count_nouns(locale: str) -> frozenset[str]:
    return frozenset(fold(word) for word in COUNT_NOUNS[locale].split())


@cache
def _forbidden() -> tuple[tuple[str, re.Pattern[str]], ...]:
    return tuple((code, bounded(patterns)) for code, patterns in FORBIDDEN.items())


@cache
def _lexicon() -> re.Pattern[str]:
    return bounded(re.escape(fold(name)) for name in CATALOG_MERCHANTS - COMMON_WORD_MERCHANTS)


class _SayCheck:
    def __init__(self, part: int, text: str, ledger: Ledger, locale: str) -> None:
        self.part = part
        self.original = text
        self.ledger = ledger
        self.locale = locale
        self.chunks = ledger.chunks()
        self.outside = list(text)
        self.errors: list[CheckError] = []

    def run(self) -> list[CheckError]:
        self._citations_per_sentence()
        self._references()
        self._mask_policy_figures()
        self._mask_ledger_merchants()
        self._scan_raw(EMAIL, "contact_outside_facts", mask=True)
        self._scan_raw(URL, "contact_outside_facts", mask=True)
        self._scan_raw(PHONE, "contact_outside_facts", mask=True)
        self._scan_folded(_lexicon(), "merchant_outside_reference", mask=True)
        self._scan_raw(DIGITS, "digit_outside_reference")
        self._scan_raw(CURRENCY, "currency_outside_reference")
        self._scan_folded(_date_words(self.locale), "date_outside_reference")
        self._scan_number_words()
        for code, pattern in _forbidden():
            self._scan_folded(pattern, code)
        return self.errors

    def _references(self) -> None:
        for match in REFERENCE.finditer(self.original):
            value = resolve(self.ledger, match.group(1), match.group(2))
            if value is None:
                self._report("unresolved_reference", match.span())
            elif not is_renderable(value):
                self._report("trace_only_reference", match.span())
            elif isinstance(value, Count):
                self._noun_after(match.end())
            self._mask(match.span())
        for match in CITATION.finditer(self.original):
            if match.group(1) not in self.chunks:
                self._report("unknown_citation", match.span())
            self._mask(match.span())

    def _noun_after(self, end: int) -> None:
        following = NEXT_WORD.match(self.original, end)
        if following and fold(following.group(1)) in _count_nouns(self.locale):
            self._report("noun_after_count", following.span(1))

    def _citations_per_sentence(self) -> None:
        chunk_of = {fact.id: chunk_id for chunk_id, fact in self.chunks.items()}
        start = 0
        for end in [match.end() for match in SENTENCE_END.finditer(self.original)] + [len(self.original)]:
            sentence = self.original[start:end]
            cited = {match.group(1) for match in CITATION.finditer(sentence)}
            for match in REFERENCE.finditer(sentence):
                chunk_id = chunk_of.get(match.group(1))
                if chunk_id is not None and chunk_id not in cited:
                    self._report("uncited_policy_reference", (start + match.start(), start + match.end()))
            start = end

    def _mask_policy_figures(self) -> None:
        figures = {
            render_value(value, self.ledger, self.locale)
            for fact in self.chunks.values()
            for name, value in fact.fields.items()
            if name.startswith("figures.") and isinstance(value, POLICY_FIGURES)
        }
        for figure in sorted(figures, key=len, reverse=True):
            folded_figure = fold(figure)
            current = fold("".join(self.outside))
            start = current.find(folded_figure)
            while start >= 0:
                self._report("policy_figure_outside_reference", (start, start + len(figure)))
                self._mask((start, start + len(figure)))
                start = current.find(folded_figure, start + len(figure))

    def _mask_ledger_merchants(self) -> None:
        for merchant in sorted(self.ledger.merchants(), key=len, reverse=True):
            current = "".join(self.outside)
            start = current.find(merchant)
            while start >= 0:
                self._mask((start, start + len(merchant)))
                start = current.find(merchant, start + len(merchant))

    def _scan_number_words(self) -> None:
        folded = fold("".join(self.outside))
        exempt = [
            match.span() for pattern in number_homonyms(self.locale) for match in pattern.finditer(folded)
        ]
        for match in number_words(self.locale).finditer(folded):
            if not any(start <= match.start() < end for start, end in exempt):
                self._report("number_word_outside_reference", match.span())

    def _scan_raw(self, pattern: re.Pattern[str], code: str, mask: bool = False) -> None:
        for match in pattern.finditer("".join(self.outside)):
            self._report(code, match.span())
            if mask:
                self._mask(match.span())

    def _scan_folded(self, pattern: re.Pattern[str], code: str, mask: bool = False) -> None:
        for match in pattern.finditer(fold("".join(self.outside))):
            self._report(code, match.span())
            if mask:
                self._mask(match.span())

    def _report(self, code: str, span: tuple[int, int]) -> None:
        start, end = span
        around = self.original[max(0, start - CONTEXT_CHARS) : end + CONTEXT_CHARS]
        self.errors.append(
            CheckError(code, self.part, span, self.original[start:end], INSTRUCTIONS[code], around)
        )

    def _mask(self, span: tuple[int, int]) -> None:
        for position in range(*span):
            self.outside[position] = " "
