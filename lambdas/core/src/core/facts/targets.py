from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from core.facts.parts import Ask, Part, View
from core.facts.values import (
    Count,
    Fact,
    FactIds,
    Flag,
    Json,
    Labels,
    Ledger,
    Merchant,
    Period,
    Ref,
    Refs,
    Trace,
)

MAX_VIEW_ITEMS = 25
SHOWN_ROWS = 5
MIN_OPTIONS = 2
MAX_OPTIONS = 5
SHOW_LIMIT = 25

TRANSACTION_REF = {
    "movement": "transaction_ref",
    "similar": "transaction_ref",
    "charge": "charge.transaction_ref",
}
CARD_REF = {"card": "card_ref", "movement": "card_ref", "charge": "charge.card_ref", "recurring": "card_ref"}
LISTS = {"movements", "cards", "recurring_list", "cases"}
CARD_CANDIDATES = ("card", "movements", "spend")
ANSWER_OPTIONS = {
    "recognize_charge": ("yes", "no"),
    "was_it_you": ("yes", "no", "why"),
    "have_card": ("yes", "no"),
    "block_card": ("yes", "no"),
    "open_claim": ("yes", "no"),
    "talk_to_person": ("yes", "no"),
}
CHARGE_ASKS = frozenset({"recognize_charge", "was_it_you", "have_card", "open_claim"})
HANDOFF = "handoff"
PERSON = "talk_to_person"
ASK_VIEWS: dict[str, tuple[str, ...]] = {
    "which_one": ("movements", "cards", "history"),
    "recognize_charge": ("charge",),
    "was_it_you": ("charge",),
    "have_card": ("charge",),
    "open_claim": ("charge",),
    "block_card": ("card",),
    PERSON: (HANDOFF,),
}
SUBJECTS = frozenset({"charge", "card", "case", "movement"})


class Unfit(ValueError):
    def __init__(self, code: str, fact_id: str) -> None:
        super().__init__(code)
        self.code = code
        self.fact_id = fact_id


@dataclass(frozen=True)
class Option:
    id: str
    fact: Fact
    read: Json = field(default_factory=dict)


def view_items(view: View, ledger: Ledger) -> list[Json]:
    resolve = VIEWS.get(view.view)
    if resolve is None:
        raise Unfit("view_unknown", view.view)
    facts = [_known(ledger, fact_id, "view_fact_unknown") for fact_id in view.facts]
    items = _unique(resolve(facts, ledger))
    if not items and view.view != HANDOFF:
        raise Unfit("view_empty", view.facts[0] if view.facts else view.view)
    return items[:MAX_VIEW_ITEMS]


def with_views(parts: list[Part], ledger: Ledger) -> list[Part]:
    parts = code_views(parts, ledger)
    asked = next((part for part in parts if isinstance(part, Ask)), None)
    if asked is None or not missing_views(parts):
        return parts
    subject = ledger.get(asked.facts[0]) if asked.facts else None
    if asked.ask in CHARGE_ASKS and subject is not None and subject.kind == "charge":
        needed = View("charge", (subject.id,))
    elif asked.ask == "block_card" and subject is not None:
        card = subject if subject.kind == "card" else _card_of(subject, ledger)
        if card is None:
            return parts
        needed = View("card", (card.id,))
    else:
        return parts
    kept = [part for part in parts if not isinstance(part, View | Ask)]
    return [*kept, needed, *(part for part in parts if isinstance(part, Ask))]


def _card_of(fact: Fact, ledger: Ledger) -> Fact | None:
    wanted = fact.fields.get(CARD_REF.get(fact.kind, ""))
    cards = [
        found
        for found in ledger.facts.values()
        if found.kind == "card" and found.fields.get("card_ref") == wanted
    ]
    return cards[-1] if wanted is not None and cards else None


