import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from core import answers
from core.access import customer_session
from core.customers import read_customer
from core.facts import fallback
from core.facts.catalog import LOCALES
from core.facts.values import Country, Ledger, Text
from core.graphs.model import Clients, bedrock_clients
from core.graphs.open_mode import Metrics, OpenModeRun, run_open_mode
from core.graphs.prompt import Context
from core.messaging import Message
from core.policies import COUNTRIES
from core.replies import Reply, compose
from core.retrieval import PolicySearch
from core.router import route
from core.tools import ToolContext, call

SERVICE = "chatbot"
EXCHANGES = 3
DEFAULT_LOCALE = "es"
SENDERS = {"customer": "customer", "assistant": "clara", "agent": "agent"}


@dataclass(frozen=True)
class Turn:
    reply: Reply
    route: str
    floor: str | None
    locale: str
    metrics: Metrics | None
    duration_ms: int

    def summary(self) -> dict[str, Any]:
        metrics = self.metrics or Metrics()
        return {
            "route": self.route,
            "floor": self.floor,
            "locale": self.locale,
            "source": self.reply.source,
            "duration_ms": self.duration_ms,
            "steps": sum(1 for step in metrics.steps if step["node"] == "supervisor"),
            "timings": metrics.steps,
            "tool_calls": metrics.tools,
            "tokens": metrics.tokens(),
            "check": {"result": _check_result(self.reply, metrics), "errors": metrics.check_errors},
            "exhausted": metrics.exhausted,
        }


def run_turn(
    message: Message,
    history: Sequence[Message],
    now: datetime,
    *,
    clients: Clients | None = None,
    clock: Callable[[], float] = time.monotonic,
    policies: PolicySearch | None = None,
    model_id: str | None = None,
) -> Turn:
    started = clock()
    dynamodb = customer_session(message.customer_id, SERVICE, read_only=True).dynamodb
    profile = read_customer(dynamodb, message.customer_id) or {}
    language = str(profile.get("language"))
    locale = language if language in LOCALES else DEFAULT_LOCALE
    country = str(profile.get("country"))
    decided = route(message.text)

    def done(reply: Reply, metrics: Metrics | None = None) -> Turn:
        elapsed = round((clock() - started) * 1000)
        return Turn(reply, decided.mode, decided.floor, locale, metrics, elapsed)

    if country not in COUNTRIES:
        unavailable = Ledger("US", now)
        return done(compose(fallback("unavailable", unavailable, locale), unavailable, locale, "fallback"))
    ledger = Ledger(country, now)
    given_name = profile.get("given_name")
    ledger.add(
        answers.CUSTOMER,
        {"given_name": Text(given_name) if given_name else None, "country": Country(country)},
    )
    if decided.floor is not None:
        return done(compose(answers.safety(decided.floor, ledger, locale), ledger, locale, "safety"))

    tools = ToolContext(message.customer_id, country, locale, now, SERVICE, None, policies)
    cards = call("list_cards", {}, tools, ledger)
    context = Context(
        given_name=given_name,
        locale=locale,
        today=tools.today.isoformat(),
        cards=ledger.payload(cards.ids),
        exchanges=exchanges(history, message),
    )
    run = OpenModeRun(message.text, context, ledger, tools, clients or bedrock_clients, clock, model_id)
    return done(run_open_mode(run), run.metrics)


def exchanges(history: Sequence[Message], message: Message) -> list[dict[str, str]]:
    earlier = [item for item in history if item.message_key < message.message_key]
    return [{"from": SENDERS[item.sender_type], "text": item.text} for item in earlier[-2 * EXCHANGES :]]


def _check_result(reply: Reply, metrics: Metrics) -> str:
    if reply.source in ("composed", "say_key"):
        return "pass"
    if reply.source == "repaired":
        return "repaired"
    return "failed" if metrics.check_errors else "skipped"
