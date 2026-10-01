import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from functools import cache
from typing import Any, Protocol

from core.policies import decode_figures, encode_figures, figure
from core.vectors import (
    SEARCH_QUERY,
    Embedder,
    Match,
    VectorIndex,
    VectorStoreError,
    bedrock_runtime,
    s3vectors,
    where_equal,
)


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    doc_id: str
    title: str
    section: str
    text: str
    doc_type: str
    country: str
    version: int
    facts_version: int
    effective_date: date
    page: int
    figures: Mapping[str, Mapping[str, Any]]
    similarity: float


class Retriever(Protocol):
    def search(
        self, query: str, country: str, k: int, filters: Mapping[str, str]
    ) -> list[RetrievedChunk]: ...


@dataclass(frozen=True)
class VectorRetriever:
    embedder: Embedder
    index: VectorIndex

    def search(self, query: str, country: str, k: int, filters: Mapping[str, str]) -> list[RetrievedChunk]:
        [vector] = self.embedder.embed([query], SEARCH_QUERY)
        matches = self.index.query(vector, k, where_equal({**filters, "country": country}))
        return [to_chunk(match) for match in matches]


NON_FILTERABLE = frozenset(
    {
        "text",
        "title",
        "section",
        "page_end",
        "url",
        "figures",
        "effective_date",
        "policy_facts_version",
        "content_hash",
    }
)


@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: str
    country: str
    language: str
    group: str
    topic: str
    doc_type: str
    doc_id: str
    version: int
    facts_version: int
    effective_date: date
    section: str
    title: str
    text: str
    figures: Mapping[str, Mapping[str, Any]]
    page_start: int
    page_end: int
    url: str
    content_hash: str

    def metadata(self) -> dict[str, Any]:
        return {
            "country": self.country,
            "language": self.language,
            "group": self.group,
            "topic": self.topic,
            "doc_type": self.doc_type,
            "doc_id": self.doc_id,
            "version": self.version,
            "page_start": self.page_start,
            "text": self.text,
            "title": self.title,
            "section": self.section,
            "page_end": self.page_end,
            "url": self.url,
            "figures": encode_figures(self.figures),
            "effective_date": self.effective_date.isoformat(),
            "policy_facts_version": self.facts_version,
            "content_hash": self.content_hash,
        }


def to_chunk(match: Match) -> RetrievedChunk:
    try:
        return _chunk(match)
    except (ValueError, KeyError, TypeError) as error:
        raise VectorStoreError(f"{match.key}: unreadable metadata: {error}") from error


def _chunk(match: Match) -> RetrievedChunk:
    metadata = match.metadata
    figures = decode_figures(str(metadata.get("figures") or ""))
    for spec in figures.values():
        figure(spec)
    return RetrievedChunk(
        chunk_id=match.key,
        doc_id=str(metadata["doc_id"]),
        title=str(metadata["title"]),
        section=str(metadata["section"]),
        text=str(metadata["text"]),
        doc_type=str(metadata["doc_type"]),
        country=str(metadata["country"]),
        version=int(metadata["version"]),
        facts_version=int(metadata["policy_facts_version"]),
        effective_date=date.fromisoformat(str(metadata["effective_date"])),
        page=int(metadata["page_start"]),
        figures=figures,
        similarity=1.0 - match.distance,
    )


@dataclass(frozen=True)
class PolicySearch:
    retriever: Retriever
    min_similarity: float
    docs_domain: str


@cache
def policy_search() -> PolicySearch:
    retriever = VectorRetriever(
        Embedder(bedrock_runtime(), os.environ["POLICY_EMBEDDING_MODEL_ID"]),
        VectorIndex(s3vectors(), os.environ["POLICY_INDEX_ARN"]),
    )
    return PolicySearch(
        retriever, float(os.environ["POLICY_MIN_SIMILARITY"]), os.environ["POLICY_DOCS_DOMAIN"]
    )
