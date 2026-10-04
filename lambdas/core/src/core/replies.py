from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from core.countries import zone
from core.facts import Ask, Part, Say, View, render
from core.facts.catalog import LABELS
from core.facts.render import format_date, render_value
from core.facts.targets import CARD_CANDIDATES, Option, Unfit, ask_options, view_items
from core.facts.values import Count, Day, Fact, Instant, Json, Labels, Ledger, Ref, Text, Trace, Value

Source = Literal["composed", "repaired", "fallback", "safety", "say_key"]

HABIT = {
    "es": "Hiciste {count} antes en este comercio; lo típico es {amount}.",
    "pt-BR": "Você fez {count} antes neste estabelecimento; o valor típico é {amount}.",
    "en": "You made {count} here before; the typical amount is {amount}.",
}
HABIT_COUNT = {
    "es": "Hiciste {count} antes en este comercio.",
    "pt-BR": "Você fez {count} antes neste estabelecimento.",
    "en": "You made {count} here before.",
}
COMPARED = {
    "es": "Este cargo es {ratio}.",
    "pt-BR": "Esta cobrança é {ratio}.",
    "en": "This charge is {ratio}.",
}
CARD_OPTION = {"es": "Tarjeta {type} {last4}", "pt-BR": "Cartão {type} {last4}", "en": "{type} card {last4}"}
ASK_PROMPTS = {"which_one": {"es": "¿Cuál es?", "pt-BR": "Qual é?", "en": "Which one is it?"}}
SHOW_LABELS = {
    "movements": {
        "es": "Ver esos movimientos",
        "pt-BR": "Ver essas movimentações",
        "en": "See those transactions",
    },
    "charge": {"es": "Ver el cargo", "pt-BR": "Ver a cobrança", "en": "See the charge"},
}
OPTION_JOIN = " · "


@dataclass(frozen=True)
class Reply:
    parts: tuple[Json, ...]
    text: str
    facts: tuple[Json, ...]
    draft: tuple[Json, ...]
    source: Source


def compose(parts: Sequence[Part], ledger: Ledger, locale: str, source: Source) -> Reply:
    says = [part for part in parts if isinstance(part, Say)]
    rendered = render(says, ledger, locale)
    chunks = ledger.chunks()
    referenced: list[str] = []
    for said in rendered:
        referenced.extend(said["facts"])
        said["citations"] = [citation(chunk_id, ledger) for chunk_id in said["citations"]]
        referenced.extend(chunks[entry["chunk_id"]].id for entry in said["citations"])
    public: list[Json] = list(rendered)
    draft: list[Json] = [part.to_wire() for part in says]
    for part in parts:
        if isinstance(part, Say):
            continue
        try:
            if isinstance(part, View):
                public.append(view(part, ledger, locale))
                draft.append(part.to_wire())
            else:
                options = ask_options(part, ledger)
                public.append(ask(part, options, ledger, locale))
                draft.append(
                    {**part.to_wire(), "options": [{"id": item.id, "read": item.read} for item in options]}
                )
        except Unfit:
            continue
        referenced.extend(part.facts)
    return Reply(
        parts=tuple(public),
        text="\n\n".join(said["text"] for said in rendered),
        facts=tuple(ledger.payload(list(dict.fromkeys(referenced)))),
        draft=tuple(draft),
        source=source,
    )


def view(part: View, ledger: Ledger, locale: str) -> Json:
    wire: Json = {"type": "view", "view": part.view, "items": view_items(part, ledger)}
    facts = [ledger.facts[fact_id] for fact_id in part.facts]
    readings = READINGS.get(part.view, _none)(facts, ledger, locale)
    if readings:
        wire["readings"] = readings
    return wire


def ask(part: Ask, options: list[Option], ledger: Ledger, locale: str) -> Json:
    wire: Json = {
        "type": "ask",
        "ask": part.ask,
        "options": [{"id": item.id, "label": _label(part.ask, item, ledger, locale)} for item in options],
    }
    prompt = ASK_PROMPTS.get(part.ask, {}).get(locale)
    if prompt:
        wire["prompt"] = prompt
    return wire


