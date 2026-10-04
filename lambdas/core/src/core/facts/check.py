import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import cache

from core.countries import zone
from core.facts.catalog import (
    CARDINALS,
    COUNT_NOUNS,
    DATE_HOMONYMS,
    DATE_PREPOSITIONS,
    DATE_WORDS,
    FEMININE_NOUNS,
    FORBIDDEN,
    INSTRUCTIONS,
    MONTHS,
    NOUNS,
    NUMBER_HOMONYMS,
    NUMBER_VALUES,
    ORDINALS,
    PERIOD_PREPOSITIONS,
    PRESENT_TODAY,
    PROCESS_ACTIONS,
    RELATIVE_DAY_LEADS,
    UNSEEN_CLAIMS,
    VOSEO,
    WEEKDAYS,
)
from core.facts.lexicon import CATALOG_MERCHANTS, COMMON_WORD_MERCHANTS
from core.facts.parts import Ask, Part, Say, View
from core.facts.render import CITATION, REFERENCE, is_renderable, is_singular, render_value, resolve
from core.facts.targets import SHOWN_ROWS, Unfit, ask_options, view_items
from core.facts.values import (
    Channel,
    Count,
    Day,
    Instant,
    Json,
    Ledger,
    Money,
    Note,
    Percent,
    Period,
    Status,
    Url,
    Value,
)

POLICY_FIGURES = (Count, Money, Percent, Channel, Url)
SENTENCE_END = re.compile(r"[.!?]+(?=\s|$)")
QUOTES = "\"'\u201c\u201d\u2018\u2019\u00ab\u00bb"
QUOTED_REFERENCE = re.compile(rf"[{QUOTES}]\s*(\{{(f\d+)\.([a-z_][a-z0-9_.]*)\}})\s*[{QUOTES}]")
SENTENCE = re.compile(r".*?(?:[.!?]+(?=\s|$)|$)\s*", re.DOTALL)

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
URL = re.compile(
    r"(?i)(?:https?://|www\.)\S+"
    r"|(?<![\w.-])[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|net|org|io|app|pe|mx|co|ar|br|us)(?![a-z0-9])(?:/\S*)?"
)
PHONE = re.compile(r"\+?\d[\d\s().-]{6,}\d")
DIGITS = re.compile(r"\d+")
NOUN_LINKS = frozenset({"de", "do", "da", "of"})
WORD_BEFORE = re.compile(r"(?<!\w)(\w+)\s+$")
CONTEXT_CHARS = 30
CITATION_AFTER_END = re.compile(r"\s*([.!?])\s*(\[p:[^\[\]\s]+\])")
NOTHING = re.compile(r"(?!)")
MISSING_PREPOSITION = {
    "pt-BR": re.compile(
        r"(?<!sobre )(?<!Sobre )\b[Qq]ua(?:l|is) (?:delas|deles|dessas|desses) (?:você|voce) "
        r"(?:quer|gostaria de) saber\b"
    ),
}
VOSEO_FORMS = re.compile(r"(?<!\w)(?:" + "|".join(VOSEO) + r")(?!\w)", re.IGNORECASE)
SPEND_SCOPE = frozenset({"merchant", "period", "compare_period", "last4"})
PLURAL_CUES = {
    "es": re.compile(r"(?<!\w)(?:están|son|ambas|ambos|todas|todos)(?!\w)", re.IGNORECASE),
    "pt-BR": re.compile(r"(?<!\w)(?:estão|são|ambas|ambos|todas|todos)(?!\w)", re.IGNORECASE),
}
CLAUSE_START = re.compile(r"[.;:!?]")
PARTICIPLE = re.compile(r"\s+(\w{3,}?[ai]d|activ)(os|as|o|a)(?!\w)")
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
                    errors.append(_part_error(unfit.code, index, unfit.fact_id, part))
            case Ask(ask) if ask not in allowed_asks:
                errors.append(_part_error("ask_not_allowed", index, ask, part))
            case Ask("show") if any(isinstance(other, View) for other in parts):
                errors.append(_part_error("show_with_view", index, "show", part))
            case Ask():
                try:
                    ask_options(part, ledger)
                except Unfit as unfit:
                    errors.append(_part_error(unfit.code, index, unfit.fact_id, part))
    errors.extend(_movements_beside_spend(parts, ledger))
    errors.extend(_cards_without_series(parts, ledger))
    return sorted(errors, key=lambda error: (error.part, error.span))


