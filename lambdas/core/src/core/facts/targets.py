from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from core.facts.parts import Ask, View
from core.facts.values import Fact, FactIds, Json, Ledger, Merchant, Period, Ref, Refs, Trace

MAX_VIEW_ITEMS = 25
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
    if not items:
        raise Unfit("view_empty", view.facts[0] if view.facts else view.view)
    return items[:MAX_VIEW_ITEMS]


def ask_options(ask: Ask, ledger: Ledger) -> list[Option]:
    facts = [_known(ledger, fact_id, "ask_fact_unknown") for fact_id in ask.facts]
    if ask.ask == "which_one":
        return _which_one(facts, ledger)
    if ask.ask == "show":
        if len(facts) != 1:
            raise Unfit("ask_options_count", ask.facts[0] if ask.facts else ask.ask)
        option = show_option(facts[0], ledger)
        if option is None:
            raise Unfit("ask_fact_unfit", facts[0].id)
        return [option]
    raise Unfit("ask_not_allowed", ask.ask)


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


def _which_one(facts: list[Fact], ledger: Ledger) -> list[Option]:
    if not MIN_OPTIONS <= len(facts) <= MAX_OPTIONS:
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
    return options


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


VIEWS: dict[str, Callable[[list[Fact], Ledger], list[Json]]] = {
    "movements": _movements,
    "cards": _cards,
    "card": _one(_cards),
    "movement": _one(_single_transaction),
    "charge": _one(_of_kind("charge", _single_transaction)),
    "history": _history,
    "case": _cases,
}
