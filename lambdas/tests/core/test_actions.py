import re
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from clara_testing.converse import FakeConverse, composed, reply, response, throttled, tool_use
from core.accounts import Accounts, transaction_key
from core.graphs.profiles import profiles
from core.messaging import Message, customer_message, reply_to
from core.turn import Turn, run_turn
from harness import Aws, DemoAccount, demo_account, uuid7

NOW = datetime(2026, 9, 20, 17, 0, tzinfo=UTC)
CUSTOMER = "c0ffee00-0000-4000-8000-0000000000a1"
DEFAULT = profiles()[0]
EXPLAINED = "Tu compra en {f6.charge.merchant} por {f6.charge.amount} fue {f6.charge.date}."


@pytest.fixture
def account(aws: Aws) -> DemoAccount:
    return demo_account(aws, CUSTOMER, "PE", "es", NOW - timedelta(hours=1))


class Chat:
    def __init__(self, aws: Aws) -> None:
        self.aws = aws
        self.room = uuid7()
        self.history: list[Message] = []
        self.minute = 30

    def send(self, text: str, *responses: Any, **input: Any) -> tuple[Turn, FakeConverse]:
        self.minute -= 1
        sent = NOW - timedelta(minutes=self.minute)
        message = customer_message(
            CUSTOMER, self.room, uuid7(int(sent.timestamp() * 1000)), text, sent, input=input or None
        )
        model = FakeConverse(list(responses))
        result = run_turn(message, list(self.history), NOW, profile=DEFAULT, clients=model.client)
        self.history += [message, self.recorded(result, message)]
        return result, model

    def tap(
        self, result: Turn, option: str, *responses: Any, note: str | None = None
    ) -> tuple[Turn, FakeConverse]:
        asked = self.history[-1]
        label = next(item["label"] for item in ask_of(result)["options"] if item["id"] == option)
        extra = {"note": note} if note else {}
        return self.send(label, *responses, ask_id=asked.message_id, option=option, **extra)

    def redeliver(self, *responses: Any) -> tuple[Turn, FakeConverse]:
        message = self.history[-2]
        model = FakeConverse(list(responses))
        return run_turn(message, list(self.history[:-2]), NOW, profile=DEFAULT, clients=model.client), model

    @staticmethod
    def recorded(result: Turn, message: Message) -> Message:
        reply = result.reply
        return reply_to(
            message,
            "assistant",
            reply.text,
            NOW,
            reply.parts,
            reply.facts,
            reply.draft,
            reply.source,
            reply.effects,
        )


def ask_of(result: Turn) -> dict[str, Any]:
    [found] = [item for item in result.reply.parts if item["type"] == "ask"]
    return found


def views(result: Turn) -> list[str]:
    return [item["view"] for item in result.reply.parts if item["type"] == "view"]


def target_of(result: Turn) -> dict[str, Any]:
    [drafted] = [item for item in result.reply.draft if item["type"] == "ask"]
    return dict(drafted.get("target") or {})


def quiet(account: DemoAccount) -> dict[str, Any]:
    rows = sorted(account.transactions, key=lambda item: (item["transaction_date"], item["transaction_id"]))
    return next(
        row
        for row in reversed(rows)
        if Decimal(str(row.get("fraud_score", 0))) <= 30
        and row["transaction_status"] == "Approved"
        and row["channel"] == "POS"
        and row["transaction_country"] == account.country
    )


def flag(aws: Aws, row: Mapping[str, Any]) -> None:
    aws.transactions.update_item(
        Key={
            "customer_id": CUSTOMER,
            "transaction_key": transaction_key(row["product_id"], row["transaction_id"]),
        },
        UpdateExpression="SET fraud_score = :score",
        ExpressionAttributeValues={":score": Decimal("88")},
    )


def block_card_row(aws: Aws, product_id: str) -> None:
    aws.products.update_item(
        Key={"customer_id": CUSTOMER, "product_id": product_id},
        UpdateExpression="SET product_status = :blocked",
        ExpressionAttributeValues={":blocked": "Blocked"},
    )


def topic(row: Mapping[str, Any]) -> dict[str, str]:
    return {"type": "charge", "product_id": row["product_id"], "transaction_id": row["transaction_id"]}


