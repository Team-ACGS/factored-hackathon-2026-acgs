import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from typing import Any

from core import answers, rules, story
from core.access import customer_session
from core.cases import OPEN_STAGES, Cases, stage
from core.customers import read_customer
from core.facts import Ask, Part, Say, fallback, render_text
from core.facts.catalog import LOCALES
from core.facts.values import Country, Ledger, Ref, Text
from core.graphs.compose import ComposeRun, run_compose
from core.graphs.model import Clients, bedrock_clients
from core.graphs.open_mode import Metrics, OpenModeRun, run_open_mode
from core.graphs.profiles import ModelProfile
from core.graphs.prompt import Context, shown_rows
from core.handoff import Package, points
from core.memory import Memory
from core.messaging import Message
from core.policies import COUNTRIES
from core.receipts import template
from core.replies import Reply, compose
from core.retrieval import PolicySearch
from core.router import AbstainClass, FloorClass, Route, abstain, closer, floor
from core.rules import TurnState
from core.tools import ToolContext, ToolResult, call
from core.tools.memory import newest, remember_fact

SERVICE = "chatbot"
EXCHANGES = 3
CONTEXT_MESSAGES = 2 * EXCHANGES
DEFAULT_LOCALE = "es"
SENDERS = {"customer": "customer", "assistant": "clara", "agent": "agent"}
CONTEXT_MEMORIES = 5
MAX_MEMORY_READ = 200
MAX_CASES_READ = 100


@dataclass(frozen=True)
class Turn:
    reply: Reply
    route: str
    floor: str | None
    locale: str
    metrics: Metrics | None
    duration_ms: int
    profile: ModelProfile
    writes: tuple[str, ...] = ()

    def summary(self) -> dict[str, Any]:
        metrics = self.metrics or Metrics()
        return {
            "route": self.route,
            "model": self.profile.id,
            "prompt": self.profile.prompt,
            "cost_usd": str(self.profile.cost(metrics.steps).quantize(Decimal("0.000001"))),
            "floor": self.floor,
            "locale": self.locale,
            "source": self.reply.source,
            "duration_ms": self.duration_ms,
            "steps": sum(1 for step in metrics.steps if step["node"] == "supervisor"),
            "timings": metrics.steps,
            "tool_calls": metrics.tools,
            "tokens": metrics.tokens(),
            "check": {
                "result": _check_result(self.reply, metrics),
                "errors": metrics.check_errors,
                "tidied": metrics.tidied,
            },
            "exhausted": metrics.exhausted,
            "writes": list(self.writes),
            "effects": [effect["type"] for effect in self.reply.effects],
        }


