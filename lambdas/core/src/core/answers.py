from typing import Literal, get_args

from core.facts.catalog import LIST_JOIN
from core.facts.fallback import FIELD, TEMPLATES
from core.facts.parts import Part, Say
from core.facts.render import render_text
from core.facts.values import Count, Fact, FactIds, Label, Ledger
from core.policies import policy_facts
from core.router import FloorClass

SayKey = Literal["about_you", "no_rankings", "no_categories", "no_statements", "no_payments"]
SAY_KEYS: tuple[str, ...] = get_args(SayKey)

CONTACT = "bank_contact"
CONTACT_FIELDS = ("phone", "phone_schedule", "phone_abroad")

SAFETY: dict[FloorClass, dict[str, str]] = {
    "not_me": {
        "es": "Si no hiciste esa compra, protege tu tarjeta ahora: llama al banco al {c.phone} "
        "({c.phone_schedule}); desde el exterior, al {c.phone_abroad}. "
        "En esa llamada una persona del banco te ayuda a bloquearla.",
        "pt-BR": "Se você não fez essa compra, proteja seu cartão agora: ligue para o banco no {c.phone} "
        "({c.phone_schedule}); do exterior, no {c.phone_abroad}. "
        "Nessa ligação uma pessoa do banco ajuda você a bloqueá-lo.",
        "en": "If you did not make that purchase, protect your card now: call the bank at {c.phone} "
        "({c.phone_schedule}); from abroad, {c.phone_abroad}. "
        "On that call a person at the bank helps you block it.",
    },
    "lost_stolen": {
        "es": "Si perdiste tu tarjeta o te la robaron, protégela ahora: llama al banco al {c.phone} "
        "({c.phone_schedule}); desde el exterior, al {c.phone_abroad}. "
        "En esa llamada una persona del banco te ayuda a bloquearla.",
        "pt-BR": "Se você perdeu seu cartão ou ele foi roubado, proteja-o agora: ligue para o banco no "
        "{c.phone} ({c.phone_schedule}); do exterior, no {c.phone_abroad}. "
        "Nessa ligação uma pessoa do banco ajuda você a bloqueá-lo.",
        "en": "If your card was lost or stolen, protect it now: call the bank at {c.phone} "
        "({c.phone_schedule}); from abroad, {c.phone_abroad}. "
        "On that call a person at the bank helps you block it.",
    },
}

REFUSALS: dict[str, dict[str, str]] = {
    "no_rankings": {
        "es": "No hago rankings de tus gastos; sí puedo decirte cuánto gastaste en un comercio "
        "o en un periodo.",
        "pt-BR": "Não faço rankings dos seus gastos; posso dizer quanto você gastou em um estabelecimento "
        "ou em um período.",
        "en": "I do not rank your spending; I can tell you how much you spent at a merchant or in a period.",
    },
    "no_categories": {
        "es": "No agrupo tus gastos por categoría; sí puedo decirte cuánto gastaste en un comercio "
        "o en un periodo.",
        "pt-BR": "Não agrupo seus gastos por categoria; posso dizer quanto você gastou em um "
        "estabelecimento ou em um período.",
        "en": "I do not group your spending by category; I can tell you how much you spent at a merchant "
        "or in a period.",
    },
    "no_statements": {
        "es": "No tengo tus estados de cuenta; puedes pedirlos llamando al banco al {c.phone} "
        "({c.phone_schedule}).",
        "pt-BR": "Não tenho as suas faturas; você pode pedi-las ligando para o banco no {c.phone} "
        "({c.phone_schedule}).",
        "en": "I do not have your statements; you can ask for them by calling the bank at {c.phone} "
        "({c.phone_schedule}).",
    },
    "no_payments": {
        "es": "No veo pagos ni vencimientos de tu tarjeta; para eso llama al banco al {c.phone} "
        "({c.phone_schedule}).",
        "pt-BR": "Não vejo pagamentos nem vencimentos do seu cartão; para isso ligue para o banco no "
        "{c.phone} ({c.phone_schedule}).",
        "en": "I do not see payments or due dates of your card; for that call the bank at {c.phone} "
        "({c.phone_schedule}).",
    },
}

ABOUT_YOU = {
    "named": {
        "es": "Eres {u.given_name}, cliente de LATAM Bank en {u.country}.",
        "pt-BR": "Você é {u.given_name}, cliente do LATAM Bank ({u.country}).",
        "en": "You are {u.given_name}, a customer of LATAM Bank in {u.country}.",
    },
    "unnamed": {
        "es": "Eres cliente de LATAM Bank en {u.country}.",
        "pt-BR": "Você é cliente do LATAM Bank ({u.country}).",
        "en": "You are a customer of LATAM Bank in {u.country}.",
    },
    "cards": {"es": "Tienes {count}: ", "pt-BR": "Você tem {count}: ", "en": "You have {count}: "},
    "card": {"es": "la {type} {last4}", "pt-BR": "o {type} {last4}", "en": "the {type} card {last4}"},
    "no_cards": {
        "es": "Todavía no veo tarjetas en tu cuenta.",
        "pt-BR": "Ainda não vejo cartões na sua conta.",
        "en": "I do not see cards in your account yet.",
    },
}