def explained() -> dict[str, Any]:
    return response(tool_use("reply", {"say": [EXPLAINED], "view": {"type": "charge", "facts": ["f6"]}}))


def card(aws: Aws, product_id: str) -> dict[str, Any]:
    return dict(aws.products.get_item(Key={"customer_id": CUSTOMER, "product_id": product_id})["Item"])


def cases(aws: Aws) -> list[dict[str, Any]]:
    return [item for item in aws.complaints.scan()["Items"] if item.get("reception_channel") == "clara"]


def memory_keys(aws: Aws) -> set[str]:
    return {str(item["memory_key"]) for item in aws.memory.scan()["Items"]}


def flagged_chat(aws: Aws, account: DemoAccount) -> tuple[Chat, Turn, dict[str, Any]]:
    row = quiet(account)
    flag(aws, row)
    chat = Chat(aws)
    asked, _ = chat.send("No reconozco este cargo.", explained(), topic=topic(row))
    return chat, asked, row


def test_the_bank_s_button_on_a_flagged_charge_explains_it_and_asks_was_it_you(
    aws: Aws, account: DemoAccount
) -> None:
    _, asked, row = flagged_chat(aws, account)

    assert asked.route == "topic"
    assert views(asked) == ["charge"]
    ask = ask_of(asked)
    assert (ask["ask"], ask["prompt"]) == ("was_it_you", "¿Fuiste tú?")
    assert [option["label"] for option in ask["options"]] == [
        "Sí, fui yo",
        "No fui yo",
        "¿Por qué me preguntas?",
    ]
    assert target_of(asked) == {"product_id": row["product_id"], "transaction_id": row["transaction_id"]}


def test_why_explains_the_bank_s_reasons_and_asks_again_without_writing(
    aws: Aws, account: DemoAccount
) -> None:
    chat, asked, _ = flagged_chat(aws, account)

    why, model = chat.tap(
        asked, "why", composed("Te pregunto porque el banco notó esto: {f2.verdict.reasons}.")
    )

    assert why.route == "story"
    assert why.reply.text.startswith("Te pregunto porque el banco notó esto: ")
    assert "puntaje" not in why.reply.text.lower()
    assert ask_of(why)["ask"] == "was_it_you"
    assert views(why) == ["charge"]
    assert memory_keys(aws) == set()
    assert len(model.requests) == 1


def test_why_falls_back_to_the_fixed_sentence_when_the_model_writes_a_value(
    aws: Aws, account: DemoAccount
) -> None:
    chat, asked, _ = flagged_chat(aws, account)

    why, _ = chat.tap(asked, "why", composed("El banco le dio 88 puntos."))

    assert why.reply.text.startswith("Te pregunto por tu compra en ")
    assert ask_of(why)["ask"] == "was_it_you"


def test_not_me_on_a_flagged_charge_remembers_it_and_asks_the_fixed_block_confirmation(
    aws: Aws, account: DemoAccount
) -> None:
    chat, asked, row = flagged_chat(aws, account)

    confirm, model = chat.tap(asked, "no")

    assert model.requests == []
    assert memory_keys(aws) == {f"unrecognized_charge#{row['transaction_id']}"}
    assert confirm.reply.effects == ({"type": "charge_answered", "transaction_id": row["transaction_id"]},)
    assert confirm.reply.text.startswith("Puedo bloquear tu tarjeta terminada en ")
    ask = ask_of(confirm)
    assert (ask["ask"], ask["prompt"]) == ("block_card", "¿Quieres que proteja tu tarjeta?")
    assert [option["label"] for option in ask["options"]] == ["Sí, bloquéala", "Ahora no"]
    assert views(confirm) == ["card"]
    assert card(aws, row["product_id"])["product_status"] == "Active"


