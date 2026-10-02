import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

from core.overlap import Shingles, jaccard, normalize, shingles

NEAR = 0.9


@dataclass(frozen=True)
class Candidate:
    chunk_id: str
    country: str
    topic: str
    text: str


def dedupe(candidates: Sequence[Candidate]) -> dict[str, str]:
    dropped: dict[str, str] = {}
    exact: dict[tuple[str, str], str] = {}
    kept: dict[tuple[str, str], list[tuple[str, Shingles]]] = {}
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