def citation(chunk_id: str, ledger: Ledger) -> Json:
    fields = ledger.chunks()[chunk_id].fields
    title, page, url = fields.get("title"), fields.get("page"), fields.get("url")
    number = page.value if isinstance(page, Trace) else None
    return {
        "chunk_id": chunk_id,
        "title": title.value if isinstance(title, Text) else "",
        "page": int(number) if isinstance(number, str) and number.isdigit() else None,
        "url": url.value if isinstance(url, Trace) else None,
    }


def _label(kind: str, option: Option, ledger: Ledger, locale: str) -> str:
    if kind == "show":
        return SHOW_LABELS[option.id][locale]
    fields = option.fact.fields
    if option.fact.kind in CARD_CANDIDATES:
        fields = _card_fact(option, ledger).fields
        text = CARD_OPTION[locale].format(
            type=_rendered(fields.get("type"), ledger, locale),
            last4=_rendered(fields.get("last4"), ledger, locale),
        )
        return text[:1].upper() + text[1:]
    prefix = "charge." if option.fact.kind == "charge" else ""
    when = fields.get(prefix + "date")
    shown = [
        _rendered(fields.get(prefix + "merchant"), ledger, locale),
        _rendered(fields.get(prefix + "amount"), ledger, locale),
        _day(when, ledger, locale),
    ]
    return OPTION_JOIN.join(text for text in shown if text)


def _card_fact(option: Option, ledger: Ledger) -> Fact:
    wanted = Ref("card", option.id)
    cards = (
        fact
        for fact in ledger.facts.values()
        if fact.kind == "card" and fact.fields.get("card_ref") == wanted
    )
    return next(cards, option.fact)


def _day(value: Value | None, ledger: Ledger, locale: str) -> str:
    if isinstance(value, Instant):
        return format_date(value.value.astimezone(zone(ledger.country)).date(), ledger, locale, article=False)
    if isinstance(value, Day):
        return format_date(value.value, ledger, locale, article=False)
    return ""


def _rendered(value: Value | None, ledger: Ledger, locale: str) -> str:
    return render_value(value, ledger, locale) if value is not None else ""


def _none(facts: list[Fact], ledger: Ledger, locale: str) -> Json:
    return {}


def _movements(facts: list[Fact], ledger: Ledger, locale: str) -> Json:
    series = next((fact for fact in facts if fact.kind == "recurring_list"), None)
    count = series.fields.get("count") if series else None
    if count is not None:
        return {"kind": "series", "count": render_value(count, ledger, locale)}
    aggregate = next((fact for fact in facts if fact.kind == "movements"), None)
    if aggregate is None:
        return {}
    return {
        name: render_value(value, ledger, locale)
        for name in ("count", "period", "last4", "merchant")
        if (value := aggregate.fields.get(name)) is not None and not isinstance(value, Trace)
    }


def _history(facts: list[Fact], ledger: Ledger, locale: str) -> Json:
    fields = facts[0].fields
    return {
        name: render_value(value, ledger, locale)
        for name in ("merchant", "count", "typical_amount", "period")
        if (value := fields.get(name)) is not None and not isinstance(value, Trace)
    }


def _charge(facts: list[Fact], ledger: Ledger, locale: str) -> Json:
    fields = facts[0].fields
    readings: Json = {}
    explanation = fields.get("verdict.explanation")
    if explanation is not None:
        readings["explanation"] = render_value(explanation, ledger, locale)
    reasons = fields.get("verdict.reasons")
    if isinstance(reasons, Labels) and reasons.values:
        readings["reasons"] = [
            {"reason": reason, "text": LABELS["reason"][reason][locale]}
            for reason in reasons.values
            if reason in LABELS["reason"]
        ]
    count, amount = fields.get("habit.prior_count"), fields.get("habit.median_amount")
    if isinstance(count, Count) and count.value:
        template = HABIT[locale] if amount is not None else HABIT_COUNT[locale]
        readings["habit"] = template.format(
            count=render_value(count, ledger, locale), amount=_rendered(amount, ledger, locale)
        )
    ratio = fields.get("habit.ratio_to_typical")
    if ratio is not None:
        readings["compared"] = COMPARED[locale].format(ratio=render_value(ratio, ledger, locale))
    return readings


READINGS = {"movements": _movements, "history": _history, "charge": _charge}
