from dataclasses import dataclass, field
from typing import Any, Literal

from core.facts.catalog import LIST_JOIN
from core.facts.parts import Ask
from core.facts.render import render_text
from core.facts.values import Fact, Labels, Ledger, Status
from core.ids import format_instant
from core.receipts import bind

Kind = Literal["fraud", "claim", "service"]
BlockOutcome = Literal["blocked", "blocked_before", "unconfirmed"]

REQUESTS = {
    "not_me": {
        "es": "Dice que no hizo este cargo.",
        "pt-BR": "Diz que não fez esta cobrança.",
        "en": "Says they did not make this charge.",
    },
    "unrecognized": {
        "es": "Dice que no reconoce este cargo.",
        "pt-BR": "Diz que não reconhece esta cobrança.",
        "en": "Says they do not recognize this charge.",
    },
    "lost": {
        "es": "Dice que perdió su tarjeta o se la robaron.",
        "pt-BR": "Diz que perdeu o cartão ou que ele foi roubado.",
        "en": "Says their card was lost or stolen.",
    },
    "claim": {
        "es": "Dice que no reconoce este cargo y que tiene su tarjeta.",
        "pt-BR": "Diz que não reconhece esta cobrança e que está com o cartão.",
        "en": "Says they do not recognize this charge and that they have their card.",
    },
    "unblock": {
        "es": "Pide desbloquear una tarjeta.",
        "pt-BR": "Pede para desbloquear um cartão.",
        "en": "Asks to unblock a card.",
    },
    "refund": {
        "es": "Pregunta por la devolución de su dinero.",
        "pt-BR": "Pergunta pela devolução do seu dinheiro.",
        "en": "Asks about getting their money back.",
    },
    "human": {
        "es": "Pide hablar con una persona.",
        "pt-BR": "Pede para falar com uma pessoa.",
        "en": "Asks to talk to a person.",
    },
}
REQUESTS["other"] = REQUESTS["human"]

POINTS = {
    "charge": {
        "es": "Cargo en {c.charge.merchant} por {c.charge.amount}, {c.charge.date}, "
        "con la tarjeta {c.card.last4}.",
        "pt-BR": "Cobrança em {c.charge.merchant} de {c.charge.amount}, {c.charge.date}, "
        "no cartão {c.card.last4}.",
        "en": "Charge at {c.charge.merchant} for {c.charge.amount}, {c.charge.date}, on card {c.card.last4}.",
    },
    "card": {"es": "Tarjeta {k.last4}.", "pt-BR": "Cartão {k.last4}.", "en": "Card {k.last4}."},
    "reasons": {
        "es": "Lo que notó el banco: {reasons}.",
        "pt-BR": "O que o banco notou: {reasons}.",
        "en": "What the bank noticed: {reasons}.",
    },
    "note": {
        "es": "Sus palabras: {c.memory.note}.",
        "pt-BR": "Disse: {c.memory.note}.",
        "en": "In their words: {c.memory.note}.",
    },
    "blocked": {
        "es": "Tarjeta {k.last4} bloqueada con su confirmación y verificada en la cuenta.",
        "pt-BR": "Cartão {k.last4} bloqueado com confirmação e verificado na conta.",
        "en": "Card {k.last4} blocked with their confirmation and checked in the account.",
    },
    "blocked_before": {
        "es": "La tarjeta {k.last4} ya estaba bloqueada; no se volvió a bloquear.",
        "pt-BR": "O cartão {k.last4} já estava bloqueado; não foi bloqueado de novo.",
        "en": "Card {k.last4} was already blocked; it was not blocked again.",
    },
    "unconfirmed": {
        "es": "El bloqueo de la tarjeta {k.last4} no se pudo confirmar.",
        "pt-BR": "O bloqueio do cartão {k.last4} não pôde ser confirmado.",
        "en": "The block of card {k.last4} could not be confirmed.",
    },
}

REASONS = {
    "score_high": {
        "es": "el sistema de alertas del banco emitió una alerta",
        "pt-BR": "o sistema de alertas do banco emitiu um alerta",
        "en": "the bank's alert system raised an alert",
    },
    "foreign_country": {
        "es": "es en otro país",
        "pt-BR": "é em outro país",
        "en": "it is in another country",
    },
    "unusual_channel": {
        "es": "es por un canal que no suele usar",
        "pt-BR": "é por um canal que não costuma usar",
        "en": "it is through a channel they do not usually use",
    },
    "new_merchant": {
        "es": "es su primera compra en este comercio",
        "pt-BR": "é a primeira compra nesse estabelecimento",
        "en": "it is their first purchase at this merchant",
    },
    "several_unrecognized": {
        "es": "hay varios cargos que no reconoce",
        "pt-BR": "há várias cobranças que não reconhece",
        "en": "there are several charges they do not recognize",
    },
}

ABOUT = {
    "es": "sobre su caso {s.case_id}.",
    "pt-BR": "sobre o caso {s.case_id}.",
    "en": "about their case {s.case_id}.",
}

