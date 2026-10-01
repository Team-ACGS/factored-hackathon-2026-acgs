import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

import yaml
from core.policies import LANGUAGES, SOURCE_LANGUAGES, doc_id

SOURCE_KEY = re.compile(r"^(?P<doc_id>[a-z0-9-]+)/(?P<language>[A-Za-z-]+)\.md$")
SECTION = re.compile(r"^## (?P<heading>\S.*?)\s*$")
TITLE = re.compile(r"^# ")


@dataclass(frozen=True)
class Problem:
    file: str
    line: int
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}: {self.code}: {self.message}"


@dataclass(frozen=True)
class Line:
    number: int
    text: str


@dataclass(frozen=True)
class Section:
    number: int
    heading: str
    line: int
    body: tuple[Line, ...]

    def words(self) -> int:
        return sum(len(line.text.split()) for line in self.body)


@dataclass(frozen=True)
class Document:
    key: str
    text: str
    meta: dict[str, Any]
    meta_lines: dict[str, int]
    preamble: tuple[Line, ...]
    sections: tuple[Section, ...]
    problems: tuple[Problem, ...] = field(default=())

    @property
    def source_hash(self) -> str:
        return hashlib.sha256(self.text.encode()).hexdigest()

    def line_of(self, name: str) -> int:
        return self.meta_lines.get(name, 1)

    @property
    def last_line(self) -> int:
        return self.text.count("\n") + 1


@dataclass(frozen=True)
class Edition:
    source: Document
    country: str

    @property
    def doc_id(self) -> str:
        return doc_id(self.country, str(self.source.meta["topic"]))

    @property
    def language(self) -> str:
        return LANGUAGES[self.country]


def expand(source: Document) -> tuple[Edition, ...]:
    return tuple(Edition(source, country) for country in SOURCE_LANGUAGES[str(source.meta["language"])])


def edition_ids(key: str) -> tuple[str, ...]:
    path = SOURCE_KEY.match(key)
    if path is None:
        return ()
    countries = SOURCE_LANGUAGES.get(path["language"], ())
    return tuple(f"{country.lower()}-{path['doc_id']}" for country in countries)


def parse(key: str, text: str) -> Document:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return _broken(
            key, text, Problem(key, 1, "frontmatter", "the document must start with a --- frontmatter")
        )
    try:
        closing = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration:
        return _broken(key, text, Problem(key, 1, "frontmatter", "the frontmatter is never closed with ---"))
    try:
        meta = yaml.safe_load("\n".join(lines[1:closing])) or {}
    except yaml.YAMLError as error:
        return _broken(key, text, Problem(key, 1, "frontmatter", f"invalid YAML: {error}"))
    if not isinstance(meta, dict):
        return _broken(key, text, Problem(key, 1, "frontmatter", "the frontmatter is not a mapping"))
    meta_lines = {
        line.split(":", 1)[0].strip(): number + 1
        for number, line in enumerate(lines[1:closing], start=1)
        if ":" in line and not line.startswith(" ")
    }
    preamble: list[Line] = []
    sections: list[Section] = []
    heading: tuple[str, int] | None = None
    body: list[Line] = []
    for number, content in enumerate(lines[closing + 1 :], start=closing + 2):
        match = SECTION.match(content)
        if match:
            if heading is not None:
                sections.append(Section(len(sections) + 1, heading[0], heading[1], tuple(body)))
            heading, body = (match.group("heading"), number), []
        elif heading is None:
            preamble.append(Line(number, content))
        else:
            body.append(Line(number, content))
    if heading is not None:
        sections.append(Section(len(sections) + 1, heading[0], heading[1], tuple(body)))
    return Document(key, text, meta, meta_lines, tuple(preamble), tuple(sections))


def _broken(key: str, text: str, problem: Problem) -> Document:
    return Document(key, text, {}, {}, (), (), (problem,))
