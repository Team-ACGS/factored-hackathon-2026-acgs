"""Deterministic text understanding for the turn.

No LLM call lives here on purpose: intent detection and yes/no polarity are
cheap enough to be plain rules. This mirrors the *idea* of apps/customer's
``src/clara/chat/lexicon.ts`` (``intentOf``, ``polarity``), but the two are
independent implementations; nothing is shared between front and back end.
"""

from __future__ import annotations

import re

from core.facts.check import fold
from core.facts.lexicon import CATALOG_MERCHANTS

YES_WORDS = re.compile(r"\b(si|sí|yes|sim|claro|dale|ok|okay|correcto|confirmo|afirmativo|isso)\b")
NO_WORDS = re.compile(r"\b(no|nao|não|nope|cancela|cancelar|negativo)\b")

# Order matters: the first matching intent wins, so the more specific phrases
# (lost/stolen card, "I don't recognize this charge") come before the broad
# ones ("balance", "policy").
INTENT_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "block_card",
        (
            "perdi",
            "perdí",
            "robaron",
            "me robaron",
            "roubaram",
            "roubada",
            "lost my card",
            "stolen",
            "bloquea mi tarjeta",
            "bloquear mi tarjeta",
            "block my card",
        ),
    ),
    (
        "claim",
        (
            "no reconozco",
            "não reconheço",
            "nao reconheço",
            "don't recognize",
            "do not recognize",
            "quiero reclamar",
            "quero reclamar",
            "disputar",
            "dispute this",
        ),
    ),
    (
        "cards",
        (
            "mis tarjetas",
            "meus cartões",
            "meus cartoes",
            "my cards",
            "saldo",
            "balance",
            "limite",
            "límite",
        ),
    ),
    (
        "case_status",
        (
            "estado de mi reclamo",
            "estado del caso",
            "status do meu caso",
            "claim status",
            "mi reclamo",
        ),
    ),
    (
        "policies",
        ("plazo", "política", "politica", "tarifa", "fee", "deadline", "policy", "legal"),
    ),
)


def intent_of(text: str) -> str:
    """A closed set of intents, picked by keyword, never by an LLM.

    Falls back to "movements" (look for a mentioned charge), the same
    catch-all the mock engine uses for text it cannot otherwise classify.
    """
    folded = fold(text)
    for intent, keywords in INTENT_KEYWORDS:
        if any(fold(keyword) in folded for keyword in keywords):
            return intent
    return "movements"


def polarity(text: str) -> bool | None:
    """A yes/no reading of a short reply, or None when it is ambiguous."""
    folded = fold(text.strip())
    if NO_WORDS.search(folded):
        return False
    if YES_WORDS.search(folded):
        return True
    return None


def mentioned_merchant(text: str) -> str | None:
    """A deterministic slot: a known merchant name mentioned in free text.

    Reuses the same merchant catalog `core.facts.check` already uses to keep
    composed answers grounded, instead of inventing a second list.
    """
    folded = fold(text)
    for merchant in sorted(CATALOG_MERCHANTS, key=len, reverse=True):
        if fold(merchant) in folded:
            return merchant
    return None