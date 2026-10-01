from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from core.facts import Ledger, render_value
from core.policies import PLACEHOLDER, TOPICS, CountryFacts

from bankdata.policies.document import Edition
from bankdata.policies.spec import locale

EPOCH = datetime(2000, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class FigureSpan:
    start: int
    end: int
    key: str


@dataclass(frozen=True)
class RenderedSection:
    number: int
    line: int
    heading: str
    text: str
    spans: tuple[FigureSpan, ...]


@dataclass(frozen=True)
class RenderedDocument:
    key: str
    doc_id: str
    title: str
    country: str
    language: str
    topic: str
    group: str
    doc_type: str
    version: int
    effective_date: date
    facts: CountryFacts
    sections: tuple[RenderedSection, ...]

    @property
    def locale(self) -> str:
        return locale(self.language)

    def figures(self, start: int, end: int, section: RenderedSection) -> dict[str, Mapping[str, Any]]:
        return {
            span.key: self.facts.specs[span.key]
            for span in section.spans
            if span.start < end and span.end > start
        }

    def markdown(self) -> str:
        head = [
            "---",
            f"doc_id: {self.doc_id}",
            f"title: {self.title}",
            f"country: {self.country}",
            f"language: {self.language}",
            f"topic: {self.topic}",
            f"doc_type: {self.doc_type}",
            f"version: {self.version}",
            f"policy_facts_version: {self.facts.version}",
            f"effective_date: {self.effective_date.isoformat()}",
            "---",
        ]
        body = [f"## {section.heading}\n\n{section.text}" for section in self.sections]
        return "\n".join(head) + "\n\n" + "\n\n".join(body) + "\n"


def render(edition: Edition, facts: CountryFacts) -> RenderedDocument:
    document, meta = edition.source, edition.source.meta
    ledger = Ledger(facts.country, EPOCH)
    language = locale(edition.language)
    sections = []
    for section in document.sections:
        source = "\n".join(line.text for line in section.body).strip("\n")
        parts: list[str] = []
        spans: list[FigureSpan] = []
        cursor = 0
        length = 0
        for match in PLACEHOLDER.finditer(source):
            before = source[cursor : match.start()]
            parts.append(before)
            length += len(before)
            value = render_value(facts.figure(match.group(1)), ledger, language)
            spans.append(FigureSpan(length, length + len(value), match.group(1)))
            parts.append(value)
            length += len(value)
            cursor = match.end()
        parts.append(source[cursor:])
        sections.append(
            RenderedSection(section.number, section.line, section.heading, "".join(parts), tuple(spans))
        )
    topic = str(meta["topic"])
    return RenderedDocument(
        key=document.key,
        doc_id=edition.doc_id,
        title=str(meta["title"]),
        country=facts.country,
        language=edition.language,
        topic=topic,
        group=TOPICS[topic][0],
        doc_type=str(meta["doc_type"]),
        version=int(meta["version"]),
        effective_date=meta["effective_date"],
        facts=facts,
        sections=tuple(sections),
    )
