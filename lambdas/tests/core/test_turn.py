import re
from datetime import UTC, datetime, timedelta

import pytest

from clara_testing.converse import FakeConverse
from core.answers import REFUSALS
from core.facts.fallback import TEMPLATES
from core.messaging import customer_message
from core.turn import run_turn
from harness import Aws, demo_account, uuid7

NOW = datetime(2026, 9, 20, 17, 0, tzinfo=UTC)
CUSTOMER = "c0ffee00-0000-4000-8000-0000000000c1"

SAFETY = {
    (
        "PE",
        "es",
        "no fui yo",
    ): "Si no hiciste esa compra, protege tu tarjeta ahora: llama al banco al +51 1 600 2000 "
    "(las 24 horas, todos los días); desde el exterior, al +51 1 600 2001. "
    "En esa llamada una persona del banco te ayuda a bloquearla.",
    (
        "PE",
        "es",
        "me robaron la tarjeta",
    ): "Si perdiste tu tarjeta o te la robaron, protégela ahora: llama al banco "
    "al +51 1 600 2000 (las 24 horas, todos los días); desde el exterior, al +51 1 600 2001. "
    "En esa llamada una persona del banco te ayuda a bloquearla.",
    (
        "BR",
        "pt-BR",
        "não fui eu",
    ): "Se você não fez essa compra, proteja seu cartão agora: ligue para o banco no "
    "+55 11 4000 2000 (24 horas, todos os dias); do exterior, no +55 11 4000 2001. "
    "Nessa ligação uma pessoa do banco ajuda você a bloqueá-lo.",
    (
        "BR",
        "pt-BR",
        "me roubaram o cartão",
    ): "Se você perdeu seu cartão ou ele foi roubado, proteja-o agora: ligue "
    "para o banco no +55 11 4000 2000 (24 horas, todos os dias); do exterior, no +55 11 4000 2001. "
    "Nessa ligação uma pessoa do banco ajuda você a bloqueá-lo.",
}


@pytest.mark.parametrize(("case", "expected"), list(SAFETY.items()))
def test_a_floor_hit_answers_with_the_safety_template_of_the_country_without_the_model(
    aws: Aws, case: tuple[str, str, str], expected: str
) -> None:
    country, language, text = case
    demo_account(aws, CUSTOMER, country, language, NOW - timedelta(hours=1))
    model = FakeConverse([])
    message = customer_message(CUSTOMER, uuid7(), uuid7(int(NOW.timestamp() * 1000)), text, NOW)

    result = run_turn(message, [], NOW, clients=model.client)

    assert result.reply.text == expected
    assert result.reply.source == "safety"
    assert result.summary()["route"] == "safety"
    assert model.requests == []


def test_a_customer_without_a_finished_setup_gets_the_unavailable_answer(aws: Aws) -> None:
    aws.customers.put_item(
        Item={"customer_id": CUSTOMER, "email": "a@example.com", "created_at": "2026-01-01"}
    )
    model = FakeConverse([])
    message = customer_message(CUSTOMER, uuid7(), uuid7(int(NOW.timestamp() * 1000)), "hola", NOW)

    result = run_turn(message, [], NOW, clients=model.client)

    assert result.reply.source == "fallback"
    assert model.requests == []


def test_no_fallback_or_refusal_offers_a_person_clara_cannot_hand_over_to() -> None:
    texts = [text for template in TEMPLATES.values() for text in template.values()]
    texts += [text for template in REFUSALS.values() for text in template.values()]

    assert not [text for text in texts if re.search(r"persona|pessoa|person\b", text)]
    assert not [text for text in texts if re.search(r"\bapp\b", text)]
