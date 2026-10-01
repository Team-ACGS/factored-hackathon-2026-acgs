import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass

from core.facts.check import fold

WORD = re.compile(r"[a-z0-9]+")
SHINGLE = 5
NEAR = 0.9


@dataclass(frozen=True)
class Candidate:
    chunk_id: str
    country: str
    topic: str
    text: str


def normalize(text: str) -> str:
    return " ".join(WORD.findall(fold(text)))


def shingles(text: str) -> frozenset[tuple[str, ...]]:
    words = normalize(text).split()
    if len(words) <= SHINGLE:
        return frozenset({tuple(words)})
    return frozenset(tuple(words[index : index + SHINGLE]) for index in range(len(words) - SHINGLE + 1))


def jaccard(left: frozenset[tuple[str, ...]], right: frozenset[tuple[str, ...]]) -> float:
    union = len(left | right)
    return len(left & right) / union if union else 1.0


def dedupe(candidates: Sequence[Candidate]) -> dict[str, str]:
    dropped: dict[str, str] = {}
    exact: dict[tuple[str, str], str] = {}
    kept: dict[tuple[str, str], list[tuple[str, frozenset[tuple[str, ...]]]]] = {}
    for candidate in candidates:
        digest = hashlib.sha256(normalize(candidate.text).encode()).hexdigest()
        twin = exact.get((candidate.country, digest))
        if twin is not None:
            dropped[candidate.chunk_id] = twin
            continue
        exact[(candidate.country, digest)] = candidate.chunk_id
        own = shingles(candidate.text)
        group = kept.setdefault((candidate.country, candidate.topic), [])
        near = next((chunk_id for chunk_id, other in group if jaccard(own, other) >= NEAR), None)
        if near is not None:
            dropped[candidate.chunk_id] = near
            continue
        group.append((candidate.chunk_id, own))
    return dropped
