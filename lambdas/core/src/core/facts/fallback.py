import re
from collections.abc import Iterable, Sequence

from core.facts.catalog import LIST_JOIN
from core.facts.parts import Part, Say, View
from core.facts.targets import Unfit, view_items
from core.facts.values import POLICY_CHUNK, Count, Fact, FactIds, Ledger, Passage, Trace, Value

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
    "movements_card": {
        "es": "Encontré {count} en tu tarjeta {last4}, {period}.",
        "pt-BR": "Encontrei {count} no seu cartão {last4}, {period}.",
        "en": "I found {count} on your card {last4}, {period}.",
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
    "spend_card": {
        "es": "Gastaste {total} en {count} con tu tarjeta {last4}, {period}.",
        "pt-BR": "Você gastou {total} em {count} no seu cartão {last4}, {period}.",
        "en": "You spent {total} across {count} on your card {last4}, {period}.",
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
    "policies": {
        "es": "Esto dice el banco en «{title}»: {text}",
        "pt-BR": "É o que diz o banco em “{title}”: {text}",
        "en": "This is what the bank says in “{title}”: {text}",
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

LEADS = {
    "movements": {"es": "Encontré ", "pt-BR": "Encontrei ", "en": "I found "},
    "spend": {"es": "Gastaste ", "pt-BR": "Você gastou ", "en": "You spent "},
}

FIELD = re.compile(r"\{([a-z_][a-z0-9_.]*)\}")
MARKUP = re.compile(r"\*\*|__|`|^\s*(?:#+|[-*+]|\d+[.)])\s+", re.MULTILINE)
SPACES = re.compile(r"\s+")
_VIEWS = ("movements", "case", "charge")


def fallback(step_key: str, ledger: Ledger, locale: str, cited: Sequence[str] = ()) -> list[Part]:
    if step_key != "answer":
        return [Say(TEMPLATES["unavailable"][locale])]
    quoted = _quoted(ledger, cited, locale)
    groups: dict[str, list[tuple[str, Fact]]] = {}
    for fact in _distinct(ledger.facts.values()):
        key = _template_key(fact)
        template = _fitting(key, fact, locale)
        if key is None or template is None:
            continue
        group = groups.setdefault(key.removesuffix("_empty"), [])
        if FIELD.search(template) or all(existing != template for existing, _ in group):
            group.append((template, fact))
    if "policies" in groups:
        return [Say(_sentence(groups["policies"], "policies", locale))]
    if "spend" in groups or "spend_compare" in groups:
        groups.pop("movements", None)
    parts: list[Part] = [Say(_sentence(group, key, locale)) for key, group in groups.items()]
    if quoted is not None:
        parts.append(quoted)
    view = _view(ledger)
    if parts and view is not None:
        parts.append(view)
    return parts or [Say(TEMPLATES["unavailable"][locale])]


def _quoted(ledger: Ledger, cited: Sequence[str], locale: str) -> Say | None:
    chunks = {
        str(chunk_id.value): fact
        for fact in ledger.facts.values()
        if fact.kind == POLICY_CHUNK and isinstance(chunk_id := fact.fields.get("chunk_id"), Trace)
    }
    chosen = next((chunk for chunk in cited if chunk in chunks), next(iter(chunks), None))
    if chosen is None:
        return None
    fact = chunks[chosen]
    passage = fact.fields.get("text")
    if not isinstance(passage, Passage) or "title" not in fact.fields:
        return None
    text = plain(passage.value)
    template = TEMPLATES["policies"][locale].format(title=f"{{{fact.id}.title}}", text=text)
    return Say(f"{template} [p:{chosen}]")


def plain(markdown: str) -> str:
    return SPACES.sub(" ", MARKUP.sub("", markdown)).strip()


def _sentence(group: list[tuple[str, Fact]], key: str, locale: str) -> str:
    bound = [_bind(template, fact) for template, fact in group]
    lead = LEADS.get(key, {}).get(locale)
    if len(bound) == 1 or lead is None or not all(text.startswith(lead) for text in bound):
        return " ".join(bound)
    clauses = [text.removeprefix(lead).removesuffix(".") for text in bound]
    return lead + ", ".join(clauses[:-1]) + LIST_JOIN[locale] + clauses[-1] + "."


def _distinct(facts: Iterable[Fact]) -> list[Fact]:
    kept: list[Fact] = []
    seen: list[tuple[str, dict[str, Value]]] = []
    for fact in facts:
        shape: tuple[str, dict[str, Value]] = (
            fact.kind,
            {name: value for name, value in fact.fields.items() if not isinstance(value, FactIds)},
        )
        if shape not in seen:
            seen.append(shape)
            kept.append(fact)
    return kept


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
    for candidate in (f"{key}_card", key, f"{key}_bare"):
        template = TEMPLATES.get(candidate or "", {}).get(locale)
        if template is not None and all(name in fact.fields for name in FIELD.findall(template)):
            return template
    return None


def _bind(template: str, fact: Fact) -> str:
    return FIELD.sub(lambda match: f"{{{fact.id}.{match.group(1)}}}", template)


def _view(ledger: Ledger) -> View | None:
    for view in _VIEWS:
        for fact in reversed(ledger.facts.values()):
            if fact.kind != view:
                continue
            candidate = View(view, (fact.id,))
            try:
                view_items(candidate, ledger)
            except Unfit:
                continue
            return candidate
    return None
