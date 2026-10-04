import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from core import answers, rules
from core.access import customer_session
from core.customers import read_customer
from core.facts import Ask, fallback
from core.facts.catalog import LOCALES
from core.facts.values import Country, Ledger, Ref, Text
from core.graphs.model import Clients, bedrock_clients
from core.graphs.open_mode import Metrics, OpenModeRun, run_open_mode
from core.graphs.profiles import ModelProfile
from core.graphs.prompt import Context, shown_rows
from core.memory import Memory
from core.messaging import Message
from core.policies import COUNTRIES
from core.replies import Reply, compose
from core.retrieval import PolicySearch
from core.router import Route, route
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


@dataclass(frozen=True)
class Turn:
    reply: Reply
    route: str
    floor: str | None
    locale: str
    metrics: Metrics | None
    duration_ms: int
    profile: ModelProfile

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
    decided = _route(message, answer, choice, topic)

    def done(reply: Reply, metrics: Metrics | None = None) -> Turn:
        elapsed = round((clock() - started) * 1000)
        return Turn(reply, decided.mode, decided.floor, locale, metrics, elapsed, profile)

    if country not in COUNTRIES:
        unavailable = Ledger("US", now)
        return done(compose(fallback("unavailable", unavailable, locale), unavailable, locale, "fallback"))
    ledger = Ledger(country, now)
    given_name = customer.get("given_name")
    ledger.add(
        answers.CUSTOMER,
        {"given_name": Text(given_name) if given_name else None, "country": Country(country)},
    )
    if answer is not None:
        return done(_closed(answer, message, now, ledger, locale))
    if decided.floor is not None:
        return done(compose(answers.safety(decided.floor, ledger, locale), ledger, locale, "safety"))

    tools = ToolContext(message.customer_id, country, locale, now, SERVICE, None, policies)
    cards = call("list_cards", {}, tools, ledger)
    memories = _memories(tools, ledger, locale)
    picked = (
        call(str(choice.read.get("tool")), choice.read.get("args") or {}, tools, ledger) if choice else None
    )
    shown = _charge(topic, tools, ledger) if topic else None
    kept = _charge(pending.target, tools, ledger) if pending and not (choice or topic) else None
    charge = (picked.ids[0] if picked and choice and choice.recent else None) or (
        shown.ids[0] if shown else None
    )
    asking = charge if rules.asks_to_recognize(ledger.get(charge or "")) else None
    reshown = kept.ids[0] if kept and rules.asks_to_recognize(ledger.get(kept.ids[0])) else None
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
        story=_story(asking, reshown, kept, ledger),
    )
    question = asking or reshown
    run = OpenModeRun(
        message.text,
        context,
        ledger,
        tools,
        profile,
        clients or bedrock_clients,
        clock,
        state=TurnState(choice.ask if choice else None, rules.RECOGNIZE if question else None),
        on_status=on_status,
        closing=(Ask(rules.RECOGNIZE, (question,)),) if question else (),
    )
    for read in (picked, shown):
        if read:
            run.read_rounds.append(list(read.ids))
    return done(run_open_mode(run), run.metrics)


def _route(
    message: Message, answer: rules.Answer | None, choice: rules.Choice | None, topic: rules.Target | None
) -> Route:
    if answer is not None:
        return Route("story", "not_me" if answer.by == "floor" else None)
    if choice is not None:
        return Route("choice")
    if topic is not None:
        return Route("topic")
    return route(message.text)


def _closed(answer: rules.Answer, message: Message, now: datetime, ledger: Ledger, locale: str) -> Reply:
    closing = rules.close_ask(answer, message, now, SERVICE)
    if closing.outcome in ("written", "redelivered") and answer.option == "no":
        return compose(answers.safety("not_me", ledger, locale), ledger, locale, "story")
    outcome = "recognized" if closing.outcome in ("written", "redelivered") else closing.outcome
    return compose(answers.closed(outcome, ledger, locale), ledger, locale, "story")


def _charge(target: rules.Target, tools: ToolContext, ledger: Ledger) -> ToolResult | None:
    read = call("charge_facts", {"transaction_ref": target.transaction_id}, tools, ledger)
    fact = ledger.get(read.ids[0]) if read.ids else None
    if (
        fact is None
        or fact.kind != "charge"
        or fact.fields.get("charge.card_ref") != Ref("card", target.product_id)
    ):
        return None
    return read


def _memories(tools: ToolContext, ledger: Ledger, locale: str) -> list[dict[str, str]]:
    items, _ = Memory.from_dynamodb(tools.dynamodb()).memories(tools.customer_id, "", MAX_MEMORY_READ)
    facts = [remember_fact(tools, ledger, item) for item in newest(items)[:CONTEXT_MEMORIES]]
    return [{"fact": fact.id, "says": answers.remembered(fact, ledger, locale)} for fact in facts]


def _story(
    asking: str | None, reshown: str | None, kept: ToolResult | None, ledger: Ledger
) -> dict[str, Any] | None:
    if asking:
        return {"ask": rules.RECOGNIZE, "charge": asking, "open": False}
    if reshown and kept:
        return {"ask": rules.RECOGNIZE, "charge": reshown, "open": True, **shown_rows(ledger, kept.ids)}
    return None


def exchanges(history: Sequence[Message], message: Message) -> list[dict[str, str]]:
    earlier = [item for item in history if item.message_key < message.message_key]
    return [{"from": SENDERS[item.sender_type], "text": item.text} for item in earlier[-CONTEXT_MESSAGES:]]


def _check_result(reply: Reply, metrics: Metrics) -> str:
    if reply.source in ("composed", "say_key"):
        return "pass"
    if reply.source == "repaired":
        return "repaired"
    return "failed" if metrics.check_errors else "skipped"
