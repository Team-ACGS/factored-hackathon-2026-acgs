import re
from collections.abc import Iterable, Sequence
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
from core.policies import PLACEHOLDER, SOURCE_LANGUAGES, TOPICS, CountryFacts, base_id

from bankdata.policies.document import SOURCE_KEY, TITLE, Document, Line, Problem, Section
from bankdata.policies.spec import (
    DISCLAIMER,
    EXEMPT_WORDS,
    FIELDS,
    GLOSSARY_LABELS,
    HEADINGS,
    INFORMAL,
    LITERAL_ACRONYMS,
    LITERAL_NAMES,
    Limits,
    locale,
)

BRACES = re.compile(r"\{\{[^{}]*\}\}")
STRAY_BRACE = re.compile(r"[{}]")
LIST_MARKER = re.compile(r"^\s*\d+\.\s")
QUESTION = re.compile(r"^### (?P<text>.+?)\s*$")
SHARED_FIELDS = ("doc_id", "topic", "doc_type", "version", "effective_date")


def validate_all(
    documents: Sequence[Document], facts: dict[str, CountryFacts], limits: Limits
) -> dict[str, list[Problem]]:
    problems = {document.key: validate(document, facts, limits) for document in documents}
    for problem in parity(documents):
        problems[problem.file].append(problem)
    return problems


def validate(document: Document, facts: dict[str, CountryFacts], limits: Limits) -> list[Problem]:
    if document.problems:
        return list(document.problems)
    problems = _frontmatter(document, limits)
    if problems:
        return problems
    language = locale(str(document.meta["language"]))
    countries = [facts[country] for country in SOURCE_LANGUAGES[str(document.meta["language"])]]
    names = _names(_name_values(facts))
    doc_type = str(document.meta["doc_type"])
    problems.extend(_structure(document, doc_type, language, limits))
    title = Line(document.line_of("title"), str(document.meta["title"]))
    problems.extend(_words(document.key, title, title.text, language, names))
    lines = [*document.preamble, *(Line(s.line, f"## {s.heading}") for s in document.sections)]
    lines += [line for section in document.sections for line in section.body]
    for line in sorted(lines, key=lambda item: item.number):
        problems.extend(_scan(document.key, line, language, countries, names))
    for section in document.sections:
        problems.extend(_disclaimer(document.key, section, language))
    return sorted(problems, key=lambda problem: (problem.line, problem.code))


def parity(documents: Sequence[Document]) -> list[Problem]:
    groups: dict[str, dict[str, Document]] = {}
    for document in documents:
        path = SOURCE_KEY.match(document.key)
        if path is not None and path["language"] in SOURCE_LANGUAGES:
            groups.setdefault(path["doc_id"], {})[path["language"]] = document
    problems: list[Problem] = []
    for name, files in sorted(groups.items()):
        reference_language = next(language for language in SOURCE_LANGUAGES if language in files)
        reference = files[reference_language]
        for language in SOURCE_LANGUAGES:
            if language not in files:
                problems.append(
                    Problem(reference.key, 1, "parity", f"document {name} has no {language} file")
                )
            elif files[language] is not reference:
                problems += _pair(name, reference, reference_language, files[language], language)
    return problems


def _pair(name: str, reference: Document, base: str, other: Document, language: str) -> list[Problem]:
    if reference.problems or other.problems:
        return []
    problems = [
        Problem(other.key, other.line_of(field), "parity", f"document {name}: {field} differs from {base}")
        for field in SHARED_FIELDS
        if field in reference.meta and other.meta.get(field) != reference.meta[field]
    ]
    for number in range(1, max(len(reference.sections), len(other.sections)) + 1):
        if number > len(other.sections):
            heading = reference.sections[number - 1].heading
            problems.append(
                Problem(
                    other.key,
                    other.last_line,
                    "parity",
                    f"document {name}: section {number} '{heading}' of {base} is missing in {language}",
                )
            )
            continue
        section = other.sections[number - 1]
        if number > len(reference.sections):
            problems.append(
                Problem(
                    other.key,
                    section.line,
                    "parity",
                    f"document {name}: section {number} of {language} is not in {base}",
                )
            )
            continue
        expected, found = _placeholders(reference.sections[number - 1]), _placeholders(section)
        if expected != found:
            changes = [f"missing {key}" for key in sorted(expected - found)]
            changes += [f"extra {key}" for key in sorted(found - expected)]
            problems.append(
                Problem(
                    other.key,
                    section.line,
                    "parity",
                    f"document {name}: section {number} of {language} differs from {base}: "
                    + ", ".join(changes),
                )
            )
    return problems


