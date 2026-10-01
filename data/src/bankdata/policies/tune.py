import json
import re
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

from core.retrieval import Retriever

SECTION = re.compile(r"-s(\d+)-c\d+$")


@dataclass(frozen=True)
class LabeledQuery:
    country: str
    query: str
    doc_id: str | None = None
    section: int | None = None


@dataclass(frozen=True)
class Outcome:
    query: LabeledQuery
    rank: int | None
    similarity: float | None
    top: float | None


@dataclass(frozen=True)
class Tuning:
    corpus_hash: str
    embedding_model: str
    k: int
    recall: float
    threshold: float
    outcomes: tuple[Outcome, ...]

    def to_json(self) -> str:
        misses = [
            asdict(outcome.query)
            for outcome in self.outcomes
            if outcome.query.doc_id and outcome.rank is None
        ]
        summary = {
            "corpus_hash": self.corpus_hash,
            "embedding_model": self.embedding_model,
            "k": self.k,
            f"recall_at_{self.k}": round(self.recall, 4),
            "threshold": self.threshold,
            "positives": sum(1 for outcome in self.outcomes if outcome.query.doc_id),
            "negatives": sum(1 for outcome in self.outcomes if not outcome.query.doc_id),
            "misses": misses,
        }
        return json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def load_queries(path: Path) -> list[LabeledQuery]:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    return [
        LabeledQuery(str(item["country"]), str(item["query"]), item.get("doc_id"), item.get("section"))
        for item in raw["query"]
    ]


def tune(
    retriever: Retriever, queries: list[LabeledQuery], corpus_hash: str, model: str, k: int = 3
) -> Tuning:
    outcomes = []
    for labeled in queries:
        chunks = retriever.search(labeled.query, labeled.country, k, {})
        rank = next(
            (
                position
                for position, chunk in enumerate(chunks, start=1)
                if chunk.doc_id == labeled.doc_id and _section(chunk.chunk_id) == labeled.section
            ),
            None,
        )
        outcomes.append(
            Outcome(
                labeled,
                rank,
                chunks[rank - 1].similarity if rank else None,
                chunks[0].similarity if chunks else None,
            )
        )
    positives = [outcome for outcome in outcomes if outcome.query.doc_id]
    hits = [outcome.similarity for outcome in positives if outcome.similarity is not None]
    negatives = [outcome.top for outcome in outcomes if not outcome.query.doc_id and outcome.top is not None]
    recall = len(hits) / len(positives) if positives else 0.0
    return Tuning(corpus_hash, model, k, recall, threshold(hits, negatives), tuple(outcomes))


def threshold(hits: list[float], negatives: list[float]) -> float:
    if not hits:
        return 1.0
    observed = sorted({*hits, *negatives})
    best = max(
        observed,
        key=lambda cut: (sum(value >= cut for value in hits) + sum(value < cut for value in negatives), -cut),
    )
    below = [value for value in observed if value < best]
    return round((best + below[-1]) / 2 if below else best, 4)


def _section(chunk_id: str) -> int | None:
    match = SECTION.search(chunk_id)
    return int(match.group(1)) if match else None