def test_yes_blocks_reads_back_opens_the_fraud_case_and_shows_the_package(
    aws: Aws, account: DemoAccount
) -> None:
    chat, asked, row = flagged_chat(aws, account)
    confirm, _ = chat.tap(asked, "no")
    ask_id = chat.history[-1].message_id

    done, _ = chat.tap(confirm, "yes", throttled())

    stored = card(aws, row["product_id"])
    assert (stored["product_status"], stored["blocked_by"]) == ("Blocked", ask_id)
    [case] = cases(aws)
    assert (case["complaint_id"], case["area"], case["case_type"], case["status"]) == (
        ask_id,
        "fraud",
        "fraud",
        "Open",
    )
    assert (case["transaction_id"], case["product_id"]) == (row["transaction_id"], row["product_id"])
    assert case["summary_source"] == "template"
    assert case["summary_language"] == "es"
    assert case["summary_points"][0] == "Dice que no hizo este cargo."
    assert any(
        point.startswith("Tarjeta terminada en") and "bloqueada" in point for point in case["summary_points"]
    )
    assert case["summary_points"][-1].startswith("Pregunta abierta: ")
    [noticed] = [point for point in case["summary_points"] if point.startswith("Lo que notó el banco: ")]
    assert "emitió una alerta" in noticed
    assert not [
        point for point in case["summary_points"] if re.search(r"\b(tu|tus|sueles|reconoces)\b", point)
    ]
    assert case["evidence"]["ask_id"] == ask_id
    texts = done.reply.text.split("\n\n")
    assert texts[0].startswith("Listo: tu tarjeta terminada en ")
    assert texts[1].startswith("Abrí el caso CLR-")
    assert "Te contactará una persona del banco" in texts[1]
    assert views(done) == ["case"]
    assert list(done.reply.effects) == [
        {"type": "card_blocked", "product_id": row["product_id"]},
        {"type": "case_opened", "complaint_id": ask_id, "case_type": "fraud"},
    ]
    assert done.summary()["writes"] == ["block", "case", "summary"]


def test_a_composed_summary_is_checked_and_stored_as_compose(aws: Aws, account: DemoAccount) -> None:
    chat, asked, _ = flagged_chat(aws, account)
    confirm, _ = chat.tap(asked, "no")

    chat.tap(
        confirm, "yes", composed("No reconoce el cargo en {f6.charge.merchant}; la tarjeta quedó bloqueada.")
    )

    [case] = cases(aws)
    assert case["summary_source"] == "compose"
    assert case["summary"].startswith("No reconoce el cargo en ")


def test_a_summary_that_speaks_of_the_reasons_to_the_customer_is_stored_from_the_template(
    aws: Aws, account: DemoAccount
) -> None:
    chat, asked, _ = flagged_chat(aws, account)
    confirm, _ = chat.tap(asked, "no")

    chat.tap(confirm, "yes", composed("No reconoce el cargo. Lo que notó el banco: {f6.verdict.reasons}."))

    [case] = cases(aws)
    assert case["summary_source"] == "template"


def test_a_redelivered_confirmation_changes_nothing_and_answers_the_same(
    aws: Aws, account: DemoAccount
) -> None:
    chat, asked, row = flagged_chat(aws, account)
    confirm, _ = chat.tap(asked, "no")
    done, _ = chat.tap(confirm, "yes", throttled())
    before = card(aws, row["product_id"]), cases(aws)

    again, _ = chat.redeliver(throttled())

    assert (card(aws, row["product_id"]), cases(aws)) == before
    assert again.reply.text == done.reply.text
    assert again.reply.effects == done.reply.effects
    assert again.summary()["writes"] == []


def test_a_second_tap_on_the_same_confirmation_writes_nothing(aws: Aws, account: DemoAccount) -> None:
    chat, asked, row = flagged_chat(aws, account)
    confirm, _ = chat.tap(asked, "no")
    chat.tap(confirm, "yes", throttled())
    ask_id = chat.history[-3].message_id
    before = card(aws, row["product_id"]), cases(aws)

    late, _ = chat.send("Sí, bloquéala", reply("Tu tarjeta ya está protegida."), ask_id=ask_id, option="yes")

    assert (card(aws, row["product_id"]), cases(aws)) == before
    assert late.reply.effects == ()
    assert late.route == "open_mode"