QUESTIONS = {
    "fraud": {
        "es": "Pregunta abierta: ¿tenía la tarjeta consigo cuando se hizo el cargo?",
        "pt-BR": "Pergunta em aberto: estava com o cartão quando a cobrança foi feita?",
        "en": "Open question: did they have the card with them when the charge was made?",
    },
    "lost": {
        "es": "Pregunta abierta: ¿cuándo y dónde perdió la tarjeta?",
        "pt-BR": "Pergunta em aberto: quando e onde o cartão foi perdido?",
        "en": "Open question: when and where was the card lost?",
    },
    "claim": {
        "es": "Pregunta abierta: ¿qué pasó con esta compra?",
        "pt-BR": "Pergunta em aberto: o que aconteceu com esta compra?",
        "en": "Open question: what happened with this purchase?",
    },
    "unblock": {
        "es": "Pregunta abierta: ¿qué tarjeta quiere desbloquear y por qué?",
        "pt-BR": "Pergunta em aberto: qual cartão quer desbloquear e por quê?",
        "en": "Open question: which card do they want unblocked, and why?",
    },
    "refund": {
        "es": "Pregunta abierta: ¿de qué cargo o caso espera la devolución?",
        "pt-BR": "Pergunta em aberto: de qual cobrança ou caso espera a devolução?",
        "en": "Open question: which charge or case do they expect money back from?",
    },
    "service": {
        "es": "Pregunta abierta: ¿en qué necesita ayuda?",
        "pt-BR": "Pergunta em aberto: com o que precisa de ajuda?",
        "en": "Open question: what do they need help with?",
    },
}


@dataclass(frozen=True)
class Package:
    kind: Kind
    request: str
    case: Fact | None
    charge: Fact | None = None
    card: Fact | None = None
    block: BlockOutcome | None = None
    evidence: dict[str, str] = field(default_factory=dict)
    about: Fact | None = None

    def facts(self) -> list[str]:
        return [fact.id for fact in (self.charge, self.card, self.case) if fact is not None]


def points(package: Package, locale: str) -> list[str]:
    request = REQUESTS[package.request][locale]
    if package.about is not None:
        request = request.removesuffix(".") + ", " + bind(ABOUT[locale], s=package.about)
    found = [request]
    charge, card = package.charge, package.card
    if charge is not None:
        found.append(bind(POINTS["charge"][locale], c=charge))
        reasons = charge.fields.get("verdict.reasons")
        known = (
            [REASONS[reason][locale] for reason in reasons.values if reason in REASONS]
            if isinstance(reasons, Labels)
            else []
        )
        if known:
            joined = known[0] if len(known) == 1 else ", ".join(known[:-1]) + LIST_JOIN[locale] + known[-1]
            found.append(POINTS["reasons"][locale].format(reasons=joined))
        if "memory.note" in charge.fields:
            found.append(bind(POINTS["note"][locale], c=charge))
    elif card is not None:
        found.append(bind(POINTS["card"][locale], k=card))
    if package.block is not None and card is not None:
        found.append(bind(POINTS[package.block][locale], k=card))
    if package.kind != "service" or (package.about is None and package.charge is None):
        found.append(QUESTIONS[_question(package)][locale])
    return found


def handoff_points(subjects: list[Fact], asked: Ask | None, ledger: Ledger, locale: str) -> list[str]:
    target = (asked.target if asked else None) or {}
    subject = subjects[0] if subjects else None
    charge = subject if subject is not None and subject.kind == "charge" else None
    card = subject if subject is not None and subject.kind == "card" else _card_of(charge, ledger)
    fraud = target.get("area") == "fraud"
    reason = str(target.get("reason") or "")
    if fraud:
        request = "not_me" if charge is not None else "lost"
    else:
        request = reason if reason in ("unblock", "refund", "human") else "other"
    blocked = card is not None and card.fields.get("status") == Status("card", "Blocked")
    block: BlockOutcome | None = "blocked_before" if fraud and blocked else None
    about = subject if subject is not None and subject.kind == "case" else None
    preview = Package("fraud" if fraud else "service", request, None, charge, card, block, about=about)
    shown = []
    for point in points(preview, locale):
        try:
            shown.append(render_text(point, ledger, locale))
        except KeyError:
            continue
    return shown


def _card_of(charge: Fact | None, ledger: Ledger) -> Fact | None:
    wanted = charge.fields.get("charge.card_ref") if charge else None
    cards = [
        fact
        for fact in ledger.facts.values()
        if fact.kind == "card" and fact.fields.get("card_ref") == wanted
    ]
    return cards[-1] if wanted and cards else None


def summary_template(package: Package, locale: str) -> str:
    return " ".join(points(package, locale)[:-1])


def rendered(texts: list[str], ledger: Ledger, locale: str) -> list[str]:
    return [render_text(text, ledger, locale) for text in texts]


def summary_row(text: str, points: list[str], locale: str, source: str, now: Any) -> dict[str, Any]:
    return {
        "summary": text,
        "summary_points": points,
        "summary_language": locale,
        "summary_generated_at": format_instant(now),
        "summary_source": source,
    }


def _question(package: Package) -> str:
    if package.kind == "fraud":
        return "fraud" if package.charge is not None else "lost"
    if package.kind == "claim":
        return "claim"
    return package.request if package.request in ("unblock", "refund") else "service"
