import re
from datetime import UTC, datetime, timedelta

import pytest

from clara_testing.converse import FakeConverse
from core.answers import REFUSALS
from core.facts.fallback import TEMPLATES
from core.graphs.profiles import profiles
from core.messaging import customer_message
from core.turn import run_turn
from harness import Aws, demo_account, uuid7

NOW = datetime(2026, 9, 20, 17, 0, tzinfo=UTC)
CUSTOMER = "c0ffee00-0000-4000-8000-0000000000c1"


@pytest.mark.parametrize(
    ("country", "language", "text", "said", "prompt"),
    [
        (
            "PE",
            "es",
            "no fui yo",
            "Vamos a proteger tu tarjeta. Elige el movimiento",
            "¿Cuál movimiento no hiciste?",
        ),
        (
            "BR",
            "pt-BR",
            "não fui eu",
            "Vamos proteger seu cartão. Escolha a movimentação",
            "Qual movimentação",
        ),
    ],
)
def test_a_bare_not_me_lists_the_newest_movements_to_pick_without_the_model(
    aws: Aws, country: str, language: str, text: str, said: str, prompt: str
) -> None:
    demo_account(aws, CUSTOMER, country, language, NOW - timedelta(hours=1))
    model = FakeConverse([])
    message = customer_message(CUSTOMER, uuid7(), uuid7(int(NOW.timestamp() * 1000)), text, NOW)

    result = run_turn(message, [], NOW, profile=profiles()[0], clients=model.client)

    assert result.reply.text.startswith(said)
    [ask] = [part for part in result.reply.parts if part["type"] == "ask"]
    assert ask["ask"] == "which_one"
    assert ask["prompt"].startswith(prompt)
    assert len(ask["options"]) == 5
    [drafted] = [part for part in result.reply.draft if part["type"] == "ask"]
    assert drafted["purpose"] == "not_me"
    assert [part["view"] for part in result.reply.parts if part["type"] == "view"] == ["movements"]
    assert (result.summary()["route"], result.floor) == ("safety", "not_me")
    assert model.requests == []


@pytest.mark.parametrize(
    ("country", "language", "text", "said"),
    [
        (
            "PE",
            "es",
            "me robaron la tarjeta",
            "Vamos a proteger tu tarjeta. Elige cuál perdiste o te robaron.",
        ),
        (
            "BR",
            "pt-BR",
            "me roubaram o cartão",
            "Vamos proteger seu cartão. Escolha qual você perdeu ou foi roubado.",
        ),
    ],
)
def test_a_lost_card_lists_every_card_and_asks_which_active_one_even_with_one(
    aws: Aws, country: str, language: str, text: str, said: str
) -> None:
    account = demo_account(aws, CUSTOMER, country, language, NOW - timedelta(hours=1))
    for card in account.cards[1:]:
        aws.products.update_item(
            Key={"customer_id": CUSTOMER, "product_id": card["product_id"]},
            UpdateExpression="SET product_status = :blocked",
            ExpressionAttributeValues={":blocked": "Blocked"},
        )
    model = FakeConverse([])
    message = customer_message(CUSTOMER, uuid7(), uuid7(int(NOW.timestamp() * 1000)), text, NOW)

    result = run_turn(message, [], NOW, profile=profiles()[0], clients=model.client)

    assert result.reply.text == said
    [view] = [part for part in result.reply.parts if part["type"] == "view"]
    assert view["view"] == "cards"
    assert len(view["items"]) == len(account.cards)
    [ask] = [part for part in result.reply.parts if part["type"] == "ask"]
    assert [option["id"] for option in ask["options"]] == [account.cards[0]["product_id"]]
    assert model.requests == []


def test_a_customer_without_a_finished_setup_gets_the_unavailable_answer(aws: Aws) -> None:
    aws.customers.put_item(
        Item={"customer_id": CUSTOMER, "email": "a@example.com", "created_at": "2026-01-01"}
    )
    model = FakeConverse([])
    message = customer_message(CUSTOMER, uuid7(), uuid7(int(NOW.timestamp() * 1000)), "hola", NOW)

    result = run_turn(message, [], NOW, profile=profiles()[0], clients=model.client)

    assert result.reply.source == "fallback"
    assert model.requests == []


def test_no_fallback_or_refusal_offers_a_person_clara_cannot_hand_over_to() -> None:
    texts = [text for template in TEMPLATES.values() for text in template.values()]
    texts += [text for template in REFUSALS.values() for text in template.values()]

    assert not [text for text in texts if re.search(r"persona|pessoa|person\b", text)]
    assert not [text for text in texts if re.search(r"\bapp\b", text)]