def run_turn(
    message: Message,
    history: Sequence[Message],
    now: datetime,
    *,
    profile: ModelProfile,
    clients: Clients | None = None,
    clock: Callable[[], float] = time.monotonic,
    policies: PolicySearch | None = None,
    on_status: Callable[[str, int], None] | None = None,
) -> Turn:
    started = clock()
    dynamodb = customer_session(message.customer_id, SERVICE, read_only=True).dynamodb
    customer = read_customer(dynamodb, message.customer_id) or {}
    language = str(customer.get("language"))
    locale = language if language in LOCALES else DEFAULT_LOCALE
    country = str(customer.get("country"))
    asked = rules.latest_reply(message, history)
    pending = rules.open_ask(asked)
    answer = rules.answer_of(message, pending)
    choice = rules.resolve_choice(message, asked)
    topic = rules.topic_of(message)
    structured = answer is not None or choice is not None or topic is not None
    hit = None if structured else floor(message.text)
    abstained = None if structured or hit else abstain(message.text)
    closing_words = not (structured or hit or abstained or pending) and closer(message.text)
    decided = Route("closer") if closing_words else _route(answer, choice, topic, hit)

    def done(reply: Reply, metrics: Metrics | None = None, writes: Sequence[str] = ()) -> Turn:
        elapsed = round((clock() - started) * 1000)
        return Turn(reply, decided.mode, decided.floor, locale, metrics, elapsed, profile, tuple(writes))

    if country not in COUNTRIES:
        unavailable = Ledger("US", now)
        return done(compose(fallback("unavailable", unavailable, locale), unavailable, locale, "fallback"))
    ledger = Ledger(country, now)
    if closing_words:
        return done(compose([Say(answers.CLOSER[locale])], ledger, locale, "say_key"))
    given_name = customer.get("given_name")
    ledger.add(
        answers.CUSTOMER,
        {"given_name": Text(given_name) if given_name else None, "country": Country(country)},
    )
    tools = ToolContext(message.customer_id, country, locale, now, SERVICE, None, policies)
    models = clients or bedrock_clients
    metrics = Metrics()

    def summarize(package: Package, example: str) -> tuple[str, str]:
        said = run_compose(
            ComposeRun(
                "summary",
                example,
                package.facts(),
                ledger,
                locale,
                profile,
                models,
                clock,
                extra={"points": points(package, locale), "messages": _customer_texts(history, message)},
                metrics=metrics,
            )
        )
        if said:
            return render_text(" ".join(said), ledger, locale), "compose"
        return render_text(example, ledger, locale), "template"

    steps = story.Story(message, now, ledger, tools, locale, summarize)
    step: story.Step | None = None
    if answer is not None:
        step = story.answered(steps, answer)
    elif choice is not None and choice.purpose:
        step = story.picked(steps, choice)
    elif hit == "not_me":
        step = story.not_me(steps, pending)
    elif hit == "lost_stolen":
        step = story.lost(steps)
    if step is not None:
        parts = _composed(step, ledger, locale, profile, models, clock, metrics)
        reply = replace(compose(parts, ledger, locale, "story"), effects=tuple(step.effects))
        return done(reply, metrics, step.writes)

    cards = call("list_cards", {}, tools, ledger)
    memories = _memories(tools, ledger, locale)
    picked = (
        call(str(choice.read.get("tool")), choice.read.get("args") or {}, tools, ledger) if choice else None
    )
    shown = _charge(topic, tools, ledger) if topic else None
    kept = _kept(pending, tools, ledger) if pending and not (choice or topic) else None
    charge = (picked.ids[0] if picked and choice and choice.recent else None) or (
        shown.ids[0] if shown else None
    )
    asking = rules.story_ask(ledger.get(charge or "")) if charge else None
    closing: Ask | None = Ask(asking, (charge,)) if asking and charge else kept
    if closing is None and abstained is not None:
        closing = Ask(rules.PERSON, (), target={"reason": abstained, "area": "service"})
    context = Context(
        given_name=given_name,
        locale=locale,
        today=tools.today.isoformat(),
        cards=ledger.payload(cards.ids),
        exchanges=exchanges(history, message),
        choice=(
            {"ask": choice.ask, "option": choice.option, **shown_rows(ledger, picked.ids)}
            if choice and picked
            else None
        ),
        memories=memories,
        topic={"type": "charge", **shown_rows(ledger, shown.ids)} if shown else None,
        story=_story(closing, kept is not None, abstained, ledger),
    )
    run = OpenModeRun(
        message.text,
        context,
        ledger,
        tools,
        profile,
        models,
        clock,
        state=TurnState(
            choice.ask if choice else None,
            closing.ask if closing else None,
            _open_cases(tools) if closing is None else frozenset(),
            rules.said_key(asked),
            _charge_of(kept, ledger),
            kept is not None and rules.answerable(message, pending, abstained is not None),
        ),
        on_status=on_status,
        closing=(closing,) if closing else (),
        metrics=metrics,
    )
    for read in (picked, shown):
        if read:
            run.read_rounds.append(list(read.ids))
    reply = run_open_mode(run)
    if pending is not None and run.answer is not None:
        step = story.answered(steps, rules.graph_answer(message, pending, run.answer))
        parts = _composed(step, ledger, locale, profile, models, clock, metrics)
        answered = replace(compose(parts, ledger, locale, "story"), effects=tuple(step.effects))
        return done(answered, metrics, [f"{write}:graph" for write in step.writes])
    if abstained is not None and reply.source == "fallback" and closing is not None:
        reply = compose([template(f"abstain_{abstained}", locale), closing], ledger, locale, "fallback")
    return done(reply, run.metrics)


def _route(
    answer: rules.Answer | None,
    choice: rules.Choice | None,
    topic: rules.Target | None,
    hit: FloorClass | None,
) -> Route:
    if answer is not None:
        return Route("story", "not_me" if answer.by == "floor" else None)
    if choice is not None:
        return Route("story" if choice.purpose else "choice")
    if topic is not None:
        return Route("topic")
    if hit is not None:
        return Route("safety", hit)
    return Route("open_mode")


def _composed(
    step: story.Step,
    ledger: Ledger,
    locale: str,
    profile: ModelProfile,
    models: Clients,
    clock: Callable[[], float],
    metrics: Metrics,
) -> list[Part]:
    parts = list(step.parts)
    composing = step.composing
    if composing is None:
        return parts
    example = parts[composing.index]
    assert isinstance(example, Say)
    said = run_compose(
        ComposeRun(
            composing.key,
            example.text,
            composing.facts,
            ledger,
            locale,
            profile,
            models,
            clock,
            metrics=metrics,
        )
    )
    if said:
        parts[composing.index : composing.index + 1] = [Say(text) for text in said]
    return parts


