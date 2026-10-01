import math
import re
from dataclasses import dataclass

from bankdata.policies.render import RenderedDocument, RenderedSection

PARAGRAPH = re.compile(r"\n\s*\n")
SENTENCE_END = re.compile(r"(?<=\D[.!?])\s+(?=\S)")
CHARS_PER_TOKEN = 3.5


@dataclass(frozen=True)
class Chunking:
    min_tokens: int = 300
    max_tokens: int = 450
    overlap: float = 0.15

    def params(self) -> dict[str, float]:
        return {"min_tokens": self.min_tokens, "max_tokens": self.max_tokens, "overlap": self.overlap}


@dataclass(frozen=True)
class Chunk:
    section: int
    number: int
    start: int
    end: int
    text: str


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def chunk_document(document: RenderedDocument, chunking: Chunking) -> list[Chunk]:
    return [chunk for section in document.sections for chunk in chunk_section(section, chunking)]


def chunk_section(section: RenderedSection, chunking: Chunking) -> list[Chunk]:
    text = section.text
    units = _units(text, int(chunking.max_tokens * CHARS_PER_TOKEN * (1 - chunking.overlap)))
    if not units:
        return []
    spans: list[tuple[int, int]] = []
    cursor, first = units[0][0], 0
    while True:
        last = first
        while (
            last + 1 < len(units)
            and estimate_tokens(text[cursor : units[last + 1][1]]) <= chunking.max_tokens
        ):
            last += 1
        end = units[last][1]
        spans.append((cursor, end))
        if last + 1 >= len(units):
            break
        cursor = _overlap_start(text, units, cursor, last, chunking.overlap * (end - cursor))
        first = last + 1
    if len(spans) > 1:
        head, tail = spans[-2], spans[-1]
        merged = text[head[0] : tail[1]]
        if (
            estimate_tokens(text[tail[0] : tail[1]]) < chunking.min_tokens
            and estimate_tokens(merged) <= chunking.max_tokens
        ):
            spans[-2:] = [(head[0], tail[1])]
    return [
        Chunk(section.number, number, start, end, text[start:end])
        for number, (start, end) in enumerate(spans, 1)
    ]


def _overlap_start(text: str, units: list[tuple[int, int]], cursor: int, last: int, budget: float) -> int:
    end = units[last][1]
    earliest: int | None = None
    for index in range(last, -1, -1):
        if units[index][0] <= cursor or end - units[index][0] > budget:
            break
        earliest = units[index][0]
    if earliest is not None:
        return earliest
    space = text.find(" ", max(cursor + 1, int(end - budget)), end)
    return _trim(text, space, end)[0] if space > 0 else units[last + 1][0]


def _units(text: str, longest: int) -> list[tuple[int, int]]:
    units: list[tuple[int, int]] = []
    for paragraph in _split(text, PARAGRAPH, 0, len(text)):
        for line in _split(text, re.compile(r"\n"), *paragraph):
            for sentence in _split(text, SENTENCE_END, *line):
                units.extend(_bounded(text, sentence, longest))
    return units


def _split(text: str, pattern: re.Pattern[str], start: int, end: int) -> list[tuple[int, int]]:
    pieces: list[tuple[int, int]] = []
    cursor = start
    for match in pattern.finditer(text, start, end):
        pieces.append((cursor, match.start()))
        cursor = match.end()
    pieces.append((cursor, end))
    return [(a, b) for a, b in (_trim(text, a, b) for a, b in pieces) if b > a]


def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _bounded(text: str, unit: tuple[int, int], longest: int) -> list[tuple[int, int]]:
    start, end = unit
    pieces: list[tuple[int, int]] = []
    while end - start > longest:
        cut = text.rfind(" ", start, start + longest)
        cut = cut if cut > start else start + longest
        pieces.append(_trim(text, start, cut))
        start = _trim(text, cut, end)[0]
    pieces.append((start, end))
    return pieces
