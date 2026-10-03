import re

from core.facts.parts import Part, Say, View
from core.facts.values import Count, Fact, FactIds, Ledger, Ref

FALLBACK_KEYS = ("answer", "unavailable")

TEMPLATES: dict[str, dict[str, str]] = {
    "unavailable": {
        "es": "No pude revisar eso ahora. Intenta de nuevo en un momento.",
        "pt-BR": "Não consegui verificar isso agora. Tente de novo em um momento.",
        "en": "I could not check that right now. Try again in a moment.",
    },
    "error": {
        "es": "No pude revisar una parte de tu información ahora.",
        "pt-BR": "Não consegui verificar uma parte das suas informações agora.",
        "en": "I could not check part of your information right now.",
    },
    "cards": {"es": "Tienes {count}.", "pt-BR": "Você tem {count}.", "en": "You have {count}."},
    "cards_empty": {
        "es": "Todavía no veo tarjetas en tu cuenta; termina la configuración para verlas.",
        "pt-BR": "Ainda não vejo cartões na sua conta; conclua a configuração para vê-los.",
        "en": "I do not see cards in your account yet; finish the setup to see them.",
    },
    "card": {
        "es": "Tu tarjeta {type} {last4} está {status}.",
        "pt-BR": "Seu cartão {type} {last4} está {status}.",
        "en": "Your {type} card {last4} is {status}.",
    },
    "movements": {
        "es": "Encontré {count}, {period}.",
        "pt-BR": "Encontrei {count}, {period}.",
        "en": "I found {count}, {period}.",
    },
    "movements_empty": {
        "es": "No encontré movimientos con ese filtro, {period}.",
        "pt-BR": "Não encontrei movimentações com esse filtro, {period}.",
        "en": "I found no transactions with that filter, {period}.",
    },
    "merchant_history": {
        "es": "En {merchant} tienes {count}; la última fue {last_date}.",
        "pt-BR": "Em {merchant} você tem {count}; a última foi {last_date}.",
        "en": "At {merchant} you have {count}; the last one was {last_date}.",
    },
    "merchant_history_empty": {
        "es": "No veo compras en {merchant} en tu historial reciente.",
        "pt-BR": "Não vejo compras em {merchant} no seu histórico recente.",
        "en": "I see no purchases at {merchant} in your recent history.",
    },
    "spend": {
        "es": "Gastaste {total} en {count}, {period}.",
        "pt-BR": "Você gastou {total} em {count}, {period}.",
        "en": "You spent {total} across {count}, {period}.",
    },
    "spend_compare": {
        "es": "Gastaste {total}, {period}, y {compare_total}, {compare_period}.",
        "pt-BR": "Você gastou {total}, {period}, e {compare_total}, {compare_period}.",
        "en": "You spent {total}, {period}, and {compare_total}, {compare_period}.",
    },
    "recurring": {
        "es": "{merchant}: cargo {cadence} de {typical_amount} en tu tarjeta {last4}.",
        "pt-BR": "{merchant}: cobrança {cadence} de {typical_amount} no seu cartão {last4}.",
        "en": "{merchant}: {cadence} charge of {typical_amount} on your card {last4}.",
    },
    "recurring_list_empty": {
        "es": "No veo cargos repetidos en tus tarjetas.",
        "pt-BR": "Não vejo cobranças repetidas nos seus cartões.",
        "en": "I see no repeated charges on your cards.",
    },
    "charge": {
        "es": "La compra en {charge.merchant} por {charge.amount} está {charge.status}.",
        "pt-BR": "A compra em {charge.merchant} de {charge.amount} está {charge.status}.",
        "en": "The purchase at {charge.merchant} for {charge.amount} is {charge.status}.",
    },
    "case": {
        "es": "Tu caso {case_id} ({type}) está {stage}.",
        "pt-BR": "O seu caso {case_id} ({type}) está {stage}.",
        "en": "Your case {case_id} ({type}) is {stage}.",
    },
    "cases_empty": {
        "es": "No tienes casos abiertos.",
        "pt-BR": "Você não tem casos abertos.",
        "en": "You have no open cases.",
    },
    "memory": {
        "es": "Me contaste: {note}.",
        "pt-BR": "Você me contou: {note}.",
        "en": "You told me: {note}.",
    },
    "memory_bare": {
        "es": "Tengo una nota tuya sobre tus cargos.",
        "pt-BR": "Tenho uma nota sua sobre as suas cobranças.",
        "en": "I have a note from you about your charges.",
    },
    "policies_empty": {
        "es": "No tengo información del banco sobre eso.",
        "pt-BR": "Não tenho informações do banco sobre isso.",
        "en": "I do not have the bank's information on that.",
    },
    "memories_empty": {
        "es": "Todavía no me has contado nada sobre tus cargos.",
        "pt-BR": "Você ainda não me contou nada sobre as suas cobranças.",
        "en": "You have not told me anything about your charges yet.",
    },
}

_FIELD = re.compile(r"\{([a-z_][a-z0-9_.]*)\}")
_VIEWS = {"movements": "movements", "cards": "cards"}


def fallback(step_key: str, ledger: Ledger, locale: str) -> list[Part]:
    if step_key != "answer":
        return [Say(TEMPLATES["unavailable"][locale])]
    parts: list[Part] = []
    for fact in ledger.facts.values():
        template = _fitting(_template_key(fact), fact, locale)
        if template is not None:
            parts.append(Say(_bind(template, fact)))
        view = _view(fact, ledger)
        if view is not None:
            parts.append(view)
    return parts or [Say(TEMPLATES["unavailable"][locale])]


def _template_key(fact: Fact) -> str | None:
    count = fact.fields.get("count")
    empty = isinstance(count, Count) and count.value == 0
    match fact.kind:
        case "error":
            return "error"
        case "cards" | "movements" | "recurring_list" | "cases" | "memories" | "policies" if empty:
            return f"{fact.kind}_empty"
        case "cards" | "movements":
            return fact.kind
        case "merchant_history":
            return "merchant_history_empty" if empty else "merchant_history"
        case "spend":
            return "spend_compare" if "compare_total" in fact.fields else "spend"
        case "card" | "recurring" | "charge" | "case" | "memory":
            return fact.kind
    return None


def _fitting(key: str | None, fact: Fact, locale: str) -> str | None:
    for candidate in (key, f"{key}_bare"):
        template = TEMPLATES.get(candidate or "", {}).get(locale)
        if template is not None and all(name in fact.fields for name in _FIELD.findall(template)):
            return template
    return None


def _bind(template: str, fact: Fact) -> str:
    return _FIELD.sub(lambda match: f"{{{fact.id}.{match.group(1)}}}", template)


def _view(fact: Fact, ledger: Ledger) -> View | None:
    view = _VIEWS.get(fact.kind)
    ids = fact.fields.get("ids")
    if view is None or not isinstance(ids, FactIds):
        return None
    refs = []
    for fact_id in ids.values:
        row = ledger.get(fact_id)
        ref = None if row is None else row.fields.get("transaction_ref", row.fields.get("card_ref"))
        if isinstance(ref, Ref):
            refs.append(ref.value)
    return View(view, tuple(refs)) if refs else None
