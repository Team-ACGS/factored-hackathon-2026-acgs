import re
from collections.abc import Iterable
from datetime import date
from functools import cache

from core.facts.catalog import DATE_HOMONYMS, FORBIDDEN, MONTHS, WEEKDAYS
from core.facts.check import (
    CURRENCY,
    DIGITS,
    EMAIL,
    PHONE,
    URL,
    bounded,
    fold,
    number_homonyms,
    number_words,
)
from core.policies import COUNTRIES, LANGUAGES, PLACEHOLDER, TOPICS, CountryFacts, doc_id

from bankdata.policies.document import SOURCE_KEY, TITLE, Document, Line, Problem, Section
from bankdata.policies.spec import (
    DISCLAIMER,
    EXEMPT_WORDS,
    FIELDS,
    GLOSSARY_LABELS,
    HEADINGS,
    Limits,
    locale,
)

BRACES = re.compile(r"\{\{[^{}]*\}\}")
STRAY_BRACE = re.compile(r"[{}]")
LIST_MARKER = re.compile(r"^\s*\d+\.\s")
QUESTION = re.compile(r"^### (?P<text>.+?)\s*$")


def validate(document: Document, facts: dict[str, CountryFacts], limits: Limits) -> list[Problem]:
    if document.problems:
        return list(document.problems)
    problems = _frontmatter(document, limits)
    if problems:
        return problems
    country = str(document.meta["country"])
    language = locale(str(document.meta["language"]))
    doc_type = str(document.meta["doc_type"])
    problems.extend(_structure(document, doc_type, language, limits))
    lines = [*document.preamble, *(Line(s.line, f"## {s.heading}") for s in document.sections)]
    lines += [line for section in document.sections for line in section.body]
    for line in sorted(lines, key=lambda item: item.number):
        problems.extend(_scan(document.key, line, language, facts[country]))
    for section in document.sections:
        problems.extend(_disclaimer(document.key, section, language))
    return sorted(problems, key=lambda problem: (problem.line, problem.code))


def _frontmatter(document: Document, limits: Limits) -> list[Problem]:
    key, meta = document.key, document.meta
    problems: list[Problem] = []

    def fail(name: str, message: str) -> None:
        problems.append(Problem(key, document.line_of(name), "frontmatter", message))

    for name in FIELDS:
        if name not in meta:
            fail(name, f"missing field {name}")
    for name in sorted(set(meta) - set(FIELDS)):
        fail(name, f"unknown field {name}")
    if problems:
        return problems
    path = SOURCE_KEY.match(key)
    country, topic = meta["country"], meta["topic"]
    if country not in COUNTRIES:
        fail("country", f"country must be one of {', '.join(COUNTRIES)}")
    elif meta["language"] != LANGUAGES[country]:
        fail("language", f"language must be {LANGUAGES[country]} for {country}")
    if topic not in TOPICS:
        fail("topic", "topic is not in the taxonomy")
    elif meta["doc_type"] != TOPICS[topic][1]:
        fail("doc_type", f"doc_type must be {TOPICS[topic][1]} for {topic}")
    elif country in COUNTRIES and meta["doc_id"] != doc_id(country, topic):
        fail("doc_id", f"doc_id must be {doc_id(country, topic)}")
    if path is None or (path["country"], path["topic"], path["doc_id"]) != (country, topic, meta["doc_id"]):
        fail("doc_id", "the path must be <country>/<topic>/<doc_id>.md and match the frontmatter")
    version = meta["version"]
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        fail("version", "version must be an integer from 1")
    if not isinstance(meta["effective_date"], date):
        fail("effective_date", "effective_date must be an ISO date")
    title = meta["title"]
    if not isinstance(title, str) or not title.strip() or len(title) > limits.max_title:
        fail("title", f"title must be text of at most {limits.max_title} characters")
    elif DIGITS.search(title) or _fraud().search(fold(title)):
        fail("title", "title must have no digit and no forbidden word")
    return problems


def _structure(document: Document, doc_type: str, language: str, limits: Limits) -> list[Problem]:
    key = document.key
    problems = [
        Problem(key, line.number, "structure", "text before the first ## section")
        for line in document.preamble
        if line.text.strip()
    ][:1]
    problems += [
        Problem(key, line.number, "structure", "no # heading; the title comes from the frontmatter")
        for section in document.sections
        for line in section.body
        if TITLE.match(line.text)
    ]
    sections = document.sections
    if doc_type in HEADINGS:
        expected = HEADINGS[doc_type][language]
        for section, heading in zip(sections, expected, strict=False):
            if section.heading != heading:
                problems.append(Problem(key, section.line, "structure", f"expected section '{heading}'"))
        problems += [
            Problem(key, section.line, "structure", f"unexpected section '{section.heading}'")
            for section in sections[len(expected) :]
        ]
        last = document.text.count("\n") + 1
        problems += [
            Problem(key, last, "structure", f"missing section '{heading}'")
            for heading in expected[len(sections) :]
        ]
    elif doc_type == "faq":
        problems += _faq(key, sections, language, limits)
    else:
        problems += _glossary(key, sections, language, limits)
    for section in sections:
        words = section.words()
        if not limits.min_words <= words <= limits.max_words:
            problems.append(
                Problem(
                    key,
                    section.line,
                    "section_length",
                    f"{words} words; a section has {limits.min_words} to {limits.max_words}",
                )
            )
    return problems


def _count(key: str, sections: tuple[Section, ...], bounds: tuple[int, int], what: str) -> list[Problem]:
    low, high = bounds
    if low <= len(sections) <= high:
        return []
    line = sections[-1].line if sections else 1
    return [Problem(key, line, "structure", f"{len(sections)} {what}; expected {low} to {high}")]