def code_views(parts: list[Part], ledger: Ledger) -> list[Part]:
    asked = next((part for part in parts if isinstance(part, Ask)), None)
    views = [part for part in parts if isinstance(part, View)]
    if asked is None:
        return parts
    if asked.ask == PERSON and not any(view.view == HANDOFF for view in views):
        named = ledger.get(asked.facts[0]) if asked.facts else None
        subject = (named.id,) if named is not None and named.kind in SUBJECTS else _subject_of(views, ledger)
        kept = [part for part in parts if not isinstance(part, View | Ask)]
        return [*kept, View(HANDOFF, subject), Ask(PERSON, subject, target=asked.target)]
    if asked.ask == "which_one" and not views:
        try:
            options = ask_options(asked, ledger)
        except Unfit:
            return parts
        kind = "cards" if options and options[0].read.get("tool") == "card_status" else "movements"
        listed = View(kind, asked.facts)
        try:
            view_items(listed, ledger)
        except Unfit:
            return parts
        return [*parts[: parts.index(asked)], listed, *parts[parts.index(asked) :]]
    return parts


def missing_views(parts: list[Part]) -> list[Ask]:
    shown = {part.view for part in parts if isinstance(part, View)}
    return [
        part
        for part in parts
        if isinstance(part, Ask) and part.ask in ASK_VIEWS and not shown & set(ASK_VIEWS[part.ask])
    ]


def _subject_of(views: list[View], ledger: Ledger) -> tuple[str, ...]:
    facts = [fact_id for view in views for fact_id in view.facts]
    if len(facts) == 1 and (fact := ledger.get(facts[0])) is not None and fact.kind in SUBJECTS:
        return (fact.id,)
    return ()


def ask_options(ask: Ask, ledger: Ledger) -> list[Option]:
    facts = [_known(ledger, fact_id, "ask_fact_unknown") for fact_id in ask.facts]
    if ask.ask == "which_one":
        return _which_one(facts, ledger, story=bool(ask.target))
    if ask.ask == "show":
        if len(facts) != 1:
            raise Unfit("ask_options_count", ask.facts[0] if ask.facts else ask.ask)
        option = show_option(facts[0], ledger)
        if option is None:
            raise Unfit("ask_fact_unfit", facts[0].id)
        return [option]
    if ask.ask in CHARGE_ASKS:
        if len(facts) != 1 or facts[0].kind != "charge" or _transaction(facts[0], ledger) is None:
            raise Unfit("ask_fact_unfit", facts[0].id if facts else ask.ask)
        return [Option(answer, facts[0]) for answer in ANSWER_OPTIONS[ask.ask]]
    if ask.ask == "block_card":
        if len(facts) != 1 or _subject(facts[0], ledger) is None:
            raise Unfit("ask_fact_unfit", facts[0].id if facts else ask.ask)
        return [Option(answer, facts[0]) for answer in ANSWER_OPTIONS[ask.ask]]
    if ask.ask == "talk_to_person":
        if not ask.target and len(facts) != 1:
            raise Unfit("ask_options_count", facts[0].id if facts else ask.ask)
        subject = facts[0] if facts else ledger.facts[next(iter(ledger.facts))]
        return [Option(answer, subject) for answer in ANSWER_OPTIONS[ask.ask]]
    raise Unfit("ask_not_allowed", ask.ask)


def ask_target(ask: Ask, ledger: Ledger) -> Json | None:
    if ask.ask in CHARGE_ASKS:
        return _transaction(ledger.facts[ask.facts[0]], ledger)
    if ask.ask == "block_card":
        return _subject(ledger.facts[ask.facts[0]], ledger)
    if ask.ask == "talk_to_person":
        fact = ledger.facts[ask.facts[0]] if len(ask.facts) == 1 else None
        case = _ref(fact, "case_ref") if fact is not None and fact.kind == "case" else None
        subject = {"complaint_id": case} if case else (_subject(fact, ledger) if fact is not None else None)
        return {"reason": "other", "area": "service", **(subject or {}), **(ask.target or {})}
    return None


def _subject(fact: Fact, ledger: Ledger) -> Json | None:
    transaction = _transaction(fact, ledger)
    if transaction is not None:
        return transaction
    card = _ref(fact, "card_ref") if fact.kind == "card" else None
    return {"product_id": card} if card else None


def recent_pick(ask: Ask, ledger: Ledger) -> bool:
    if ask.ask != "which_one":
        return False
    return _newest_of_recent([ledger.facts[fact_id] for fact_id in ask.facts], ledger)


def recognizable(fact: Fact) -> bool:
    reasons = fact.fields.get("verdict.reasons")
    flagged = isinstance(reasons, Labels) and "score_high" in reasons.values
    return fact.kind == "charge" and "memory.type" not in fact.fields and not flagged


