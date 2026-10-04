import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from moto.iam.access_control import IAMPolicy, PermissionResult

from clara_testing.converse import FakeConverse, reply, response, tool_use
from core import access, rules
from core.access import READ_ONLY_POLICY
from core.accounts import transaction_key
from core.graphs.profiles import profiles
from core.messaging import Message, customer_message, reply_to
from core.turn import Turn, run_turn
from harness import Aws, DemoAccount, demo_account, uuid7

NOW = datetime(2026, 9, 20, 17, 0, tzinfo=UTC)
CUSTOMER = "c0ffee00-0000-4000-8000-0000000000d1"
DEFAULT = profiles()[0]
EXPLAINED = "Tu compra en {f6.charge.merchant} por {f6.charge.amount} fue {f6.charge.date}."


def explained(fact: str) -> str:
    return EXPLAINED.replace("{f6.", "{" + fact + ".")


@pytest.fixture
def account(aws: Aws) -> DemoAccount:
    return demo_account(aws, CUSTOMER, "PE", "es", NOW - timedelta(hours=1))


@pytest.fixture
def assumed(aws: Aws, monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    assume_role = access._sts.assume_role

    def recording(**request: Any) -> Any:
        requests.append(request)
        return assume_role(**request)

    access._sessions.clear()
    monkeypatch.setattr(access._sts, "assume_role", recording)
    return requests


def at(offset: timedelta) -> datetime:
    return NOW - offset


def says(text: str, room: str, sent: datetime, **input: Any) -> Message:
    return customer_message(
        CUSTOMER, room, uuid7(int(sent.timestamp() * 1000)), text, sent, input=input or None
    )


def newest(account: DemoAccount) -> list[dict[str, Any]]:
    rows = sorted(account.transactions, key=lambda item: (item["transaction_date"], item["transaction_id"]))
    return rows[-5:][::-1]


def quiet(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return next(row for row in rows if Decimal(str(row.get("fraud_score", 0))) <= 30)


def flag(aws: Aws, row: dict[str, Any]) -> None:
    aws.transactions.update_item(
        Key={
            "customer_id": CUSTOMER,
            "transaction_key": transaction_key(row["product_id"], row["transaction_id"]),
        },
        UpdateExpression="SET fraud_score = :score",
        ExpressionAttributeValues={":score": Decimal("88")},
    )


def part(result: Turn, kind: str) -> dict[str, Any]:
    [found] = [item for item in result.reply.parts if item["type"] == kind]
    return found


def context_of(model: FakeConverse, index: int = 0) -> dict[str, Any]:
    text = model.requests[index]["system"][2]["text"].split("\n", 2)[2]
    context: dict[str, Any] = json.loads(text)
    return context


def recorded(result: Turn, message: Message) -> Message:
    return reply_to(
        message,
        "assistant",
        result.reply.text,
        NOW,
        result.reply.parts,
        result.reply.facts,
        result.reply.draft,
    )


def picked(
    account: DemoAccount, row: dict[str, Any], remembered: int = 0
) -> tuple[Turn, Message, list[Message], FakeConverse]:
    room = uuid7()
    first_row = 6 + remembered
    rows = [f"f{first_row + index}" for index in range(5)]
    question = says("hay una transacción que no reconozco", room, at(timedelta(minutes=3)))
    asking = FakeConverse(
        [
            response(tool_use("search_movements", {"limit": 5})),
            response(
                tool_use(
                    "reply",
                    {
                        "say": ["Estos son tus movimientos más recientes. ¿Cuál no reconoces?"],
                        "ask": {"type": "which_one", "facts": rows},
                    },
                )
            ),
        ]
    )
    first = run_turn(question, [], NOW, profile=DEFAULT, clients=asking.client)
    asked = recorded(first, question)
    label = next(o["label"] for o in part(first, "ask")["options"] if o["id"] == row["transaction_id"])
    tap = says(label, room, at(timedelta(minutes=2)), ask_id=asked.message_id, option=row["transaction_id"])
    charge = f"f{first_row}"
    answering = FakeConverse(
        [
            response(
                tool_use("reply", {"say": [explained(charge)], "view": {"type": "charge", "facts": [charge]}})
            )
        ]
    )
    result = run_turn(tap, [question, asked], NOW, profile=DEFAULT, clients=answering.client)
    return result, tap, [question, asked], answering


def answered(
    history: list[Message], last: Message, result: Turn, text: str, **input: Any
) -> tuple[Turn, Message, FakeConverse]:
    asked = recorded(result, last)
    message = says(
        text,
        last.room_id,
        at(timedelta(minutes=1)),
        **({"ask_id": asked.message_id, **input} if input else {}),
    )
    model = FakeConverse([reply("Listo.")])
    return (
        run_turn(message, [*history, last, asked], NOW, profile=DEFAULT, clients=model.client),
        message,
        model,
    )


def memory_rows(aws: Aws) -> dict[str, dict[str, Any]]:
    return {str(item["memory_key"]): item for item in aws.memory.scan()["Items"]}


def test_a_charge_picked_from_the_newest_movements_is_explained_then_the_bank_asks_if_it_is_recognized(
    account: DemoAccount,
) -> None:
    row = quiet(newest(account))

    result, _, _, model = picked(account, row)

    assert result.route == "choice"
    assert part(result, "view")["view"] == "charge"
    ask = part(result, "ask")
    assert ask == {
        "type": "ask",
        "ask": "recognize_charge",
        "options": [{"id": "yes", "label": "Sí, fui yo"}, {"id": "no", "label": "No lo reconozco"}],
        "prompt": "¿Reconoces este cargo?",
        "note": True,
    }
    [drafted] = [item for item in result.reply.draft if item["type"] == "ask"]
    assert drafted["target"] == {"product_id": row["product_id"], "transaction_id": row["transaction_id"]}
    assert context_of(model)["story"] == {"ask": "recognize_charge", "charge": "f6", "open": False}
    assert result.summary()["tool_calls"] == []


def test_on_a_turn_where_the_bank_asks_its_question_is_the_only_ask(account: DemoAccount) -> None:
    row = quiet(newest(account))
    room = uuid7()
    topic = {"type": "charge", "product_id": row["product_id"], "transaction_id": row["transaction_id"]}
    message = says("No reconozco este cargo.", room, at(timedelta(minutes=1)), topic=topic)
    model = FakeConverse(
        [
            response(tool_use("reply", {"say": [EXPLAINED], "ask": {"type": "show", "facts": ["f2"]}})),
            response(
                tool_use("reply", {"say": [EXPLAINED], "ask": {"type": "recognize_charge", "facts": ["f6"]}})
            ),
        ]
    )

    result = run_turn(message, [], NOW, profile=DEFAULT, clients=model.client)

    assert result.summary()["check"]["errors"] == ["ask_not_allowed"]
    assert [item["ask"] for item in result.reply.parts if item["type"] == "ask"] == ["recognize_charge"]
    assert [item.get("target") for item in result.reply.draft if item["type"] == "ask"] == [
        {"product_id": row["product_id"], "transaction_id": row["transaction_id"]}
    ]


def test_the_bank_s_charge_button_opens_the_charge_without_a_search_and_asks(account: DemoAccount) -> None:
    row = quiet(account.transactions[::-1])
    topic = {"type": "charge", "product_id": row["product_id"], "transaction_id": row["transaction_id"]}
    message = says("No reconozco el cargo.", uuid7(), at(timedelta(minutes=1)), topic=topic)
    model = FakeConverse(
        [response(tool_use("reply", {"say": [EXPLAINED], "view": {"type": "charge", "facts": ["f6"]}}))]
    )

    result = run_turn(message, [], NOW, profile=DEFAULT, clients=model.client)

    assert result.route == "topic"
    assert context_of(model)["topic"]["facts"][0]["kind"] == "charge"
    assert part(result, "ask")["ask"] == "recognize_charge"
    assert part(result, "view")["items"] == [
        {"product_id": row["product_id"], "transaction_id": row["transaction_id"]}
    ]


def test_a_topic_on_a_charge_the_card_does_not_hold_is_free_text(aws: Aws, account: DemoAccount) -> None:
    row = quiet(account.transactions[::-1])
    other_card = next(card["product_id"] for card in account.cards if card["product_id"] != row["product_id"])
    topic = {"type": "charge", "product_id": other_card, "transaction_id": row["transaction_id"]}
    message = says("No reconozco el cargo.", uuid7(), at(timedelta(minutes=1)), topic=topic)
    model = FakeConverse([reply("¿Me dices la fecha del cargo?")])

    result = run_turn(message, [], NOW, profile=DEFAULT, clients=model.client)

    assert context_of(model)["topic"] is None
    assert context_of(model)["story"] is None
    assert not [item for item in result.reply.parts if item["type"] == "ask"]


def test_a_flagged_charge_is_not_asked_here(aws: Aws, account: DemoAccount) -> None:
    row = quiet(newest(account))
    flag(aws, row)

    result, _, _, model = picked(account, row)

    assert context_of(model)["story"] is None
    assert not [item for item in result.reply.parts if item["type"] == "ask"]


def test_yes_with_a_note_is_remembered_by_the_rules_without_the_model(
    aws: Aws, account: DemoAccount, assumed: list[dict[str, Any]]
) -> None:
    row = quiet(newest(account))
    first, tap, history, _ = picked(account, row)
    assumed.clear()

    result, message, model = answered(
        history, tap, first, "Sí, fui yo", option="yes", note="  era la gasolina del viaje "
    )

    assert model.requests == []
    assert result.route == "story"
    assert result.reply.source == "story"
    assert result.reply.text == "Gracias, lo anoto: reconoces este cargo y no volveré a preguntarte por él."
    stored = memory_rows(aws)[f"recognized_charge#{row['transaction_id']}"]
    assert stored["note"] == "era la gasolina del viaje"
    assert stored["source_room_id"] == message.room_id
    assert stored["ask_id"] == recorded(first, tap).message_id
    assert stored["merchant"] == row["merchant_name"]
    assert stored["created_at"] == "2026-09-20T17:00:00.000Z"
    assert [request.get("Policy") for request in assumed] == [None]


def test_no_is_remembered_and_answered_with_the_bank_s_phone(aws: Aws, account: DemoAccount) -> None:
    row = quiet(newest(account))
    first, tap, history, _ = picked(account, row)

    result, _, _ = answered(history, tap, first, "No lo reconozco", option="no")

    assert set(memory_rows(aws)) == {f"unrecognized_charge#{row['transaction_id']}"}
    assert result.reply.text.startswith(
        "Si no hiciste esa compra, protege tu tarjeta ahora: llama al banco al "
    )


@pytest.mark.parametrize(
    ("text", "kind", "note"),
    [
        ("sí, era la gasolina del viaje", "recognized_charge", "era la gasolina del viaje"),
        ("Sí fui yo.", "recognized_charge", None),
        ("no, nunca compré ahí", "unrecognized_charge", "nunca compré ahí"),
        ("creo que no fui yo", "unrecognized_charge", None),
    ],
)
def test_a_short_answer_or_a_typed_not_me_closes_the_open_ask(
    aws: Aws, account: DemoAccount, text: str, kind: str, note: str | None
) -> None:
    row = quiet(newest(account))
    first, tap, history, _ = picked(account, row)

    result, _, model = answered(history, tap, first, text)

    assert model.requests == []
    assert result.route == "story"
    stored = memory_rows(aws)[f"{kind}#{row['transaction_id']}"]
    assert stored.get("note") == note


@pytest.mark.parametrize("text", ["creo que sí, fui yo", "¿sí?", "si no lo reconozco, ¿qué hago?"])
def test_a_yes_the_rules_cannot_read_never_writes_and_the_question_stays(
    aws: Aws, account: DemoAccount, text: str
) -> None:
    row = quiet(newest(account))
    first, tap, history, _ = picked(account, row)

    result, _, model = answered(history, tap, first, text)

    assert memory_rows(aws) == {}
    assert result.route == "open_mode"
    assert context_of(model)["story"]["open"] is True
    assert part(result, "ask")["ask"] == "recognize_charge"


def test_closing_is_idempotent_per_ask_on_redelivery(aws: Aws, account: DemoAccount) -> None:
    row = quiet(newest(account))
    first, tap, _, _ = picked(account, row)
    asked = recorded(first, tap)
    pending = rules.open_ask(asked)
    assert pending is not None
    message = says("Sí, fui yo", tap.room_id, at(timedelta(minutes=1)), ask_id=asked.message_id, option="yes")
    answer = rules.answer_of(message, pending)
    assert answer is not None

    once = rules.close_ask(answer, message, NOW, "chatbot")
    again = rules.close_ask(answer, message, NOW + timedelta(seconds=30), "chatbot")
    other = rules.close_ask(replace(answer, ask=replace(pending, ask_id=uuid7())), message, NOW, "chatbot")

    assert (once.outcome, again.outcome, other.outcome) == ("written", "redelivered", "already")
    [stored] = memory_rows(aws).values()
    assert stored["created_at"] == "2026-09-20T17:00:00.000Z"


def test_a_tap_on_an_older_ask_never_writes(aws: Aws, account: DemoAccount) -> None:
    row = quiet(newest(account))
    first, tap, history, _ = picked(account, row)
    closed, message, _ = answered(history, tap, first, "Sí, fui yo", option="yes")
    late = says(
        "No lo reconozco",
        tap.room_id,
        at(timedelta(seconds=30)),
        ask_id=recorded(first, tap).message_id,
        option="no",
    )
    model = FakeConverse([reply("Listo.")])

    result = run_turn(
        late,
        [*history, tap, recorded(first, tap), message, recorded(closed, message)],
        NOW,
        profile=DEFAULT,
        clients=model.client,
    )

    assert result.route == "open_mode"
    assert set(memory_rows(aws)) == {f"recognized_charge#{row['transaction_id']}"}


def test_a_remembered_charge_is_never_asked_again_and_its_note_answers(
    aws: Aws, account: DemoAccount
) -> None:
    row = quiet(newest(account))
    first, tap, history, _ = picked(account, row)
    answered(history, tap, first, "Sí, fui yo", option="yes", note="la gasolina del viaje")
    topic = {"type": "charge", "product_id": row["product_id"], "transaction_id": row["transaction_id"]}
    message = says("¿Qué es este cargo?", uuid7(), at(timedelta(seconds=10)), topic=topic)
    model = FakeConverse(
        [
            response(
                tool_use(
                    "reply",
                    {"say": ["Ya me dijiste que reconoces este cargo: \u201c{f7.memory.note}\u201d."]},
                )
            )
        ]
    )

    result = run_turn(message, [], NOW, profile=DEFAULT, clients=model.client)

    context = context_of(model)
    assert context["story"] is None
    assert context["memories"][0]["fact"] == "f6"
    assert "«la gasolina del viaje»" in context["memories"][0]["says"]
    assert result.reply.text == "Ya me dijiste que reconoces este cargo: «la gasolina del viaje»."
    assert not [item for item in result.reply.parts if item["type"] == "ask"]


def test_three_recognized_charges_at_one_merchant_teach_the_merchant_and_never_soften_its_alert(
    aws: Aws, account: DemoAccount
) -> None:
    by_merchant: dict[str, list[dict[str, Any]]] = {}
    for item in account.transactions:
        if item["transaction_status"] == "Approved":
            by_merchant.setdefault(item["merchant_name"], []).append(item)
    rows = next(items for items in by_merchant.values() if len(items) >= 5)
    room = uuid7()
    for index, row in enumerate(rows[:3]):
        asked = Message(
            CUSTOMER, room, uuid7(), "assistant", "", "2026-09-20T16:00:00.000Z", "2026-09-20T16:00:00.000Z"
        )
        pending = rules.OpenAsk(
            asked.message_id, rules.RECOGNIZE, rules.Target(row["product_id"], row["transaction_id"])
        )
        message = says("sí", room, at(timedelta(minutes=10 - index)))
        answer = rules.answer_of(message, pending)
        assert answer is not None
        closing = rules.close_ask(answer, message, NOW, "chatbot")
        assert closing.merchant_learned is (index == 2)
    flagged, quiet_one = rows[3], rows[4]
    flag(aws, flagged)
    model = FakeConverse(
        [
            response(
                tool_use("charge_facts", {"transaction_ref": flagged["transaction_id"]}),
                tool_use("charge_facts", {"transaction_ref": quiet_one["transaction_id"]}),
            ),
            reply("Listo."),
        ]
    )

    run_turn(
        says("¿qué son estos cargos?", room, at(timedelta(minutes=1))),
        [],
        NOW,
        profile=DEFAULT,
        clients=model.client,
    )

    assert any(key.startswith("recognized_merchant#") for key in memory_rows(aws))
    facts = json.loads(model.requests[1]["messages"][-1]["content"][0]["toolResult"]["content"][0]["text"])[
        "facts"
    ]
    flagged_fact = facts[0]["fields"]
    assert flagged_fact["verdict.reasons"]["values"][0] == "score_high"
    assert flagged_fact["merchant_recognized"]["value"] is True


def test_the_merchant_never_suppresses_the_question_on_a_charge_not_yet_answered(
    aws: Aws, account: DemoAccount
) -> None:
    rows = newest(account)
    row = quiet(rows)
    aws.memory.put_item(
        Item={
            "customer_id": CUSTOMER,
            "memory_key": f"recognized_merchant#{row['merchant_name'].lower()}",
            "type": "recognized_merchant",
            "subject": row["merchant_name"],
            "created_at": "2026-09-19T12:00:00.000Z",
        }
    )

    result, _, _, model = picked(account, row, remembered=1)

    assert result.reply.source == "composed"
    assert context_of(model)["story"]["charge"] == "f7"
    assert part(result, "ask")["ask"] == "recognize_charge"


def test_up_to_five_memories_enter_the_context_newest_first(aws: Aws, account: DemoAccount) -> None:
    rows = account.transactions[:7]
    for day, row in enumerate(rows, start=1):
        aws.memory.put_item(
            Item={
                "customer_id": CUSTOMER,
                "memory_key": f"recognized_charge#{row['transaction_id']}",
                "type": "recognized_charge",
                "subject": row["transaction_id"],
                "note": f"nota {day}",
                "created_at": f"2026-09-{day:02d}T12:00:00.000Z",
                "merchant": row["merchant_name"],
                "product_id": row["product_id"],
                "amount": row["amount"],
                "currency": row["currency"],
                "charged_at": row["transaction_date"],
            }
        )
    model = FakeConverse([reply("Listo.")])

    run_turn(says("hola", uuid7(), at(timedelta(seconds=5))), [], NOW, profile=DEFAULT, clients=model.client)

    memories = context_of(model)["memories"]
    assert [entry["fact"] for entry in memories] == ["f6", "f7", "f8", "f9", "f10"]
    assert memories[0]["says"].startswith(f"Reconociste tu cargo en {rows[6]['merchant_name']} por ")
    assert memories[0]["says"].endswith("Me dijiste: «nota 7».")


def test_every_graph_turn_reads_only_with_the_read_only_session(
    account: DemoAccount, assumed: list[dict[str, Any]]
) -> None:
    row = quiet(newest(account))
    first, tap, history, _ = picked(account, row)
    answered(history, tap, first, "creo que sí")
    topic = {"type": "charge", "product_id": row["product_id"], "transaction_id": row["transaction_id"]}
    model = FakeConverse([reply("Listo.")])
    run_turn(
        says("No lo reconozco", uuid7(), at(timedelta(seconds=5)), topic=topic),
        [],
        NOW,
        profile=DEFAULT,
        clients=model.client,
    )

    assert assumed
    assert all(request["Policy"] == READ_ONLY_POLICY for request in assumed)
    policy = IAMPolicy(READ_ONLY_POLICY)
    for table in ("memory", "products"):
        arn = f"arn:aws:dynamodb:us-east-1:123456789012:table/clara-test-{table}"
        for action in ("dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:BatchWriteItem"):
            assert policy.is_action_permitted(action, arn) != PermissionResult.PERMITTED


def test_the_rules_refuse_the_question_on_a_flagged_charge_without_sending_the_reply_back(
    aws: Aws, account: DemoAccount
) -> None:
    row = quiet(newest(account))
    flag(aws, row)
    model = FakeConverse(
        [
            response(tool_use("charge_facts", {"transaction_ref": row["transaction_id"]})),
            response(
                tool_use("reply", {"say": [EXPLAINED], "ask": {"type": "recognize_charge", "facts": ["f6"]}})
            ),
        ]
    )

    result = run_turn(
        says("no reconozco este cargo", uuid7(), at(timedelta(seconds=5))),
        [],
        NOW,
        profile=DEFAULT,
        clients=model.client,
    )

    assert result.reply.source == "composed"
    assert result.summary()["check"]["tidied"] == {"ask_refused": 1}
    assert not [item for item in result.reply.parts if item["type"] == "ask"]
