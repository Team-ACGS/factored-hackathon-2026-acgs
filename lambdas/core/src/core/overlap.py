import re

from core.facts.check import fold

WORD = re.compile(r"[a-z0-9]+")
SHINGLE = 5

Shingles = frozenset[tuple[str, ...]]


def normalize(text: str) -> str:
    return " ".join(WORD.findall(fold(text)))


def shingles(text: str) -> Shingles:
    words = normalize(text).split()
    if len(words) <= SHINGLE:
        return frozenset({tuple(words)})
    return frozenset(tuple(words[index : index + SHINGLE]) for index in range(len(words) - SHINGLE + 1))


def jaccard(left: Shingles, right: Shingles) -> float:
    union = len(left | right)
    return len(left & right) / union if union else 1.0


def containment(left: Shingles, right: Shingles) -> float:
    smaller = min(len(left), len(right))
    return len(left & right) / smaller if smaller else 1.0
