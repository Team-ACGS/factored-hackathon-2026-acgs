import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from functools import cache

from core.facts.catalog import (
    CARDINALS,
    DATE_HOMONYMS,
    DATE_WORDS,
    FORBIDDEN,
    INSTRUCTIONS,
    MONTHS,
    NUMBER_HOMONYMS,
    ORDINALS,
    WEEKDAYS,
)
from core.facts.lexicon import CATALOG_MERCHANTS, COMMON_WORD_MERCHANTS
from core.facts.parts import Ask, Part, Say, View
from core.facts.render import CITATION, REFERENCE, is_renderable, resolve
from core.facts.values import Json, Ledger

Chunk = str | Mapping[str, object]

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
URL = re.compile(
    r"(?i)(?:https?://|www\.)\S+"
    r"|(?<![\w.-])[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|net|org|io|app|pe|mx|co|ar|br|us)(?![a-z0-9])(?:/\S*)?"
)
PHONE = re.compile(r"\+?\d[\d\s().-]{6,}\d")
DIGITS = re.compile(r"\d+")
CURRENCY = re.compile(r"US\$|R\$|S/|[$€£¥]|(?<![A-Za-z])(?:USD|PEN|MXN|COP|ARS|BRL|EUR)(?![A-Za-z])")


@dataclass(frozen=True)
class CheckError:
    code: str
    part: int
    span: tuple[int, int]
    text: str
    instruction: str

    def to_dict(self) -> Json:
        return {
            "code": self.code,
            "part": self.part,
            "span": list(self.span),
            "text": self.text,
            "instruction": self.instruction,
        }


def check(
    parts: Sequence[Part], ledger: Ledger, locale: str, chunks: Iterable[Chunk] = ()
) -> list[CheckError]:
    chunk_ids = {_chunk_id(chunk) for chunk in chunks}
    refs = ledger.refs()
    errors: list[CheckError] = []
    for index, part in enumerate(parts):
        match part:
            case Say(text):
                errors.extend(_SayCheck(index, text, ledger, locale, chunk_ids).run())
            case View(_, ids):
                errors.extend(_error("view_id_unknown", index, (0, 0), id_) for id_ in ids if id_ not in refs)
            case Ask(_, target) if target is not None and target not in refs:
                errors.append(_error("ask_target_unknown", index, (0, 0), target))
    return sorted(errors, key=lambda error: (error.part, error.span))


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


def _chunk_id(chunk: Chunk) -> str:
    return chunk if isinstance(chunk, str) else str(chunk["chunk_id"])


def _bounded(alternatives: Iterable[str]) -> re.Pattern[str]:
    ordered = sorted(set(alternatives), key=len, reverse=True)
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(ordered) + r")(?![a-z0-9])")


@cache
def _date_words(locale: str) -> re.Pattern[str]:
    homonyms = set(DATE_HOMONYMS.get(locale, ()))
    months = [fold(month) for month in MONTHS[locale] if fold(month) not in homonyms]
    words = [*months, *WEEKDAYS[locale].split(), *DATE_WORDS[locale].split()]
    return _bounded(re.escape(word) for word in words)


@cache
def _number_words(locale: str) -> re.Pattern[str]:
    return _bounded(re.escape(word) for word in (CARDINALS[locale] + " " + ORDINALS[locale]).split())


@cache
def _number_homonyms(locale: str) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(r"(?<![a-z0-9])" + pattern) for pattern in NUMBER_HOMONYMS[locale])


@cache
def _forbidden() -> tuple[tuple[str, re.Pattern[str]], ...]:
    return tuple((code, _bounded(patterns)) for code, patterns in FORBIDDEN.items())


@cache
def _lexicon() -> re.Pattern[str]:
    return _bounded(re.escape(fold(name)) for name in CATALOG_MERCHANTS - COMMON_WORD_MERCHANTS)


class _SayCheck:
    def __init__(self, part: int, text: str, ledger: Ledger, locale: str, chunk_ids: set[str]) -> None:
        self.part = part
        self.original = text
        self.ledger = ledger
        self.locale = locale
        self.chunk_ids = chunk_ids
        self.outside = list(text)
        self.errors: list[CheckError] = []

    def run(self) -> list[CheckError]:
        self._references()
        self._mask_ledger_merchants()
        self._scan_raw(EMAIL, "contact_outside_facts", mask=True)
        self._scan_raw(URL, "contact_outside_facts", mask=True)
        self._scan_raw(PHONE, "contact_outside_facts", mask=True)
        self._scan_folded(_lexicon(), "merchant_outside_reference", mask=True)
        self._scan_raw(DIGITS, "digit_outside_reference")
        self._scan_raw(CURRENCY, "currency_outside_reference")
        self._scan_folded(_date_words(self.locale), "date_outside_reference")
        self._number_words()
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
            self._mask(match.span())
        for match in CITATION.finditer(self.original):
            if match.group(1) not in self.chunk_ids:
                self._report("unknown_citation", match.span())
            self._mask(match.span())

    def _mask_ledger_merchants(self) -> None:
        for merchant in sorted(self.ledger.merchants(), key=len, reverse=True):
            current = "".join(self.outside)
            start = current.find(merchant)
            while start >= 0:
                self._mask((start, start + len(merchant)))
                start = current.find(merchant, start + len(merchant))

    def _number_words(self) -> None:
        folded = fold("".join(self.outside))
        exempt = [
            match.span() for pattern in _number_homonyms(self.locale) for match in pattern.finditer(folded)
        ]
        for match in _number_words(self.locale).finditer(folded):
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
        self.errors.append(_error(code, self.part, span, self.original[span[0] : span[1]]))

    def _mask(self, span: tuple[int, int]) -> None:
        for position in range(*span):
            self.outside[position] = " "