def _faq(key: str, sections: tuple[Section, ...], language: str, limits: Limits) -> list[Problem]:
    problems = _count(key, sections, limits.faq_sections, "subtopics")
    questions = 0
    for section in sections:
        for index, line in enumerate(section.body):
            match = QUESTION.match(line.text)
            if not match:
                continue
            questions += 1
            text = match.group("text")
            opened = language != "es" or text.startswith("¿")
            if not text.endswith("?") or not opened:
                problems.append(
                    Problem(key, line.number, "structure", "a question ends with a question mark")
                )
            answer = _paragraphs(section.body[index + 1 :])
            if not answer:
                problems.append(Problem(key, line.number, "structure", "a question needs an answer"))
    low, high = limits.faq_questions
    if not low <= questions <= high:
        at = sections[-1].line if sections else 1
        problems.append(Problem(key, at, "structure", f"{questions} questions; expected {low} to {high}"))
    return problems


def _glossary(key: str, sections: tuple[Section, ...], language: str, limits: Limits) -> list[Problem]:
    problems = _count(key, sections, limits.glossary_sections, "term groups")
    labels = GLOSSARY_LABELS[language]
    for section in sections:
        terms = [index for index, line in enumerate(section.body) if line.text.startswith("### ")]
        if not terms:
            problems.append(Problem(key, section.line, "structure", "a term group needs ### terms"))
        for index in terms:
            paragraphs = _paragraphs(section.body[index + 1 :])
            starts = tuple(paragraph.text.split(":**", 1)[0] + ":**" for paragraph in paragraphs[:3])
            if starts != labels:
                at = section.body[index].number
                problems.append(Problem(key, at, "structure", f"a term needs {', '.join(labels)}"))
    return problems


def _paragraphs(lines: Iterable[Line]) -> list[Line]:
    found: list[Line] = []
    fresh = True
    for line in lines:
        if line.text.startswith("#"):
            break
        if not line.text.strip():
            fresh = True
        elif fresh:
            found.append(line)
            fresh = False
    return found


def _disclaimer(key: str, section: Section, language: str) -> list[Problem]:
    legal = [line for line in section.body if "{{policy.legal." in line.text]
    text = fold(" ".join(" ".join(line.text.split()) for line in section.body))
    if legal and fold(DISCLAIMER[language]) not in text:
        return [
            Problem(key, legal[0].number, "legal_disclaimer", f"add '{DISCLAIMER[language]}' to this section")
        ]
    return []


def _scan(key: str, line: Line, language: str, facts: CountryFacts) -> list[Problem]:
    outside = list(line.text)
    problems: list[Problem] = []

    def mask(span: tuple[int, int]) -> None:
        for position in range(*span):
            outside[position] = " "

    def report(code: str, message: str) -> None:
        problems.append(Problem(key, line.number, code, message))

    heading = line.text.startswith("#")
    for match in BRACES.finditer(line.text):
        placeholder = PLACEHOLDER.fullmatch(match.group(0))
        if heading:
            report("placeholder_heading", f"{match.group(0)} in a heading; headings carry no figure")
        elif placeholder is None:
            report("placeholder_malformed", f"{match.group(0)} is not {{{{policy.<group>.<key>}}}}")
        elif placeholder.group(1) not in facts.specs:
            report("placeholder_unknown", f"{match.group(0)} is not a key of {facts.country}")
        mask(match.span())
    if STRAY_BRACE.search("".join(outside)):
        report("placeholder_malformed", "a brace outside a {{policy.<group>.<key>}} placeholder")
    marker = LIST_MARKER.match(line.text)
    if marker:
        mask(marker.span())
    for match in _exempt().finditer(fold("".join(outside))):
        mask(match.span())
    for pattern, code in ((EMAIL, "raw_contact"), (URL, "raw_contact"), (PHONE, "raw_contact")):
        for match in pattern.finditer("".join(outside)):
            report(code, f"'{line.text[match.start() : match.end()]}' must be a placeholder")
            mask(match.span())
    for pattern in (DIGITS, CURRENCY):
        for match in pattern.finditer("".join(outside)):
            report("raw_figure", f"'{line.text[match.start() : match.end()]}' must be a placeholder")
            mask(match.span())
    folded = fold("".join(outside))
    for match in _dates(language).finditer(folded):
        report("raw_date", f"'{line.text[match.start() : match.end()]}' is a month or weekday name")
    homonyms = [span for pattern in number_homonyms(language) for span in _spans(pattern, folded)]
    for match in number_words(language).finditer(folded):
        if not any(start <= match.start() < end for start, end in homonyms):
            report("number_word", f"'{line.text[match.start() : match.end()]}' must be a placeholder")
    for match in _fraud().finditer(folded):
        report("forbidden_word", f"'{line.text[match.start() : match.end()]}' is forbidden")
    return problems


def _spans(pattern: re.Pattern[str], text: str) -> list[tuple[int, int]]:
    return [match.span() for match in pattern.finditer(text)]


@cache
def _dates(language: str) -> re.Pattern[str]:
    homonyms = set(DATE_HOMONYMS.get(language, ()))
    months = [fold(month) for month in MONTHS[language] if fold(month) not in homonyms]
    return bounded(re.escape(word) for word in [*months, *WEEKDAYS[language].split()])


@cache
def _exempt() -> re.Pattern[str]:
    return bounded(EXEMPT_WORDS)


@cache
def _fraud() -> re.Pattern[str]:
    return bounded(FORBIDDEN["fraud_word"])