def test_a_yes_read_by_the_graph_never_blocks_and_shows_the_confirmation_again(
    aws: Aws, account: DemoAccount
) -> None:
    chat, asked, row = flagged_chat(aws, account)
    chat.tap(asked, "no")

    again, _ = chat.send("dale, hazlo de una vez", reply("Entiendo."))

    assert card(aws, row["product_id"])["product_status"] == "Active"
    assert ask_of(again)["ask"] == "block_card"
    assert target_of(again)["product_id"] == row["product_id"]
    assert cases(aws) == []


@pytest.mark.parametrize(
    "text",
    [
        "Sí, pero no la bloquees todavía",
        "sí, mejor mañana",
        "sí, espera un momento",
        "si, pero primero quiero hablar con alguien",
    ],
)
def test_a_yes_with_anything_after_it_never_blocks_and_shows_the_confirmation_again(
    aws: Aws, account: DemoAccount, text: str
) -> None:
    chat, asked, row = flagged_chat(aws, account)
    chat.tap(asked, "no")

    again, _ = chat.send(text, reply("Entiendo."))

    assert card(aws, row["product_id"])["product_status"] == "Active"
    assert ask_of(again)["ask"] == "block_card"
    assert cases(aws) == []


def test_a_bare_typed_yes_confirms_the_block(aws: Aws, account: DemoAccount) -> None:
    chat, asked, row = flagged_chat(aws, account)
    chat.tap(asked, "no")

    chat.send("sí", throttled())

    assert card(aws, row["product_id"])["product_status"] == "Blocked"


def test_a_yes_with_a_tail_never_opens_a_claim(aws: Aws, account: DemoAccount) -> None:
    chat, asked, _ = quiet_chat(aws, account)
    question, _ = chat.tap(asked, "no")
    chat.tap(question, "yes")

    again, _ = chat.send("sí, pero mañana", reply("Entiendo."))

    assert ask_of(again)["ask"] == "open_claim"
    assert cases(aws) == []


def test_not_now_keeps_the_card_and_opens_nothing(aws: Aws, account: DemoAccount) -> None:
    chat, asked, row = flagged_chat(aws, account)
    confirm, _ = chat.tap(asked, "no")

    declined, _ = chat.tap(confirm, "no", throttled())

    assert declined.reply.text == "Está bien, no la bloqueo. Si cambias de opinión, escríbeme."
    assert card(aws, row["product_id"])["product_status"] == "Active"
    assert cases(aws) == []
    assert declined.reply.effects == ()


def test_a_card_the_bank_blocked_meanwhile_is_not_written_and_the_case_still_opens(
    aws: Aws, account: DemoAccount
) -> None:
    chat, asked, row = flagged_chat(aws, account)
    confirm, _ = chat.tap(asked, "no")
    block_card_row(aws, row["product_id"])

    done, _ = chat.tap(confirm, "yes", throttled())

    assert "blocked_by" not in card(aws, row["product_id"])
    assert done.reply.text.startswith("Tu tarjeta terminada en ")
    assert "ya estaba bloqueada" in done.reply.text.split("\n\n")[0]
    [case] = cases(aws)
    assert any("ya estaba bloqueada" in point for point in case["summary_points"])
    assert [effect["type"] for effect in done.reply.effects] == ["case_opened"]