def _placeholders(section: Section) -> set[str]:
    return {match.group(1) for line in section.body for match in PLACEHOLDER.finditer(line.text)}


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
    language, topic = meta["language"], meta["topic"]
    if language not in SOURCE_LANGUAGES:
        fail("language", f"language must be one of {', '.join(SOURCE_LANGUAGES)}")
    if topic not in TOPICS:
        fail("topic", "topic is not in the taxonomy")
    elif meta["doc_type"] != TOPICS[topic][1]:
        fail("doc_type", f"doc_type must be {TOPICS[topic][1]} for {topic}")
    elif meta["doc_id"] != base_id(topic):
        fail("doc_id", f"doc_id must be {base_id(topic)}")
    if path is None or (path["doc_id"], path["language"]) != (meta["doc_id"], language):
        fail("doc_id", "the path must be <doc_id>/<language>.md and match the frontmatter")
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
        problems += [
            Problem(key, document.last_line, "structure", f"missing section '{heading}'")
            for heading in expected[len(sections) :]
        ]
    elif doc_type == "faq":
        problems += _faq(key, sections, language, limits)
    else:
        problems += _glossary(key, sections, language, limits)
    low, high = limits.section_words
    for section in sections:
        words = section.words()
        if not low <= words <= high:
            problems.append(
                Problem(key, section.line, "section_length", f"{words} words; a section has {low} to {high}")
            )
    total = sum(section.words() for section in sections)
    low, high = limits.document_words
    if sections and not low <= total <= high:
        problems.append(
            Problem(
                key, sections[0].line, "document_length", f"{total} words; a document has {low} to {high}"
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


def _scan(
    key: str, line: Line, language: str, countries: list[CountryFacts], names: re.Pattern[str]
) -> list[Problem]:
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
        else:
            missing = [facts.country for facts in countries if placeholder.group(1) not in facts.specs]
            if missing:
                report("placeholder_unknown", f"{match.group(0)} is not a key of {', '.join(missing)}")
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
    return problems + _words(key, line, "".join(outside), language, names)


def _words(key: str, line: Line, text: str, language: str, names: re.Pattern[str]) -> list[Problem]:
    problems = [
        Problem(
            key,
            line.number,
            "literal_name",
            f"'{line.text[match.start() : match.end()]}' names a country or an authority; "
            "use its placeholder or a generic noun",
        )
        for pattern, target in ((names, fold(text)), (_acronyms(), text))
        for match in pattern.finditer(target)
    ]
    if language in INFORMAL:
        problems += [
            Problem(
                key,
                line.number,
                "register",
                f"'{line.text[match.start() : match.end()]}' is informal; "
                f"write {'usted' if language == 'es' else 'você'}",
            )
            for match in _informal(language).finditer(fold(text))
        ]
    return problems


def _name_values(facts: dict[str, CountryFacts]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                str(spec["value"])
                for country in facts.values()
                for spec in country.specs.values()
                if spec.get("type") == "name"
            }
        )
    )


@cache
def _names(values: tuple[str, ...]) -> re.Pattern[str]:
    return bounded(
        r"\s+".join(re.escape(word) for word in fold(name).split()) for name in (*LITERAL_NAMES, *values)
    )


@cache
def _acronyms() -> re.Pattern[str]:
    ordered = sorted(LITERAL_ACRONYMS, key=len, reverse=True)
    return re.compile(r"(?<![A-Za-z0-9])(?:" + "|".join(map(re.escape, ordered)) + r")(?![A-Za-z0-9])")


@cache
def _informal(language: str) -> re.Pattern[str]:
    return bounded(fold(word) for word in INFORMAL[language])


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