def candidate(fact: Fact, ledger: Ledger) -> tuple[str, Json] | None:
    transaction = _transaction(fact, ledger)
    if transaction is not None:
        return "transaction", transaction
    if fact.kind in CARD_CANDIDATES:
        card = _ref(fact, "card_ref")
        return ("card", {"product_id": card}) if card else None
    return None


def show_option(fact: Fact, ledger: Ledger) -> Option | None:
    match fact.kind:
        case "spend":
            return _show_spend(fact)
        case "case":
            transaction = _ref(fact, "transaction_ref")
            if transaction is None:
                return None
            return Option("charge", fact, {"tool": "charge_facts", "args": {"transaction_ref": transaction}})
        case "card":
            card = _ref(fact, "card_ref")
            if card is None:
                return None
            args = {"card_ref": card, "limit": SHOW_LIMIT}
            return Option("movements", fact, {"tool": "search_movements", "args": args})
    return None


def _which_one(facts: list[Fact], ledger: Ledger, story: bool = False) -> list[Option]:
    if not (1 if story else MIN_OPTIONS) <= len(facts) <= MAX_OPTIONS:
        raise Unfit("ask_options_count", facts[0].id if facts else "which_one")
    options: list[Option] = []
    kinds: set[str] = set()
    for fact in facts:
        found = candidate(fact, ledger)
        if found is None:
            raise Unfit("ask_fact_unfit", fact.id)
        kind, item = found
        kinds.add(kind)
        if kind == "transaction":
            option = Option(item["transaction_id"], fact, _read("charge_facts", "transaction_ref", item))
        else:
            option = Option(item["product_id"], fact, _read("card_status", "card_ref", item))
        if any(existing.id == option.id for existing in options):
            raise Unfit("ask_options_repeated", fact.id)
        options.append(option)
    if len(kinds) > 1:
        raise Unfit("ask_options_mixed", facts[-1].id)
    if story or _newest_of_recent(facts, ledger):
        return options
    for fact in facts:
        if _matched(fact, ledger) > len(options):
            raise Unfit("ask_options_partial", fact.id)
    return options


def newest_page(fact: Fact) -> tuple[str, ...] | None:
    ids = fact.fields.get("ids")
    if fact.kind == "movements" and fact.fields.get("recent") == Flag(True) and isinstance(ids, FactIds):
        return ids.values[:MAX_OPTIONS]
    return None


def _newest_of_recent(facts: list[Fact], ledger: Ledger) -> bool:
    chosen = tuple(fact.id for fact in facts)
    return any(newest_page(fact) == chosen for fact in ledger.facts.values())


def _matched(row: Fact, ledger: Ledger) -> int:
    for fact in ledger.facts.values():
        ids, count = fact.fields.get("ids"), fact.fields.get("count")
        if (
            fact.kind == "movements"
            and isinstance(ids, FactIds)
            and row.id in ids.values
            and isinstance(count, Count)
        ):
            return count.value
    return 0


def _read(tool: str, argument: str, item: Json) -> Json:
    key = "transaction_id" if argument == "transaction_ref" else "product_id"
    return {"tool": tool, "args": {argument: item[key]}}


def _show_spend(fact: Fact) -> Option | None:
    periods = [
        value for name in ("period", "compare_period") if isinstance(value := fact.fields.get(name), Period)
    ]
    if not periods:
        return None
    args: Json = {
        "date_from": min(period.start for period in periods).isoformat(),
        "date_to": max(period.end for period in periods).isoformat(),
        "limit": SHOW_LIMIT,
    }
    merchant = fact.fields.get("merchant")
    if isinstance(merchant, Merchant | Trace) and isinstance(merchant.value, str):
        args["merchant"] = merchant.value
    card = _ref(fact, "card_ref")
    if card:
        args["card_ref"] = card
    return Option("movements", fact, {"tool": "search_movements", "args": args})


def _known(ledger: Ledger, fact_id: str, code: str) -> Fact:
    fact = ledger.get(fact_id)
    if fact is None or fact.kind == "error":
        raise Unfit(code, fact_id)
    return fact


def _ref(fact: Fact, name: str) -> str | None:
    value = fact.fields.get(name)
    return value.value if isinstance(value, Ref) else None