def tidy_reply(texts: Sequence[str], ledger: Ledger) -> tuple[list[str], dict[str, int]]:
    kinds = {fact_id: fact.kind for fact_id, fact in ledger.facts.items()}

    def referenced(text: str) -> set[str | None]:
        return {kinds.get(match.group(1)) for match in REFERENCE.finditer(text)}

    def restates_search(sentence: str) -> bool:
        found = [(kinds.get(match.group(1)), match.group(2)) for match in REFERENCE.finditer(sentence)]
        return any(kind == "movements" for kind, _ in found) and all(
            kind == "movements" or (kind == "spend" and field in SPEND_SCOPE) for kind, field in found
        )

    spend = any("spend" in referenced(text) for text in texts)

    def dropped_as(sentence: str) -> str | None:
        found = referenced(sentence)
        if spend and restates_search(sentence):
            return "movements_beside_spend"
        if found or CITATION.search(sentence):
            return None
        if _process_actions().search(fold(sentence)):
            return "uncited_process"
        if _location_talk().search(fold(sentence)):
            return "location_talk"
        return None

    kept: list[str] = []
    edits: dict[str, int] = {}
    for text in texts:
        others = []
        for sentence in (match.group(0) for match in SENTENCE.finditer(text) if match.group(0)):
            kind = dropped_as(sentence)
            if kind is None:
                others.append(sentence)
            else:
                edits[kind] = edits.get(kind, 0) + 1
        if "".join(others).strip():
            kept.append("".join(others).strip())
    if not kept:
        return list(texts), {}
    return kept, edits


def _cards_without_series(parts: Sequence[Part], ledger: Ledger) -> list[CheckError]:
    says = [(index, part.text) for index, part in enumerate(parts) if isinstance(part, Say)]
    series = {
        fact.fields.get("card_ref")
        for _, text in says
        for match in REFERENCE.finditer(text)
        if (fact := ledger.get(match.group(1))) is not None and fact.kind == "recurring"
    }
    if not series:
        return []
    errors = []
    for index, text in says:
        offset = 0
        for sentence in SENTENCE.findall(text):
            fields: dict[str, set[str]] = {}
            for match in REFERENCE.finditer(sentence):
                fields.setdefault(match.group(1), set()).add(match.group(2))
            for match in REFERENCE.finditer(sentence):
                fact = ledger.get(match.group(1))
                if (
                    fact is not None
                    and fact.kind == "card"
                    and fields[fact.id] == {"last4"}
                    and fact.fields.get("card_ref") not in series
                ):
                    span = (offset + match.start(), offset + match.end())
                    errors.append(_error("card_without_series", index, span, match.group(0)))
            offset += len(sentence)
    return errors


def _movements_beside_spend(parts: Sequence[Part], ledger: Ledger) -> list[CheckError]:
    said = [(index, part.text) for index, part in enumerate(parts) if isinstance(part, Say)]
    kinds = {fact_id: fact.kind for fact_id, fact in ledger.facts.items()}
    references = [(index, match) for index, text in said for match in REFERENCE.finditer(text)]
    if not any(kinds.get(match.group(1)) == "spend" for _, match in references):
        return []
    return [
        _error("movements_beside_spend", index, match.span(), match.group(0))
        for index, match in references
        if kinds.get(match.group(1)) == "movements"
    ]


def repair_instruction(errors: Sequence[CheckError]) -> str:
    codes = list(dict.fromkeys(error.code for error in errors))
    return (
        f"Call reply again once, with all {len(codes)} kinds of error below fixed together "
        f"({', '.join(codes)}); keep every part that had no error."
    )


def tidy(text: str, ledger: Ledger, locale: str) -> tuple[str, dict[str, int]]:
    text, citations = CITATION_AFTER_END.subn(r" \2\1", text)
    text, numbers = _counts_as_references(text, ledger, locale)
    text, nouns = _drop_doubled_nouns(text, ledger, locale)
    text, periods = _drop_prepositions(text, ledger, (Period,), PERIOD_PREPOSITIONS[locale])
    text, relative = _relative_day_leads(text, ledger, locale)
    text, dates = _drop_prepositions(text, ledger, (Day, Instant), DATE_PREPOSITIONS[locale])
    text, agreement = _agree_after_counts(text, ledger, locale)
    text, plural_statuses = _plural_card_statuses(text, ledger, locale)
    text, dashes = DASH.subn(", ", text)
    text, grammar = MISSING_PREPOSITION.get(locale, NOTHING).subn(_with_preposition, text)
    text, voseo = VOSEO_FORMS.subn(_as_tu, text) if locale == "es" else (text, 0)
    text, quotes = _unquoted_notes(text, ledger)
    edits = {
        "number_word": numbers,
        "doubled_noun": nouns,
        "period_preposition": periods,
        "date_preposition": dates,
        "relative_day": relative,
        "agreement": agreement + plural_statuses,
        "dash": dashes,
        "grammar": grammar,
        "voseo": voseo,
        "citation_placement": citations,
        "note_quotes": quotes,
    }
    return text, {kind: count for kind, count in edits.items() if count}