def _charge(target: rules.Target, tools: ToolContext, ledger: Ledger) -> ToolResult | None:
    if target.transaction_id is None or target.product_id is None:
        return None
    read = call("charge_facts", {"transaction_ref": target.transaction_id}, tools, ledger)
    fact = ledger.get(read.ids[0]) if read.ids else None
    if (
        fact is None
        or fact.kind != "charge"
        or fact.fields.get("charge.card_ref") != _card_ref(target.product_id)
    ):
        return None
    return read


def _kept(pending: rules.OpenAsk, tools: ToolContext, ledger: Ledger) -> Ask | None:
    target = pending.target
    read = _charge(target, tools, ledger) if target.transaction_id else None
    charge = read.ids[0] if read else None
    if pending.ask == rules.PERSON:
        case = _case(target.complaint_id, tools, ledger) if target.complaint_id else None
        subject = charge or case
        return Ask(rules.PERSON, (subject,) if subject else (), target=target.to_wire())
    if pending.ask == rules.BLOCK and charge is None and target.product_id:
        wanted = _card_ref(target.product_id)
        card = next(
            (
                fact.id
                for fact in ledger.facts.values()
                if fact.kind == "card" and fact.fields.get("card_ref") == wanted
            ),
            None,
        )
        return Ask(rules.BLOCK, (card,)) if card else None
    return Ask(pending.ask, (charge,)) if charge else None


def _case(complaint_id: str, tools: ToolContext, ledger: Ledger) -> str | None:
    read = call("case_status", {"case_ref": complaint_id}, tools, ledger)
    fact = ledger.get(read.ids[0]) if read.ids else None
    return fact.id if fact is not None and fact.kind == "case" else None


def _charge_of(kept: Ask | None, ledger: Ledger) -> str | None:
    subject = ledger.get(kept.facts[0]) if kept and kept.facts else None
    return subject.id if subject is not None and subject.kind == "charge" else None


def _card_ref(product_id: str) -> Ref:
    return Ref("card", product_id)


def _open_cases(tools: ToolContext) -> frozenset[str]:
    items, _ = Cases.from_dynamodb(tools.dynamodb()).cases(tools.customer_id, MAX_CASES_READ)
    return frozenset(
        str(item["transaction_id"])
        for item in items
        if item.get("transaction_id") and stage(item) in OPEN_STAGES
    )


def _memories(tools: ToolContext, ledger: Ledger, locale: str) -> list[dict[str, str]]:
    items, _ = Memory.from_dynamodb(tools.dynamodb()).memories(tools.customer_id, "", MAX_MEMORY_READ)
    facts = [remember_fact(tools, ledger, item) for item in newest(items)[:CONTEXT_MEMORIES]]
    return [{"fact": fact.id, "says": answers.remembered(fact, ledger, locale)} for fact in facts]


def _story(
    closing: Ask | None, open_: bool, abstained: AbstainClass | None, ledger: Ledger
) -> dict[str, Any] | None:
    if closing is None:
        return None
    body: dict[str, Any] = {"ask": closing.ask, "open": open_}
    subject = ledger.get(closing.facts[0]) if closing.facts else None
    if subject is not None:
        body["charge" if subject.kind == "charge" else "card"] = subject.id
        if open_:
            body.update(shown_rows(ledger, [subject.id]))
    if abstained is not None and closing.ask == rules.PERSON and not open_:
        body["abstain"] = abstained
    return body


def _customer_texts(history: Sequence[Message], message: Message) -> list[str]:
    earlier = [
        item.text
        for item in history
        if item.sender_type == "customer" and item.message_key < message.message_key
    ]
    return [*earlier[-CONTEXT_MESSAGES:], message.text]


def exchanges(history: Sequence[Message], message: Message) -> list[dict[str, str]]:
    earlier = [item for item in history if item.message_key < message.message_key]
    return [{"from": SENDERS[item.sender_type], "text": item.text} for item in earlier[-CONTEXT_MESSAGES:]]


def _check_result(reply: Reply, metrics: Metrics) -> str:
    if reply.source in ("composed", "say_key"):
        return "pass"
    if reply.source == "repaired":
        return "repaired"
    return "failed" if metrics.check_errors else "skipped"
