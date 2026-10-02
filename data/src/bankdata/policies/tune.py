import json
import math
import re
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

from core.policies import DOCUMENT_LANGUAGES, document_language
from core.retrieval import RetrievedChunk, Retriever, near_duplicate
from core.tools.policies import SearchPoliciesInput

SECTION = re.compile(r"-s(\d+)-c\d+$")
K = 3
TOOL_K: int = SearchPoliciesInput.model_fields["k"].default
MAX_UNRELATED_RATE = 0.1


@dataclass(frozen=True)
class Answer:
    doc_id: str
    section: int


@dataclass(frozen=True)
class LabeledQuery:
    country: str
    query: str
    answers: tuple[Answer, ...] = ()
    language: str | None = None

    @property
    def document_language(self) -> str:
        return document_language(self.country)

    @property
    def cross_language(self) -> bool:
        return self.language is not None and self.language != self.document_language

    @property
    def answerable(self) -> bool:
        return bool(self.answers)


@dataclass(frozen=True)
class Outcome:
    query: LabeledQuery
    returned: tuple[str, ...]
    similarities: tuple[float, ...]
    rank: int | None
    near_duplicates: int

    @property
    def top(self) -> float | None:
        return self.similarities[0] if self.similarities else None

    @property
    def similarity(self) -> float | None:
        return self.similarities[self.rank - 1] if self.rank else None

    def hit(self, k: int = K) -> bool:
        return self.rank is not None and self.rank <= k


@dataclass(frozen=True)
class Tuning:
    corpus_hash: str
    embedding_model: str
    outcomes: tuple[Outcome, ...]
    thresholds: Mapping[str, float]

    def measured(self, language: str | None = None) -> list[Outcome]:
        return [
            outcome
            for outcome in self.outcomes
            if not outcome.query.cross_language
            and (language is None or outcome.query.document_language == language)
        ]

    def recall(self, outcomes: Iterable[Outcome], k: int = K) -> float:
        positives = [outcome for outcome in outcomes if outcome.query.answerable]
        return sum(outcome.hit(k) for outcome in positives) / len(positives) if positives else 0.0

    def to_json(self) -> str:
        cross = [outcome for outcome in self.outcomes if outcome.query.cross_language]
        summary = {
            "corpus_hash": self.corpus_hash,
            "embedding_model": self.embedding_model,
            "k": K,
            "tool_k": TOOL_K,
            "max_unrelated_rate": MAX_UNRELATED_RATE,
            "thresholds": dict(self.thresholds),
            "overall": self._block(self.measured()),
            "languages": {
                language: {
                    **self._block(self.measured(language)),
                    **self._at_cut(self.measured(language), self.thresholds[language]),
                }
                for language in DOCUMENT_LANGUAGES
            },
            "cross_language": {
                "queries": len(cross),
                f"recall_at_{K}": round(self.recall(cross), 4),
                "outcomes": [
                    {
                        "country": outcome.query.country,
                        "language": outcome.query.language,
                        "query": outcome.query.query,
                        "rank": outcome.rank,
                        "top": _round(outcome.top),
                    }
                    for outcome in cross
                ],
            },
            "near_duplicates": sum(outcome.near_duplicates for outcome in self.outcomes),
            "misses": [
                {"country": outcome.query.country, "query": outcome.query.query, "returned": outcome.returned}
                for outcome in self.measured()
                if outcome.query.answerable and not outcome.hit()
            ],
        }
        return json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n"

    def _block(self, outcomes: list[Outcome]) -> dict[str, Any]:
        return {
            "positives": sum(outcome.query.answerable for outcome in outcomes),
            "negatives": sum(not outcome.query.answerable for outcome in outcomes),
            f"recall_at_{K}": round(self.recall(outcomes), 4),
            f"recall_at_{TOOL_K}": round(self.recall(outcomes, TOOL_K), 4),
        }

    def _at_cut(self, outcomes: list[Outcome], cut: float) -> dict[str, int]:
        positives = [outcome for outcome in outcomes if outcome.query.answerable]
        return {
            "answered": sum(outcome.top is not None and outcome.top >= cut for outcome in positives),
            "hits_passing": sum(
                outcome.hit() and outcome.similarity is not None and outcome.similarity >= cut
                for outcome in positives
            ),
            "unrelated_passing": sum(
                outcome.top is not None and outcome.top >= cut
                for outcome in outcomes
                if not outcome.query.answerable
            ),
        }


def load_queries(path: Path) -> list[LabeledQuery]:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    return [
        LabeledQuery(
            str(item["country"]),
            str(item["query"]),
            tuple(
                Answer(str(answer["doc_id"]), int(answer["section"])) for answer in item.get("answers", [])
            ),
            item.get("language"),
        )
        for item in raw["query"]
    ]


def tune(retriever: Retriever, queries: list[LabeledQuery], corpus_hash: str, model: str) -> Tuning:
    outcomes = tuple(
        _outcome(labeled, retriever.search(labeled.query, labeled.country, TOOL_K, {})) for labeled in queries
    )
    measured = [outcome for outcome in outcomes if not outcome.query.cross_language]
    thresholds = {
        language: threshold(
            [
                outcome.similarity
                for outcome in measured
                if outcome.query.document_language == language
                and outcome.hit()
                and outcome.similarity is not None
            ],
            [
                outcome.top
                for outcome in measured
                if outcome.query.document_language == language
                and not outcome.query.answerable
                and outcome.top is not None
            ],
        )
        for language in DOCUMENT_LANGUAGES
    }
    return Tuning(corpus_hash, model, outcomes, thresholds)


def threshold(
    hits: Sequence[float], negatives: Sequence[float], max_rate: float = MAX_UNRELATED_RATE
) -> float:
    if not hits:
        return 1.0
    allowed = math.floor(len(negatives) * max_rate + 1e-9)
    observed = sorted({*hits, *negatives, 1.0})
    feasible = [cut for cut in observed if sum(value >= cut for value in negatives) <= allowed]
    best = max(
        feasible,
        key=lambda cut: (sum(value >= cut for value in hits) + sum(value < cut for value in negatives), -cut),
    )
    below = [value for value in observed if value < best]
    return round((best + below[-1]) / 2 if below else best, 4)


def _outcome(labeled: LabeledQuery, chunks: list[RetrievedChunk]) -> Outcome:
    accepted = {(answer.doc_id, answer.section) for answer in labeled.answers}
    rank = next(
        (
            position
            for position, chunk in enumerate(chunks, start=1)
            if (chunk.doc_id, _section(chunk.chunk_id)) in accepted
        ),
        None,
    )
    return Outcome(
        labeled,
        tuple(chunk.chunk_id for chunk in chunks),
        tuple(chunk.similarity for chunk in chunks),
        rank,
        sum(near_duplicate(left.text, right.text) for left, right in combinations(chunks, 2)),
    )


def _section(chunk_id: str) -> int | None:
    match = SECTION.search(chunk_id)
    return int(match.group(1)) if match else None


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 4)