def _unquoted_notes(text: str, ledger: Ledger) -> tuple[str, int]:
    def unquote(match: re.Match[str]) -> str:
        quoted = isinstance(resolve(ledger, match.group(2), match.group(3)), Note)
        return match.group(1) if quoted else match.group(0)

    return QUOTED_REFERENCE.subn(unquote, text)


def _as_tu(match: re.Match[str]) -> str:
    said = match.group(0)
    tu = VOSEO[said.lower()]
    return tu[:1].upper() + tu[1:] if said[:1].isupper() else tu


def _with_preposition(match: re.Match[str]) -> str:
    asked = match.group(0)
    return ("Sobre q" if asked[0] == "Q" else "sobre q") + asked[1:]


def _counts_as_references(text: str, ledger: Ledger, locale: str) -> tuple[str, int]:
    by_noun: dict[str, list[tuple[str, Count]]] = {}
    for fact in ledger.facts.values():
        for name, value in fact.fields.items():
            if isinstance(value, Count):
                by_noun.setdefault(value.noun, []).append((f"{{{fact.id}.{name}}}", value))
    only = {noun: found[0] for noun, found in by_noun.items() if len(found) == 1}
    folded = fold(text)
    swaps = []
    for match in number_words(locale).finditer(folded):
        number = NUMBER_VALUES[locale].get(match.group(0))
        for noun, (reference, count) in only.items():
            plural = fold(NOUNS.get(noun, {}).get(locale, ("", ""))[1])
            following = re.compile(r"\s+" + r"\s+".join(map(re.escape, plural.split())) + r"(?!\w)")
            after = following.match(folded, match.end()) if plural else None
            if after and count.value == number:
                swaps.append((match.start(), after.end(), reference))
                break
    for start, end, reference in reversed(swaps):
        text = text[:start] + reference + text[end:]
    return text, len(swaps)


def _drop_prepositions(
    text: str, ledger: Ledger, kinds: tuple[type, ...], prepositions: frozenset[str]
) -> tuple[str, int]:
    cuts = []
    for match in REFERENCE.finditer(text):
        before = WORD_BEFORE.search(text, 0, match.start())
        typed = isinstance(resolve(ledger, match.group(1), match.group(2)), kinds)
        if typed and before and fold(before.group(1)) in prepositions:
            cuts.append(before.span())
    for start, end in reversed(cuts):
        text = text[:start] + text[end:]
    return text, len(cuts)


def _relative_day_leads(text: str, ledger: Ledger, locale: str) -> tuple[str, int]:
    leads = RELATIVE_DAY_LEADS[locale]
    swaps = []
    for match in REFERENCE.finditer(text):
        before = WORD_BEFORE.search(text, 0, match.start())
        value = resolve(ledger, match.group(1), match.group(2))
        if before and fold(before.group(1)) in leads and _relative(value, ledger):
            lead = leads[fold(before.group(1))]
            swaps.append((before.start(), before.end(), f"{lead} " if lead else ""))
    for start, end, lead in reversed(swaps):
        text = text[:start] + lead + text[end:]
    return text, len(swaps)


def _relative(value: Value | None, ledger: Ledger) -> bool:
    if isinstance(value, Period) and value.start == value.end:
        day = value.start
    elif isinstance(value, Day):
        day = value.value
    elif isinstance(value, Instant):
        day = value.value.astimezone(zone(ledger.country)).date()
    else:
        return False
    return (ledger.today - day).days in (0, 1)


def _agree_after_counts(text: str, ledger: Ledger, locale: str) -> tuple[str, int]:
    if locale not in FEMININE_NOUNS:
        return text, 0
    swaps = []
    for match in REFERENCE.finditer(text):
        count = resolve(ledger, match.group(1), match.group(2))
        participle = PARTICIPLE.match(text, match.end())
        if not isinstance(count, Count) or participle is None:
            continue
        vowel = "a" if count.noun in FEMININE_NOUNS[locale] else "o"
        ending = vowel if is_singular(count.value, locale) else vowel + "s"
        if participle.group(2) != ending:
            swaps.append((participle.start(2), participle.end(2), ending))
    for start, end, ending in reversed(swaps):
        text = text[:start] + ending + text[end:]
    return text, len(swaps)


