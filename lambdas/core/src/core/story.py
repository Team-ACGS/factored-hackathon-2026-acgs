from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from core import answers, rules
from core.access import customer_session
from core.accounts import BLOCKED, Accounts
from core.cases import Cases
from core.facts import fallback
from core.facts.parts import Ask, Part, View
from core.facts.values import Fact, Json, Ledger, Ref, Status
from core.handoff import BlockOutcome, Kind, Package, points, rendered, summary_row, summary_template
from core.ids import format_instant
from core.messaging import Message
from core.receipts import fixed, template
from core.rules import Answer, Choice, OpenAsk, Target
from core.tools import ToolContext, call
from core.tools.cases import case_fields

SERVICE = "chatbot"


@dataclass(frozen=True)
class Composing:
    key: str
    index: int
    facts: tuple[str, ...]


@dataclass
class Step:
    parts: list[Part]
    effects: list[Json] = field(default_factory=list)
    composing: Composing | None = None
    writes: list[str] = field(default_factory=list)


Summarize = Callable[[Package, str], tuple[str, str]]


@dataclass
class Story:
    message: Message
    now: datetime
    ledger: Ledger
    tools: ToolContext
    locale: str
    summarize: Summarize

    def session(self) -> Any:
        return customer_session(self.message.customer_id, SERVICE).dynamodb


def answered(story: Story, answer: Answer) -> Step:
    asked, target = answer.ask, answer.ask.target
    if asked.ask in rules.ABOUT_THE_CHARGE:
        return _about_the_charge(story, answer)
    if asked.ask == rules.HAVE_CARD:
        charge = read_charge(story, target)
        if charge is None:
            return _unavailable(story)
        if answer.option == "yes":
            consent = fixed("consent_claim", story.locale, c=charge)
            return Step([consent, View("charge", (charge.id,)), Ask(rules.CLAIM, (charge.id,))])
        return protect(story, charge)
    if answer.option == "no":
        key = {rules.BLOCK: "declined_block", rules.CLAIM: "declined_claim"}.get(asked.ask, "declined_person")
        return Step([template(key, story.locale)], composing=Composing(key, 0, ()))
    if asked.ask == rules.BLOCK:
        return _block(story, asked)
    if asked.ask == rules.CLAIM:
        charge = read_charge(story, target)
        if charge is None:
            return _unavailable(story)
        return _hand_off(story, asked, "claim", "claim", charge=charge, card=_card_of_charge(story, charge))
    return _person(story, asked)


def _about_the_charge(story: Story, answer: Answer) -> Step:
    asked = answer.ask
    if answer.option == "why":
        charge = read_charge(story, asked.target)
        if charge is None:
            return _unavailable(story)
        why = template("why_asked", story.locale, c=charge)
        return Step(
            [why, View("charge", (charge.id,)), Ask(rules.WAS_IT_YOU, (charge.id,))],
            composing=Composing("why_asked", 0, (charge.id,)),
        )
    closing = rules.close_ask(answer, story.message, story.now)
    if closing.outcome == "missing":
        return _unavailable(story)
    kind = "recognized_charge" if answer.option == "yes" else "unrecognized_charge"
    if closing.outcome == "already" and closing.earlier != kind:
        return Step([fixed("already", story.locale)])
    writes = ["memory"] if closing.outcome == "written" else []
    answered = _answered(asked.target) if closing.outcome in ("written", "redelivered") else []
    charge = read_charge(story, asked.target)
    if answer.option == "yes":
        facts = (charge.id,) if charge else ()
        thanks = template("recognized", story.locale)
        return Step([thanks], answered, Composing("recognized", 0, facts), writes)
    if charge is None:
        return _unavailable(story)
    if asked.ask == rules.WAS_IT_YOU or answer.by in ("floor", "graph") or rules.protect_signals(charge):
        step = protect(story, charge)
    else:
        step = Step(
            [
                fixed("have_card", story.locale),
                View("charge", (charge.id,)),
                Ask(rules.HAVE_CARD, (charge.id,)),
            ]
        )
    step.writes = writes + step.writes
    step.effects = answered + step.effects
    return step


def _answered(target: Target) -> list[Json]:
    return (
        [{"type": "charge_answered", "transaction_id": target.transaction_id}]
        if target.transaction_id
        else []
    )


