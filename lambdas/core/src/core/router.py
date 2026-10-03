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


@dataclass(frozen=True)
class Route:
    mode: Literal["safety", "open_mode"]
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
