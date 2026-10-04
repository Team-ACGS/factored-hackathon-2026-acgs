import re
from dataclasses import dataclass
from functools import cache


@dataclass(frozen=True)
class Term:
    bank: str
    customer: tuple[str, ...]


GLOSSARY: dict[str, tuple[Term, ...]] = {
    "es": (Term("bloquear", ("cancelar", "anular", "dar de baja", "desactivar", "suspender", "congelar")),),
    "pt-BR": (Term("bloquear", ("cancelar", "anular", "desativar", "suspender", "congelar")),),
    "en": (Term("block", ("cancel", "deactivate", "suspend", "freeze", "lock")),),
}


def bank_terms(query: str, locale: str) -> str | None:
    mapped = query
    for term in GLOSSARY.get(locale, ()):
        mapped = _pattern(term, locale).sub(term.bank, mapped)
    return mapped if mapped != query else None


def prompt_lines() -> str:
    return "\n".join(
        f"- {locale}: {', '.join(term.customer)} -> {term.bank}"
        for locale, terms in GLOSSARY.items()
        for term in terms
    )


@cache
def _pattern(term: Term, locale: str) -> re.Pattern[str]:
    return re.compile(
        r"(?<!\w)(?:" + "|".join(_word(word, locale) for word in term.customer) + r")(?!\w)", re.IGNORECASE
    )


def _word(word: str, locale: str) -> str:
    words = word.split()
    if len(words) > 1:
        return r"\w+\s+" + r"\s+".join(map(re.escape, words[1:]))
    if locale == "en":
        return re.escape(word.removesuffix("e")) + r"\w*"
    return re.escape(word[:-2]) + r"\w*"