def not_me(story: Story, pending: OpenAsk | None) -> Step:
    if pending is not None and pending.target.transaction_id is not None:
        charge = read_charge(story, pending.target)
        if charge is not None:
            return protect(story, charge)
    if pending is not None and pending.ask == rules.BLOCK and pending.target.product_id:
        card = card_fact(story, pending.target.product_id)
        if card is not None:
            return protect(story, card)
    read = call("search_movements", {"limit": 5}, story.tools, story.ledger)
    rows = [fact_id for fact_id in read.ids if story.ledger.facts[fact_id].kind == "movement"][:5]
    if not rows:
        return Step(answers.safety("not_me", story.ledger, story.locale))
    return Step([fixed("not_me", story.locale), Ask("which_one", tuple(rows), target={"purpose": "not_me"})])


def lost(story: Story) -> Step:
    read = call("list_cards", {}, story.tools, story.ledger)
    cards = [fact_id for fact_id in read.ids if story.ledger.facts[fact_id].kind == "card"]
    if not cards:
        return Step(answers.safety("lost_stolen", story.ledger, story.locale))
    active = [fact_id for fact_id in cards if _active(story.ledger.facts[fact_id])]
    if not active:
        person = Ask(rules.PERSON, (), target={"reason": "lost", "area": "fraud"})
        return Step([fixed("lost_none", story.locale), View("cards", tuple(cards)), person])
    return Step(
        [
            fixed("lost", story.locale),
            View("cards", tuple(cards)),
            Ask("which_one", tuple(active[:5]), target={"purpose": "lost"}),
        ]
    )


def picked(story: Story, choice: Choice) -> Step:
    if choice.purpose == "lost":
        card = card_fact(story, choice.option)
        return protect(story, card) if card is not None else _unavailable(story)
    ask_id = str((story.message.input or {}).get("ask_id"))
    charge_id = _charge_of_pick(story, choice.option)
    charge = story.ledger.facts[charge_id] if charge_id else None
    if charge is None:
        return _unavailable(story)
    product = _ref(charge, "charge.card_ref")
    outcome, _, _ = rules.remember_answer(
        story.message.customer_id,
        ask_id,
        Target(product, choice.option),
        False,
        None,
        story.message.room_id,
        story.now,
    )
    step = protect(story, charge)
    if outcome == "written":
        step.writes.insert(0, "memory")
    if outcome in ("written", "redelivered"):
        step.effects = _answered(Target(product, choice.option)) + step.effects
    return step


def protect(story: Story, subject: Fact) -> Step:
    product = _ref(subject, "charge.card_ref") or _ref(subject, "card_ref")
    card = card_fact(story, product) if product else None
    if card is None:
        return _unavailable(story)
    if not _active(card):
        target: Json = {"reason": "card_blocked", "area": "fraud"}
        return Step(
            [
                fixed("card_blocked_offer", story.locale, k=card),
                Ask(rules.PERSON, (subject.id,), target=target),
            ]
        )
    return Step(
        [
            fixed("consent_block", story.locale, k=card),
            View("card", (card.id,)),
            Ask(rules.BLOCK, (subject.id,)),
        ]
    )


def _block(story: Story, asked: OpenAsk) -> Step:
    target = asked.target
    if target.product_id is None:
        return _unavailable(story)
    card = card_fact(story, target.product_id)
    charge = read_charge(story, target) if target.transaction_id else None
    if card is None:
        return _unavailable(story)
    accounts = Accounts.from_dynamodb(story.session())
    outcome = accounts.block(
        story.message.customer_id, target.product_id, asked.ask_id, format_instant(story.now)
    )
    status = accounts.read_status(story.message.customer_id, target.product_id)
    block: BlockOutcome
    if status == BLOCKED and outcome in ("written", "redelivered"):
        block, receipt = "blocked", "blocked"
    elif status == BLOCKED and outcome == "already":
        block, receipt = "blocked_before", "blocked_before"
    else:
        block, receipt = "unconfirmed", "block_unconfirmed"
    effects: list[Json] = []
    if block == "blocked":
        effects.append({"type": "card_blocked", "product_id": target.product_id})
    request = "not_me" if charge is not None else "lost"
    step = _hand_off(story, asked, "fraud", request, charge=charge, card=card, block=block)
    step.parts.insert(0, fixed(receipt, story.locale, k=card))
    step.effects = effects + step.effects
    step.writes = (["block"] if outcome == "written" else []) + step.writes
    return step


