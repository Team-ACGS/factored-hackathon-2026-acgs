import re
from dataclasses import dataclass
from typing import Literal

from core.facts.check import bounded, fold

FloorClass = Literal["not_me", "lost_stolen"]

FLOOR: dict[FloorClass, tuple[str, ...]] = {
    "not_me": (
        "no fui yo",
        "yo no fui",
        "no lo hice yo",
        "no hice esa compra",
        "no autorice",
        "nao fui eu",
        "eu nao fiz",
        "nao fiz essa compra",
        "nao autorizei",
        "wasn't me",
        "was not me",
        "i didn't make",
        "i did not make",
    ),
    "lost_stolen": (
        "me robaron",
        "perdi mi tarjeta",
        "perdi la tarjeta",
        "se me perdio la tarjeta",
        "se me perdio mi tarjeta",
        "me roubaram",
        "fui roubado",
        "fui roubada",
        "roubaram meu cartao",
        "roubaram o cartao",
        "roubaram o meu cartao",
        "perdi meu cartao",
        "perdi o cartao",
        "perdi o meu cartao",
        "stolen",
        "lost my card",
    ),
}

_SPACES = re.compile(r"\s+")
_PATTERNS = {kind: bounded(re.escape(phrase) for phrase in phrases) for kind, phrases in FLOOR.items()}


ShortAnswer = Literal["yes", "no"]

ANSWERS: dict[ShortAnswer, tuple[str, ...]] = {
    "yes": (
        "si",
        "si fui yo",
        "fui yo",
        "si lo reconozco",
        "lo reconozco",
        "si es mio",
        "es mio",
        "sim",
        "sim fui eu",
        "fui eu",
        "sim reconheco",
        "reconheco",
        "e meu",
        "yes",
        "yes it was me",
        "it was me",
        "i recognize it",
    ),
    "no": (
        "no",
        "no lo reconozco",
        "no la reconozco",
        "no es mio",
        "no fui yo",
        "nao",
        "nao reconheco",
        "nao e meu",
        "nao fui eu",
        "no i don't recognize it",
        "i don't recognize it",
        "it wasn't me",
    ),
}

_CLAUSE_END = re.compile(r"[,.;:!?\n]")
_OPENING = "¡\"'«“ "


@dataclass(frozen=True)
class Route:
    mode: Literal["safety", "open_mode", "choice", "topic", "story"]
    floor: FloorClass | None = None


def normalize(text: str) -> str:
    return _SPACES.sub(" ", fold(text)).strip()


def floor(text: str) -> FloorClass | None:
    normalized = normalize(text)
    for kind, pattern in _PATTERNS.items():
        if pattern.search(normalized):
            return kind
    return None


def route(text: str) -> Route:
    hit = floor(text)
    return Route("safety", hit) if hit else Route("open_mode")


def short_answer(text: str) -> tuple[ShortAnswer, str] | None:
    if text.lstrip().startswith("¿"):
        return None
    found: tuple[ShortAnswer, int, str] | None = None
    for end in [*_CLAUSE_END.finditer(text), None]:
        stop = end.start() if end else len(text)
        clause = normalize(_CLAUSE_END.sub(" ", text[:stop]).strip(_OPENING))
        answer = next((kind for kind, phrases in ANSWERS.items() if clause in phrases), None)
        if answer is not None:
            found = (answer, end.end() if end else stop, end.group(0) if end else "")
    if found is None or found[2] == "?":
        return None
    return found[0], text[found[1] :].strip()
