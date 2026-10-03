"""The chatbot's turn: a fixed pipeline, not an agent loop.

    load_prior_ask -> resolve_ask? -> classify -> extract? -> retrieve
    -> decide -> act? -> compose -> egress -> assemble

Every step is deterministic code except ``extract`` and ``compose``, and both
of those call Bedrock only when a rule or a template cannot answer, and both
fail soft to the deterministic path (see ``llm.py``). No step ever lets an
LLM pick *which* tool or action to run: `classify`/`decide` do that in plain
code, and the two sensitive actions (`block_card`, `create_complaint`) live
outside `core.tools.registry.TOOLS`, reachable only from `act`, only after an
explicit customer confirmation.

Scope note (Option A, text-only): the project's `core.messaging.Message`
only carries a flat `text` field today; there is no `blocks` field for
structured `say`/`view`/`ask` parts yet (that is Option B, future work, and
touches `core`, `apps/customer` and possibly `chat_notifier`). To still
support a two-turn confirmation ("may I block your card?" / "yes") without
touching anything outside `lambdas/chatbot`, a pending `Ask` is encoded as a
small tagged suffix on the stored reply text and decoded back on the next
turn (`_encode_ask`/`_decode_ask`). That suffix is visible in the chat today;
it goes away once `Message` grows a real `blocks` field.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from core.customers import read_customer
from core.facts import Ask, Fact, Ledger, Part, Say, View, check, fallback, parse_parts, render, render_text
from core.facts.parts import InvalidPart
from core.facts.values import Ref, Trace
from core.messaging import Message, Messaging
from core.observability import logger
from core.policies import LANGUAGES
from core.tools.context import NotFound, ToolContext, Verdict
from core.tools.registry import call as call_tool

from chatbot import actions, lexicon, llm

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource

ASK_TAG_START = "\n[[ask:"
ASK_TAG_END = "]]"


@dataclass(frozen=True)
class ProposedAction:
    name: str  # "block_card" | "create_complaint"
    args: dict[str, str]


@dataclass
class TurnState:
    customer_id: str
    country: str
    language: str
    room_id: str
    message_text: str
    prior_ask: Ask | None = None
    confirmed: bool | None = None
    intent: str | None = None
    slots: dict[str, str] = field(default_factory=dict)
    ledger: Ledger | None = None
    decision: Verdict | None = None
    proposed_action: ProposedAction | None = None
    say: str | None = None
    view: View | None = None
    ask: Ask | None = None


# ---------------------------------------------------------------------------
# load_prior_ask / resolve_ask
# ---------------------------------------------------------------------------


def load_prior_ask(state: TurnState, messaging: Messaging) -> None:
    """Determinista: lee el último mensaje "assistant" de la sala. No usa
    ninguna tabla nueva, todo vive en el propio mensaje que `assemble` ya
    escribió en el turno anterior."""
    history = messaging.history(state.customer_id, state.room_id)
    if history and history[-1].sender_type == "customer":
        history = history[:-1]
    if history and history[-1].sender_type == "assistant":
        state.prior_ask = _decode_ask(history[-1].text)


def resolve_ask(state: TurnState) -> bool:
    """Determinista: si hay una pregunta pendiente y la respuesta es un
    sí/no claro, resuelve el turno aquí mismo (sin pasar por
    classify/extract/retrieve/decide) y devuelve True. Si no hay pregunta
    pendiente, o la respuesta es ambigua, devuelve False y el turno sigue el
    camino normal, tratando el mensaje como uno nuevo."""
    if state.prior_ask is None:
        return False
    yes = lexicon.polarity(state.message_text)
    if yes is None:
        return False
    state.confirmed = yes
    state.proposed_action = _action_for(state.prior_ask, yes)
    return True


def _action_for(ask: Ask, yes: bool) -> ProposedAction | None:
    if not yes or ask.target is None:
        return None
    if ask.ask == "block":
        return ProposedAction("block_card", {"card_ref": ask.target})
    if ask.ask == "claim" and ":" in ask.target:
        product_id, transaction_id = ask.target.split(":", 1)
        return ProposedAction("create_complaint", {"product_id": product_id, "transaction_id": transaction_id})
    return None


# ---------------------------------------------------------------------------
# classify / extract
# ---------------------------------------------------------------------------


def classify(state: TurnState) -> None:
    """Determinista: la intención decide qué tools llama `retrieve`. Nunca es
    un LLM el que elige la tool."""
    state.intent = lexicon.intent_of(state.message_text)


def extract(state: TurnState) -> None:
    """LLM condicional: solo cuando el intent necesita un dato (el comercio
    mencionado) que la regla determinista (`lexicon.mentioned_merchant`) no
    pudo sacar del texto libre."""
    if state.intent not in ("movements", "claim"):
        return
    guess = lexicon.mentioned_merchant(state.message_text)
    if guess is not None:
        state.slots["merchant"] = guess
        return
    extracted = llm.extract_merchant(state.message_text, state.language)
    if extracted is not None:
        state.slots["merchant"] = extracted


# ---------------------------------------------------------------------------
# retrieve
# ---------------------------------------------------------------------------


def retrieve(state: TurnState, context: ToolContext) -> None:
    """Determinista: llama TOOLS[intent] por un lookup fijo, no por una
    elección libre de un LLM."""
    assert state.ledger is not None
    ledger = state.ledger
    if state.intent in ("block_card", "cards"):
        call_tool("list_cards", {}, context, ledger)
    elif state.intent == "case_status":
        call_tool("case_status", {}, context, ledger)
    elif state.intent == "policies":
        call_tool("search_policies", {"query": state.message_text}, context, ledger)
    else:  # "claim" and the "movements" catch-all
        args: dict[str, Any] = {"merchant": state.slots["merchant"]} if "merchant" in state.slots else {"limit": 5}
        call_tool("search_movements", args, context, ledger)


# ---------------------------------------------------------------------------
# decide
# ---------------------------------------------------------------------------


def decide(state: TurnState) -> None:
    """Determinista: la tabla de reglas sobre el ledger. Solo *propone* una
    acción sensible (ask + view); nunca la ejecuta. `act` es el único lugar
    que ejecuta, y solo tras una confirmación explícita del cliente."""
    assert state.ledger is not None
    ledger = state.ledger

    if state.intent == "block_card":
        card = _first_fact(ledger, "card")
        target = _ref(card, "card_ref") if card else None
        if target is None:
            state.decision = Verdict("answer")
            return
        state.decision = Verdict("confirm_block", ("block_card",))
        state.ask = Ask("block", target=target)
        state.view = View("blockConfirm", (target,))
        state.proposed_action = ProposedAction("block_card", {"card_ref": target})
        return

    if state.intent == "claim":
        movement = _first_fact(ledger, "movement")
        transaction_ref = _ref(movement, "transaction_ref") if movement else None
        card_ref = _ref(movement, "card_ref") if movement else None
        if transaction_ref is None or card_ref is None:
            state.decision = Verdict("answer")
            return
        target = f"{card_ref}:{transaction_ref}"
        state.decision = Verdict("confirm_claim", ("create_complaint",))
        state.ask = Ask("claim", target=target)
        state.view = View("claimConfirm", (transaction_ref,))
        state.proposed_action = ProposedAction(
            "create_complaint", {"product_id": card_ref, "transaction_id": transaction_ref}
        )
        return

    state.decision = Verdict("answer")


def _first_fact(ledger: Ledger, kind: str) -> Fact | None:
    return next((fact for fact in ledger.facts.values() if fact.kind == kind), None)


def _ref(fact: Fact, field_name: str) -> str | None:
    value = fact.fields.get(field_name)
    return value.value if isinstance(value, Ref) else None


# ---------------------------------------------------------------------------
# act
# ---------------------------------------------------------------------------


def act(state: TurnState, context: ToolContext, write_dynamodb: "DynamoDBServiceResource") -> None:
    """Determinista. Solo corre si `resolve_ask` confirmó un sí a una
    pregunta pendiente. `block_card`/`create_complaint` no están en
    `core.tools.registry.TOOLS`: ningún LLM puede alcanzarlas, solo este
    nodo."""
    if state.confirmed is not True or state.proposed_action is None:
        return
    assert state.ledger is not None
    action = state.proposed_action
    try:
        if action.name == "block_card":
            actions.block_card(context, write_dynamodb, state.ledger, action.args["card_ref"])
            state.view = View("blockResult", (action.args["card_ref"],))
        elif action.name == "create_complaint":
            actions.create_complaint(
                context, write_dynamodb, state.ledger, action.args["product_id"], action.args["transaction_id"]
            )
            state.view = View("claimReceipt", (action.args["transaction_id"],))
        else:
            return
        state.decision = Verdict("done", (action.name,))
    except NotFound:
        state.ledger.add(
            "error",
            {"tool": Trace(action.name), "error": Trace("not_found"), "detail": Trace("no longer available")},
        )


# ---------------------------------------------------------------------------
# compose
# ---------------------------------------------------------------------------

_ASK_TEMPLATES: dict[str, dict[str, str]] = {
    "block": {
        "es": "Para bloquear tu tarjeta {ref}, responde sí o no.",
        "pt-BR": "Para bloquear seu cartão {ref}, responda sim ou não.",
        "en": "To block your card {ref}, reply yes or no.",
    },
    "claim": {
        "es": "¿Abro un reclamo por este cargo? Responde sí o no.",
        "pt-BR": "Abro uma reclamação sobre esta cobrança? Responda sim ou não.",
        "en": "Should I open a claim for this charge? Reply yes or no.",
    },
}

_RESULT_TEMPLATES: dict[str, dict[str, str]] = {
    "block_card": {
        "es": "Listo, bloqueé tu tarjeta {ref}.",
        "pt-BR": "Pronto, bloqueei seu cartão {ref}.",
        "en": "Done, I blocked your card {ref}.",
    },
    "create_complaint": {
        "es": "Listo, abrí el reclamo {case_id}.",
        "pt-BR": "Pronto, abri a reclamação {case_id}.",
        "en": "Done, I opened claim {case_id}.",
    },
}

_DECLINE_TEXT = {
    "es": "Entendido, no hago ningún cambio.",
    "pt-BR": "Entendido, não farei nenhuma alteração.",
    "en": "Got it, I will not make any changes.",
}


def compose(state: TurnState, locale: str) -> tuple[list[Part], bool]:
    """¿Hay plantilla para este caso? úsala, sin LLM. Si no (RAG), una
    llamada a Bedrock, siempre citando el ledger. Devuelve (parts, used_llm)
    para que `egress` sepa si corresponde el chequeo de grounding."""
    assert state.ledger is not None
    ledger = state.ledger

    if state.confirmed is False:
        return [Say(_DECLINE_TEXT[locale])], False

    if state.decision is not None and state.decision.decision == "done" and state.proposed_action is not None:
        return _result_parts(state, ledger, locale), False

    if state.ask is not None and state.confirmed is None:
        return [Say(_ask_question(state.ask, ledger, locale)), state.ask], False

    if state.intent == "policies":
        has_excerpts = any(fact.kind == "policy_chunk" for fact in ledger.facts.values())
        if has_excerpts:
            generated = llm.compose(state.message_text, ledger, locale)
            if generated is not None:
                return generated, True

    return fallback("answer", ledger, locale), False


def _ask_question(ask: Ask, ledger: Ledger, locale: str) -> str:
    template = _ASK_TEMPLATES[ask.ask][locale]
    if "{ref}" not in template:
        return template
    card = _first_fact(ledger, "card")
    ref_text = render_text(f"{{{card.id}.last4}}", ledger, locale) if card else ""
    return template.format(ref=ref_text)


def _result_parts(state: TurnState, ledger: Ledger, locale: str) -> list[Part]:
    action = state.proposed_action
    assert action is not None
    if action.name == "block_card":
        card = _first_fact(ledger, "card")
        ref_text = render_text(f"{{{card.id}.last4}}", ledger, locale) if card else ""
        text = _RESULT_TEMPLATES["block_card"][locale].format(ref=ref_text)
    else:
        case = _first_fact(ledger, "case")
        case_id_text = render_text(f"{{{case.id}.case_id}}", ledger, locale) if case else ""
        text = _RESULT_TEMPLATES["create_complaint"][locale].format(case_id=case_id_text)
    parts: list[Part] = [Say(text)]
    if state.view is not None:
        parts.append(state.view)
    return parts


# ---------------------------------------------------------------------------
# egress / assemble
# ---------------------------------------------------------------------------


def egress(parts: list[Part], ledger: Ledger, locale: str, used_llm: bool) -> list[Part]:
    """Determinista. Si `compose` usó plantilla, el texto ya está verificado
    y este paso es trivial. Si usó Bedrock, corre el chequeo de citación de
    `core.facts.check` y, si falla, cae a la plantilla determinista en vez de
    arriesgar una alucinación."""
    if not used_llm:
        return parts
    errors = check(parts, ledger, locale)
    if errors:
        logger.warning("compose failed the grounding check", codes=[error.code for error in errors])
        return fallback("answer", ledger, locale)
    return parts


def assemble(parts: list[Part], ledger: Ledger, locale: str) -> str:
    """Determinista: empaqueta las partes en el `text` plano que
    `core.messaging.Message` sabe guardar hoy (Opción A). El `view`, cuando
    existe, queda calculado en `state.view` pero no se transmite todavía;
    `Ask`, en cambio, sí debe sobrevivir al próximo turno, así que se codifica
    como un sufijo (ver el docstring del módulo)."""
    rendered = render(parts, ledger, locale)
    say_text = "\n\n".join(item["text"] for item in rendered if item["type"] == "say")
    ask_part = next((part for part in parts if isinstance(part, Ask)), None)
    return _encode_ask(say_text, ask_part)


def _encode_ask(text: str, ask: Ask | None) -> str:
    if ask is None:
        return text
    tag = json.dumps(ask.to_wire(), separators=(",", ":"), ensure_ascii=False)
    return f"{text}{ASK_TAG_START}{tag}{ASK_TAG_END}"


def _decode_ask(text: str) -> Ask | None:
    start = text.rfind(ASK_TAG_START)
    if start == -1 or not text.endswith(ASK_TAG_END):
        return None
    raw = text[start + len(ASK_TAG_START) : -len(ASK_TAG_END)]
    try:
        wire = json.loads(raw)
        if not isinstance(wire, dict):
            return None
        [part] = parse_parts([wire])
    except (json.JSONDecodeError, InvalidPart, ValueError):
        return None
    return part if isinstance(part, Ask) else None


# ---------------------------------------------------------------------------
# the turn, end to end
# ---------------------------------------------------------------------------


def _locale_of(language: object, country: str) -> str:
    if language in ("es", "pt-BR", "en"):
        return str(language)
    raw = LANGUAGES.get(country, "en-US")
    return raw if raw == "pt-BR" else raw.split("-")[0]


def run_turn(
    message: Message, messaging: Messaging, dynamodb: "DynamoDBServiceResource", service: str
) -> str:
    """Orchestrates the pipeline documented at the top of this module and
    returns the plain text `handler.answer` writes as the reply. ``ingress``
    (sender/room checks) stays in `handler.py`, unchanged; the write to
    `core.messaging` and the `turn.completed` event also stay there,
    unchanged."""
    customer = read_customer(dynamodb, message.customer_id) or {}
    country = str(customer.get("country") or "PE")
    locale = _locale_of(customer.get("language"), country)

    state = TurnState(
        customer_id=message.customer_id,
        country=country,
        language=locale,
        room_id=message.room_id,
        message_text=message.text,
    )

    load_prior_ask(state, messaging)
    resolved = resolve_ask(state)

    now = datetime.now(UTC)
    context = ToolContext(customer_id=message.customer_id, country=country, language=locale, now=now, service=service)
    state.ledger = Ledger(country=country, now=now)

    if not resolved:
        classify(state)
        extract(state)
        retrieve(state, context)
        decide(state)

    act(state, context, dynamodb)

    parts, used_llm = compose(state, locale)
    parts = egress(parts, state.ledger, locale, used_llm)
    return assemble(parts, state.ledger, locale)