def _plural_card_statuses(text: str, ledger: Ledger, locale: str) -> tuple[str, int]:
    cue = PLURAL_CUES.get(locale)
    if cue is None:
        return text, 0
    swaps = []
    for match in REFERENCE.finditer(text):
        value = resolve(ledger, match.group(1), match.group(2))
        if not isinstance(value, Status) or value.domain != "card":
            continue
        clause = CLAUSE_START.split(text[: match.start()])[-1]
        if cue.search(clause):
            swaps.append((match.start(), match.end(), render_value(value, ledger, locale) + "s"))
    for start, end, plural in reversed(swaps):
        text = text[:start] + plural + text[end:]
    return text, len(swaps)


def _drop_doubled_nouns(text: str, ledger: Ledger, locale: str) -> tuple[str, int]:
    cuts = []
    for match in REFERENCE.finditer(text):
        value = resolve(ledger, match.group(1), match.group(2))
        doubled = doubled_noun(text, match.end(), value, locale) if isinstance(value, Count) else None
        if doubled:
            cuts.append((match.end(), doubled[1]))
    for start, end in reversed(cuts):
        text = text[:start] + text[end:]
    return text, len(cuts)


def doubled_noun(text: str, end: int, count: Count, locale: str) -> tuple[int, int] | None:
    match = _noun_phrases(count.noun, locale).match(fold(text), end)
    return match.span(1) if match else None


@cache
def _noun_phrases(noun: str, locale: str) -> re.Pattern[str]:
    phrases: set[tuple[str, ...]] = {(word,) for word in _count_nouns(locale)}
    for form in NOUNS.get(noun, {}).get(locale, ()):
        words = fold(form).split()
        phrases.update(tuple(words[start:]) for start in range(len(words)) if set(words[start:]) - NOUN_LINKS)
    alternatives = sorted((r"\s+".join(map(re.escape, phrase)) for phrase in phrases), key=len, reverse=True)
    return re.compile(r"\s+(" + "|".join(alternatives) + r")(?!\w)")


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


def _part_error(code: str, part: int, text: str, shown: View | Ask) -> CheckError:
    kind, name = ("view", shown.view) if isinstance(shown, View) else ("ask", shown.ask)
    described = f"{kind} {name} with facts {', '.join(shown.facts)}"
    return CheckError(code, part, (0, 0), text, INSTRUCTIONS[code], described)


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
def _present_today(locale: str) -> re.Pattern[str]:
    return bounded([PRESENT_TODAY[locale]])


@cache
def _location_talk() -> re.Pattern[str]:
    return bounded(FORBIDDEN["location_talk"])


@cache
def _process_actions() -> re.Pattern[str]:
    return bounded(PROCESS_ACTIONS)


@cache
def _unseen_claims() -> re.Pattern[str]:
    return bounded(UNSEEN_CLAIMS)


def _unseen_rows(ledger: Ledger) -> bool:
    return any(
        fact.kind == "movements"
        and isinstance(count := fact.fields.get("count"), Count)
        and count.value > SHOWN_ROWS
        for fact in ledger.facts.values()
    )


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
        self._mask_folded(_present_today(self.locale))
        self._scan_folded(_date_words(self.locale), "date_outside_reference")
        self._scan_number_words()
        if _unseen_rows(self.ledger):
            self._scan_folded(_unseen_claims(), "unseen_rows_claim")
        for code, pattern in _forbidden():
            self._scan_folded(pattern, code)
        self._uncited_process()
        return self.errors

    def _uncited_process(self) -> None:
        start = 0
        for end in [match.end() for match in SENTENCE_END.finditer(self.original)] + [len(self.original)]:
            sentence = self.original[start:end]
            found = _process_actions().search(fold(sentence))
            if found and not CITATION.search(sentence):
                self._report("uncited_process", (start + found.start(), start + found.end()))
            start = end

    def _mask_folded(self, pattern: re.Pattern[str]) -> None:
        for match in pattern.finditer(fold("".join(self.outside))):
            self._mask(match.span())

    def _references(self) -> None:
        for match in REFERENCE.finditer(self.original):
            value = resolve(self.ledger, match.group(1), match.group(2))
            if value is None:
                self._report("unresolved_reference", match.span())
            elif not is_renderable(value):
                self._report("trace_only_reference", match.span())
            elif isinstance(value, Count):
                self._noun_after(match.end(), value)
            self._mask(match.span())
        for match in CITATION.finditer(self.original):
            if match.group(1) not in self.chunks:
                self._report("unknown_citation", match.span())
            self._mask(match.span())

    def _noun_after(self, end: int, count: Count) -> None:
        doubled = doubled_noun(self.original, end, count, self.locale)
        if doubled:
            self._report("noun_after_count", doubled)

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