def _person(story: Story, asked: OpenAsk) -> Step:
    target = asked.target
    kind: Kind = "fraud" if target.area == "fraud" else "service"
    charge = read_charge(story, target) if target.transaction_id else None
    card = card_fact(story, target.product_id) if target.product_id else None
    if kind == "fraud":
        request = "not_me" if charge is not None else "lost"
        block: BlockOutcome | None = "blocked_before" if card is not None and not _active(card) else None
        return _hand_off(story, asked, kind, request, charge=charge, card=card, block=block)
    request = target.reason if target.reason in ("unblock", "refund", "human") else "other"
    return _hand_off(story, asked, kind, request, charge=charge, card=card)


def _hand_off(
    story: Story,
    asked: OpenAsk,
    kind: Kind,
    request: str,
    *,
    charge: Fact | None = None,
    card: Fact | None = None,
    block: BlockOutcome | None = None,
) -> Step:
    target = asked.target
    customer = story.message.customer_id
    cases = Cases.from_dynamodb(story.session())
    product = target.product_id or (_ref(card, "card_ref") if card else None)
    evidence = {
        "room_id": story.message.room_id,
        "ask_id": asked.ask_id,
        "message_id": story.message.message_id,
        **({"transaction_id": target.transaction_id} if target.transaction_id else {}),
    }
    row, created = cases.open(
        customer, asked.ask_id, kind, format_instant(story.now), product, target.transaction_id, evidence
    )
    if row is None:
        contact = answers.contact(story.ledger)
        return Step([fixed("case_unconfirmed", story.locale, p=contact)])
    case = story.ledger.add(
        "case", case_fields(story.tools, Accounts.from_dynamodb(story.tools.dynamodb()), row)
    )
    package = Package(kind, request, case, charge, card, block, evidence)
    texts = points(package, story.locale)
    listed = rendered(texts, story.ledger, story.locale)
    summary, source = story.summarize(package, summary_template(package, story.locale))
    written = cases.write_summary(
        customer, asked.ask_id, summary_row(summary, listed, story.locale, source, story.now)
    )
    receipt = "claim_opened" if kind == "claim" else "case_opened"
    return Step(
        [fixed(receipt, story.locale, s=case), View("case", (case.id,))],
        effects=[{"type": "case_opened", "complaint_id": asked.ask_id, "case_type": kind}],
        writes=[*(["case"] if created else []), *(["summary"] if written else [])],
    )


def read_charge(story: Story, target: Target) -> Fact | None:
    if target.transaction_id is None or target.product_id is None:
        return None
    read = call("charge_facts", {"transaction_ref": target.transaction_id}, story.tools, story.ledger)
    fact = story.ledger.get(read.ids[0]) if read.ids else None
    if (
        fact is None
        or fact.kind != "charge"
        or fact.fields.get("charge.card_ref") != Ref("card", target.product_id)
    ):
        return None
    return fact


def card_fact(story: Story, product_id: str) -> Fact | None:
    wanted = Ref("card", product_id)
    known = [
        fact
        for fact in story.ledger.facts.values()
        if fact.kind == "card" and fact.fields.get("card_ref") == wanted
    ]
    if not known:
        call("list_cards", {}, story.tools, story.ledger)
        known = [
            fact
            for fact in story.ledger.facts.values()
            if fact.kind == "card" and fact.fields.get("card_ref") == wanted
        ]
    return known[-1] if known else None


def _card_of_charge(story: Story, charge: Fact) -> Fact | None:
    product = _ref(charge, "charge.card_ref")
    return card_fact(story, product) if product else None


def _charge_of_pick(story: Story, transaction_id: str) -> str | None:
    read = call("charge_facts", {"transaction_ref": transaction_id}, story.tools, story.ledger)
    fact = story.ledger.get(read.ids[0]) if read.ids else None
    return fact.id if fact is not None and fact.kind == "charge" else None


def _active(card: Fact) -> bool:
    return card.fields.get("status") == Status("card", "Active")


def _ref(fact: Fact, name: str) -> str | None:
    value = fact.fields.get(name)
    return value.value if isinstance(value, Ref) else None


def _unavailable(story: Story) -> Step:
    return Step(fallback("unavailable", story.ledger, story.locale))
