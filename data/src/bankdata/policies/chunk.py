import math
from dataclasses import dataclass

from bankdata.policies.document import Problem
from bankdata.policies.render import RenderedDocument, RenderedSection

CHARS_PER_TOKEN = 3.5


@dataclass(frozen=True)
class Chunking:
    max_tokens: int = 512

    def params(self) -> dict[str, int | str]:
        return {"unit": "section", "max_tokens": self.max_tokens}


@dataclass(frozen=True)
class Chunk:
    section: int
    number: int
    start: int
    end: int
    text: str


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def embedding_input(title: str, heading: str, text: str) -> str:
    return f"{title}\n{heading}\n\n{text}"


def chunk_document(document: RenderedDocument) -> list[Chunk]:
    return [chunk_section(section) for section in document.sections]


def chunk_section(section: RenderedSection) -> Chunk:
    text = section.text
    start = len(text) - len(text.lstrip())
    end = len(text.rstrip())
    return Chunk(section.number, 1, start, end, text[start:end])


def oversized(document: RenderedDocument, chunking: Chunking) -> list[Problem]:
    return [
        Problem(
            document.key,
            section.line,
            "chunk_length",
            f"about {tokens} tokens in {document.country} with the title and heading; "
            f"a section embeds at most {chunking.max_tokens}",
        )
        for section in document.sections
        if (tokens := estimate_tokens(embedding_input(document.title, section.heading, section.text)))
        > chunking.max_tokens
    ]