CLOSED = {
    "recognized": {
        "es": "Gracias, lo anoto: reconoces este cargo y no volveré a preguntarte por él.",
        "pt-BR": "Obrigada, anotei: você reconhece esta cobrança e não vou perguntar de novo sobre ela.",
        "en": "Thank you, noted: you recognize this charge and I will not ask you about it again.",
    },
    "already": {
        "es": "Ya me habías respondido sobre este cargo, así que lo dejo como me dijiste.",
        "pt-BR": "Você já tinha me respondido sobre esta cobrança, então deixo como você me disse.",
        "en": "You had already answered me about this charge, so I keep it as you told me.",
    },
}

REMEMBERED = {
    "recognized_charge": {
        "es": "Reconociste tu cargo en {merchant} por {amount}, {date}.",
        "pt-BR": "Você reconheceu a cobrança em {merchant} de {amount}, {date}.",
        "en": "You recognized your charge at {merchant} for {amount}, {date}.",
    },
    "unrecognized_charge": {
        "es": "No reconociste tu cargo en {merchant} por {amount}, {date}.",
        "pt-BR": "Você não reconheceu a cobrança em {merchant} de {amount}, {date}.",
        "en": "You did not recognize your charge at {merchant} for {amount}, {date}.",
    },
    "recognized_merchant": {
        "es": "Reconociste varias compras tuyas en {merchant}.",
        "pt-BR": "Você reconheceu várias compras suas em {merchant}.",
        "en": "You recognized several of your purchases at {merchant}.",
    },
    "note": {"es": " Me dijiste: {note}.", "pt-BR": " Você me disse: {note}.", "en": " You told me: {note}."},
}

CUSTOMER = "customer"


def contact(ledger: Ledger) -> Fact:
    for fact in ledger.facts.values():
        if fact.kind == CONTACT:
            return fact
    facts = policy_facts()[ledger.country]
    return ledger.add(CONTACT, {name: facts.figure(f"channels.{name}") for name in CONTACT_FIELDS})


def safety(kind: FloorClass, ledger: Ledger, locale: str) -> list[Part]:
    return [Say(_bind(SAFETY[kind][locale], "c", contact(ledger)))]


def closed(outcome: str, ledger: Ledger, locale: str) -> list[Part]:
    if outcome == "missing":
        return [Say(TEMPLATES["unavailable"][locale])]
    return [Say(CLOSED[outcome][locale])]


def remembered(fact: Fact, ledger: Ledger, locale: str) -> str:
    kind = fact.fields.get("type")
    about = REMEMBERED[kind.value][locale] if isinstance(kind, Label) and kind.value in REMEMBERED else ""
    if any(name not in fact.fields for name in FIELD.findall(about)):
        about = ""
    note = REMEMBERED["note"][locale] if "note" in fact.fields else ""
    return render_text(_fields((about + note).strip(), fact), ledger, locale)


def say_key(key: str, ledger: Ledger, locale: str) -> list[Part]:
    if key == "about_you":
        return about_you(ledger, locale)
    return [Say(_bind(REFUSALS[key][locale], "c", contact(ledger)))]


def about_you(ledger: Ledger, locale: str) -> list[Part]:
    customer = next(fact for fact in ledger.facts.values() if fact.kind == CUSTOMER)
    who = ABOUT_YOU["named" if "given_name" in customer.fields else "unnamed"][locale]
    parts: list[Part] = [Say(_bind(who, "u", customer))]
    cards = next((fact for fact in ledger.facts.values() if fact.kind == "cards"), None)
    ids = cards.fields.get("ids") if cards else None
    count = cards.fields.get("count") if cards else None
    if cards is None or not isinstance(ids, FactIds) or not isinstance(count, Count) or not count.value:
        return [*parts, Say(ABOUT_YOU["no_cards"][locale])]
    listed = [_fields(ABOUT_YOU["card"][locale], ledger.facts[fact_id]) for fact_id in ids.values]
    joined = listed[0] if len(listed) == 1 else ", ".join(listed[:-1]) + LIST_JOIN[locale] + listed[-1]
    return [*parts, Say(_fields(ABOUT_YOU["cards"][locale], cards) + joined + ".")]


def _bind(template: str, alias: str, fact: Fact) -> str:
    return template.replace("{" + alias + ".", "{" + fact.id + ".")


def _fields(template: str, fact: Fact) -> str:
    for name in fact.fields:
        template = template.replace("{" + name + "}", "{" + fact.id + "." + name + "}")
    return template