def test_a_block_that_does_not_read_back_is_never_announced(
    aws: Aws, account: DemoAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    chat, asked, _ = flagged_chat(aws, account)
    confirm, _ = chat.tap(asked, "no")
    monkeypatch.setattr(Accounts, "read_status", lambda self, customer_id, product_id: None)

    done, _ = chat.tap(confirm, "yes", throttled())

    assert done.reply.text.startswith("No pude confirmar el bloqueo de tu tarjeta terminada en ")
    assert "Listo" not in done.reply.text
    assert [effect["type"] for effect in done.reply.effects] == ["case_opened"]
    [case] = cases(aws)
    assert any("no se pudo confirmar" in point for point in case["summary_points"])


def test_not_me_on_a_card_already_blocked_offers_a_person_and_opens_a_fraud_case_without_a_write(
    aws: Aws, account: DemoAccount
) -> None:
    chat, asked, row = flagged_chat(aws, account)
    block_card_row(aws, row["product_id"])

    offer, _ = chat.tap(asked, "no")

    assert ask_of(offer)["ask"] == "talk_to_person"
    assert target_of(offer)["area"] == "fraud"
    handed, _ = chat.tap(offer, "yes", throttled())
    [case] = cases(aws)
    assert case["area"] == "fraud"
    assert "blocked_by" not in card(aws, row["product_id"])
    assert any("ya estaba bloqueada" in point for point in case["summary_points"])
    assert views(handed) == ["case"]


def test_lost_card_pick_blocks_the_chosen_card_with_read_back(aws: Aws, account: DemoAccount) -> None:
    chat = Chat(aws)
    listed, _ = chat.send("me robaron la tarjeta")
    chosen = account.cards[1]["product_id"]

    confirm, _ = chat.tap(listed, chosen)

    assert ask_of(confirm)["ask"] == "block_card"
    assert target_of(confirm) == {"product_id": chosen}
    done, _ = chat.tap(confirm, "yes", throttled())
    assert card(aws, chosen)["product_status"] == "Blocked"
    assert all(
        card(aws, other["product_id"])["product_status"] == "Active"
        for other in account.cards
        if other["product_id"] != chosen
    )
    [case] = cases(aws)
    assert "transaction_id" not in case
    assert case["summary_points"][0] == "Dice que perdió su tarjeta o se la robaron."
    assert done.reply.text.startswith("Listo: tu tarjeta terminada en ")


def test_a_bare_not_me_pick_is_remembered_and_goes_to_the_block_confirmation(
    aws: Aws, account: DemoAccount
) -> None:
    chat = Chat(aws)
    listed, _ = chat.send("no fui yo")
    option = ask_of(listed)["options"][0]["id"]

    confirm, model = chat.tap(listed, option)

    assert model.requests == []
    assert memory_keys(aws) == {f"unrecognized_charge#{option}"}
    assert ask_of(confirm)["ask"] == "block_card"
    assert target_of(confirm)["transaction_id"] == option


def quiet_chat(aws: Aws, account: DemoAccount) -> tuple[Chat, Turn, dict[str, Any]]:
    row = quiet(account)
    chat = Chat(aws)
    asked, _ = chat.send("No reconozco este cargo.", explained(), topic=topic(row))
    assert ask_of(asked)["ask"] == "recognize_charge"
    return chat, asked, row


def test_the_claim_path_asks_about_the_card_then_confirms_and_reads_back_the_case(
    aws: Aws, account: DemoAccount
) -> None:
    chat, asked, row = quiet_chat(aws, account)
    question, _ = chat.tap(asked, "no")
    assert ask_of(question)["ask"] == "have_card"

    consent, _ = chat.tap(question, "yes")
    assert consent.reply.text.startswith("Puedo abrir una aclaración por tu cargo en ")
    assert ask_of(consent)["ask"] == "open_claim"
    assert cases(aws) == []

    opened, _ = chat.tap(consent, "yes", throttled())
    [case] = cases(aws)
    assert (case["area"], case["case_type"], case["transaction_id"]) == (
        "claims",
        "claim",
        row["transaction_id"],
    )
    assert opened.reply.text.startswith("Abrí tu aclaración CLR-")
    assert "Te contactará" not in opened.reply.text
    assert card(aws, row["product_id"])["product_status"] == "Active"


def test_no_card_on_the_claim_question_goes_to_the_block_confirmation(aws: Aws, account: DemoAccount) -> None:
    chat, asked, _ = quiet_chat(aws, account)
    question, _ = chat.tap(asked, "no")

    confirm, _ = chat.tap(question, "no")

    assert ask_of(confirm)["ask"] == "block_card"


def test_a_protect_signal_skips_the_card_question(aws: Aws, account: DemoAccount) -> None:
    row = quiet(account)
    aws.transactions.update_item(
        Key={
            "customer_id": CUSTOMER,
            "transaction_key": transaction_key(row["product_id"], row["transaction_id"]),
        },
        UpdateExpression="SET transaction_country = :abroad",
        ExpressionAttributeValues={":abroad": "US"},
    )
    chat = Chat(aws)
    asked, _ = chat.send("No reconozco este cargo.", explained(), topic=topic(row))

    confirm, _ = chat.tap(asked, "no")

    assert ask_of(confirm)["ask"] == "block_card"


@pytest.mark.parametrize(
    ("text", "reason"),
    [("Desbloquea mi tarjeta", "unblock"), ("¿cuándo me devuelven la plata?", "refund")],
)
def test_unblock_and_money_get_a_person_never_a_write(
    aws: Aws, account: DemoAccount, text: str, reason: str
) -> None:
    chat = Chat(aws)

    abstained, model = chat.send(text, reply("Eso lo hace una persona del banco."))

    assert ask_of(abstained)["ask"] == "talk_to_person"
    assert target_of(abstained) == {"reason": reason, "area": "service"}
    context = model.requests[0]["system"][2]["text"]
    assert f'"abstain":"{reason}"' in context
    assert all(card(aws, item["product_id"])["product_status"] == "Active" for item in account.cards)
    assert cases(aws) == []

    handed, _ = chat.tap(abstained, "yes", throttled())
    [case] = cases(aws)
    assert (case["area"], case["case_type"]) == ("service", "service")
    assert handed.reply.effects == (
        {"type": "case_opened", "complaint_id": case["complaint_id"], "case_type": "service"},
    )
    assert all(card(aws, item["product_id"])["product_status"] == "Active" for item in account.cards)


def test_an_abstention_without_the_model_answers_from_the_template_and_still_offers_a_person(
    aws: Aws, account: DemoAccount
) -> None:
    chat = Chat(aws)

    abstained, _ = chat.send("Desbloquea mi tarjeta", throttled(), throttled())

    assert abstained.reply.text == "Desbloquear una tarjeta lo hace una persona del banco."
    assert ask_of(abstained)["ask"] == "talk_to_person"


def test_the_abstention_lexicon_never_replaces_an_open_safety_ask(aws: Aws, account: DemoAccount) -> None:
    chat, asked, _ = flagged_chat(aws, account)
    chat.tap(asked, "no")

    kept, _ = chat.send("y después me la desbloquean?", reply("Desbloquearla lo hace una persona del banco."))

    assert ask_of(kept)["ask"] == "block_card"


def test_a_claim_proposed_by_the_graph_enters_at_the_card_question(aws: Aws, account: DemoAccount) -> None:
    row = quiet(account)
    chat = Chat(aws)
    proposal = response(
        tool_use(
            "reply",
            {
                "say": [EXPLAINED],
                "view": {"type": "charge", "facts": ["f6"]},
                "ask": {"type": "open_claim", "facts": ["f6"]},
            },
        )
    )

    result, _ = chat.send(
        "me cobraron mal esta compra",
        response(tool_use("charge_facts", {"transaction_ref": row["transaction_id"]})),
        proposal,
    )

    assert ask_of(result)["ask"] == "have_card"
    assert target_of(result)["transaction_id"] == row["transaction_id"]


def test_a_person_asked_about_a_case_names_it_and_the_stored_package_is_the_preview(
    aws: Aws, account: DemoAccount
) -> None:
    chat = Chat(aws)

    abstained, _ = chat.send(
        "¿cuándo me devuelven la plata de mi aclaración?",
        response(tool_use("case_status", {})),
        response(
            tool_use(
                "reply",
                {
                    "say": ["Tu aclaración {f6.case_id} está {f6.stage}."],
                    "view": {"type": "case", "facts": ["f6"]},
                },
            )
        ),
    )

    [handoff] = [part for part in abstained.reply.parts if part.get("view") == "handoff"]
    planted = account.claim
    assert planted is not None
    assert handoff["items"] == [{"complaint_id": planted["complaint_id"]}]
    [request] = handoff["readings"]["points"]
    assert request.startswith("Pregunta por la devolución de su dinero, sobre su caso CLR-")
    assert target_of(abstained)["complaint_id"] == planted["complaint_id"]

    chat.tap(abstained, "yes", throttled())

    [stored] = [case for case in cases(aws) if case["complaint_id"] != planted["complaint_id"]]
    assert stored["summary_points"] == handoff["readings"]["points"]