def _expanded(facts: Iterable[Fact], ledger: Ledger) -> list[Fact]:
    found: list[Fact] = []
    for fact in facts:
        ids = fact.fields.get("ids")
        if fact.kind in LISTS and isinstance(ids, FactIds):
            found.extend(_expanded((ledger.facts[fact_id] for fact_id in ids.values), ledger))
        else:
            found.append(fact)
    return found


def _transaction(fact: Fact, ledger: Ledger) -> Json | None:
    name = TRANSACTION_REF.get(fact.kind)
    transaction = _ref(fact, name) if name else None
    if transaction is None:
        return None
    card = _ref(fact, CARD_REF.get(fact.kind, "")) or ledger.owners.get(transaction)
    return {"product_id": card, "transaction_id": transaction} if card else None


def _transactions(fact: Fact, ledger: Ledger) -> list[Json]:
    single = _transaction(fact, ledger)
    if single is not None:
        return [single]
    if fact.kind not in ("recurring", "merchant_history"):
        raise Unfit("view_fact_unfit", fact.id)
    refs = fact.fields.get("ids")
    return [
        {"product_id": ledger.owners[transaction], "transaction_id": transaction}
        for transaction in (reversed(refs.values) if isinstance(refs, Refs) else ())
        if transaction in ledger.owners
    ]


def _movements(facts: list[Fact], ledger: Ledger) -> list[Json]:
    return [item for fact in _expanded(facts, ledger) for item in _transactions(fact, ledger)]


def _cards(facts: list[Fact], ledger: Ledger) -> list[Json]:
    items = []
    for fact in _expanded(facts, ledger):
        card = _ref(fact, CARD_REF.get(fact.kind, ""))
        if card is None:
            raise Unfit("view_fact_unfit", fact.id)
        items.append({"product_id": card})
    return items


def _one(resolve: Callable[[list[Fact], Ledger], list[Json]]) -> Callable[[list[Fact], Ledger], list[Json]]:
    def single(facts: list[Fact], ledger: Ledger) -> list[Json]:
        items = _unique(resolve(facts, ledger))
        if len(items) > 1:
            raise Unfit("view_fact_unfit", facts[-1].id)
        return items

    return single


def _of_kind(kind: str, resolve: Callable[[list[Fact], Ledger], list[Json]]) -> Callable[..., list[Json]]:
    def only(facts: list[Fact], ledger: Ledger) -> list[Json]:
        for fact in facts:
            if fact.kind != kind:
                raise Unfit("view_fact_unfit", fact.id)
        return resolve(facts, ledger)

    return only


def _single_transaction(facts: list[Fact], ledger: Ledger) -> list[Json]:
    items = []
    for fact in facts:
        item = _transaction(fact, ledger)
        if item is None:
            raise Unfit("view_fact_unfit", fact.id)
        items.append(item)
    return items


def _history(facts: list[Fact], ledger: Ledger) -> list[Json]:
    if len(facts) != 1 or facts[0].kind != "merchant_history":
        raise Unfit("view_fact_unfit", facts[-1].id if facts else "history")
    return _transactions(facts[0], ledger)


def _cases(facts: list[Fact], ledger: Ledger) -> list[Json]:
    items = []
    for fact in _expanded(facts, ledger):
        case = _ref(fact, "case_ref") if fact.kind == "case" else None
        if case is None:
            raise Unfit("view_fact_unfit", fact.id)
        items.append({"complaint_id": case})
    return items


def _unique(items: list[Json]) -> list[Json]:
    seen: list[Json] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen


def _handoff(facts: list[Fact], ledger: Ledger) -> list[Json]:
    if len(facts) > 1:
        raise Unfit("view_fact_unfit", facts[-1].id)
    if not facts or facts[0].kind not in SUBJECTS:
        return []
    [fact] = facts
    if fact.kind == "case":
        return _cases(facts, ledger)
    if fact.kind == "card":
        return _cards(facts, ledger)
    return _single_transaction(facts, ledger)


VIEWS: dict[str, Callable[[list[Fact], Ledger], list[Json]]] = {
    "movements": _movements,
    "cards": _cards,
    "card": _one(_cards),
    "movement": _one(_single_transaction),
    "charge": _one(_of_kind("charge", _single_transaction)),
    "history": _history,
    "case": _cases,
    HANDOFF: _handoff,
}
