import uuid
from datetime import UTC, datetime, timedelta

import boto3
import pytest

from core.ids import uuid7_time
from core.messaging import (
    MAX_TEXT_LENGTH,
    InvalidMessage,
    Message,
    Messaging,
    customer_message,
    reply_to,
)
from harness import Aws, uuid7

CUSTOMER = "c0ffee00-0000-4000-8000-000000000001"


def at(message_id: str) -> datetime:
    return uuid7_time(uuid.UUID(message_id))


def message(room_id: str, message_id: str, text: str = "hola") -> Message:
    return customer_message(CUSTOMER, room_id, message_id, text, at(message_id))


@pytest.fixture
def messaging(aws: Aws) -> Messaging:
    return Messaging.from_dynamodb(boto3.resource("dynamodb"))


def test_sent_at_comes_from_the_message_id() -> None:
    message_id = uuid7(1_790_000_000_123)

    sent = message(uuid7(), message_id)

    assert sent.sent_at == "2026-09-21T14:13:20.123Z"
    assert sent.message_key == f"{sent.room_id}#2026-09-21T14:13:20.123Z#{message_id}"


@pytest.mark.parametrize("skew", [timedelta(minutes=2, seconds=1), -timedelta(minutes=2, seconds=1)])
def test_a_message_id_more_than_two_minutes_from_server_time_is_rejected(skew: timedelta) -> None:
    message_id = uuid7()

    with pytest.raises(InvalidMessage):
        customer_message(CUSTOMER, uuid7(), message_id, "hola", at(message_id) + skew)


def test_a_message_id_within_two_minutes_is_accepted() -> None:
    message_id = uuid7()

    sent = customer_message(CUSTOMER, uuid7(), message_id, "hola", at(message_id) + timedelta(seconds=119))

    assert sent.message_id == message_id


@pytest.mark.parametrize("text", ["", "   ", "x" * (MAX_TEXT_LENGTH + 1)])
def test_empty_or_oversized_text_is_rejected(text: str) -> None:
    with pytest.raises(InvalidMessage):
        message(uuid7(), uuid7(), text)


def test_a_room_id_that_is_not_a_uuid7_is_rejected() -> None:
    with pytest.raises(InvalidMessage):
        message(str(uuid.uuid4()), uuid7())


def test_send_creates_the_room_with_the_first_message_only(aws: Aws, messaging: Messaging) -> None:
    room_id = uuid7()
    first = message(room_id, uuid7())
    messaging.send(first)
    messaging.send(message(room_id, uuid7()))

    rooms = aws.room_items()
    assert len(rooms) == 1
    assert rooms[0]["created_at"] == first.created_at
    assert rooms[0]["delegated_to_human"] is False


def test_a_retried_send_stores_the_message_once_and_returns_the_stored_one(
    aws: Aws, messaging: Messaging
) -> None:
    room_id, message_id = uuid7(), uuid7()
    first = message(room_id, message_id)
    retried = customer_message(CUSTOMER, room_id, message_id, "hola", at(message_id) + timedelta(seconds=30))

    _, created_first = messaging.send(first)
    stored_retry, created_retry = messaging.send(retried)

    assert created_first is True
    assert created_retry is False
    assert stored_retry == first
    assert len(aws.message_items()) == 1


def test_history_is_the_room_in_order_and_nothing_else(messaging: Messaging) -> None:
    room_id, other_room = uuid7(1_790_000_000_000), uuid7(1_790_000_000_001)
    ids = [uuid7(1_790_000_000_000 + offset) for offset in (10, 20, 30)]
    for message_id in reversed(ids):
        messaging.send(message(room_id, message_id))
    messaging.send(message(other_room, uuid7(1_790_000_000_015)))

    history = messaging.history(CUSTOMER, room_id)

    assert [sent.message_id for sent in history] == ids


def test_a_reply_sorts_right_after_the_message_it_answers(messaging: Messaging) -> None:
    room_id = uuid7()
    milliseconds = 1_790_000_000_500
    answered = message(room_id, uuid7(milliseconds))
    same_millisecond = [message(room_id, uuid7(milliseconds)) for _ in range(20)]
    for sent in [answered, *same_millisecond]:
        messaging.send(sent)

    reply, _ = messaging.write(reply_to(answered, "assistant", "hola", datetime.now(UTC)))

    order = [sent.message_id for sent in messaging.history(CUSTOMER, room_id)]
    assert order[order.index(answered.message_id) + 1] == reply.message_id
    assert reply.sent_at == answered.sent_at


def test_a_reply_is_identical_when_computed_again(messaging: Messaging) -> None:
    answered = message(uuid7(), uuid7())
    first = reply_to(answered, "assistant", "hola", datetime.now(UTC))
    again = reply_to(answered, "assistant", "hola", datetime.now(UTC) + timedelta(seconds=5))

    messaging.write(first)
    stored, created = messaging.write(again)

    assert again.message_key == first.message_key
    assert created is False
    assert stored == first


def test_latest_room_is_the_most_recent_one(messaging: Messaging) -> None:
    older, newer = uuid7(1_790_000_000_000), uuid7(1_790_000_100_000)
    messaging.send(message(newer, uuid7()))
    messaging.send(message(older, uuid7()))

    latest = messaging.latest_room(CUSTOMER)

    assert latest is not None
    assert latest.room_id == newer


def test_latest_room_is_none_for_a_new_customer(messaging: Messaging) -> None:
    assert messaging.latest_room(CUSTOMER) is None


def test_a_reply_keeps_its_parts_and_audit_fields_and_publishes_only_the_parts(messaging: Messaging) -> None:
    question = message(uuid7(), uuid7())
    messaging.send(question)
    citation = {"chunk_id": "c1", "title": "Doc", "page": 4, "url": "https://docs.test/doc.pdf#page=4"}
    say = {"type": "say", "text": "S/ 10.00", "facts": ["f6"], "citations": [citation]}
    fact = {
        "id": "f6",
        "kind": "spend",
        "fields": {"count": {"type": "count", "value": 3, "noun": "purchase"}},
    }
    answer = reply_to(
        question,
        "assistant",
        "S/ 10.00",
        datetime.now(UTC),
        parts=(say,),
        facts=(fact,),
        draft=({"type": "say", "text": "{f6.total}"},),
        source="composed",
    )

    messaging.write(answer)

    stored = messaging.stored(CUSTOMER, answer.message_key)
    assert stored == answer
    assert stored.public() == {**answer.public(), "parts": [say]}
    assert {"facts", "draft", "source"}.isdisjoint(stored.public())


def test_a_message_without_parts_publishes_its_text_only(messaging: Messaging) -> None:
    sent = message(uuid7(), uuid7())
    messaging.send(sent)

    stored = messaging.stored(CUSTOMER, sent.message_key)

    assert stored is not None
    assert "parts" not in stored.public()


def test_before_reads_only_the_last_messages_of_the_room_before_the_one_answered(
    messaging: Messaging,
) -> None:
    room, other_room = uuid7(), uuid7()
    start = 1_790_000_000_000
    sent = [message(room, uuid7(start + index * 1000), f"m{index}") for index in range(10)]
    for item in [*sent, message(other_room, uuid7(start + 4500), "other")]:
        messaging.send(item)

    earlier = messaging.before(sent[8], 6)

    assert [item.text for item in earlier] == ["m2", "m3", "m4", "m5", "m6", "m7"]


def test_a_tap_carries_its_ask_and_option_and_never_publishes_them() -> None:
    ask_id = uuid7()
    message_id = uuid7()

    tapped = customer_message(
        CUSTOMER, uuid7(), message_id, "Primax", at(message_id), input={"ask_id": ask_id, "option": "tx-1"}
    )

    assert tapped.input == {"ask_id": ask_id, "option": "tx-1"}
    assert Message.from_item(tapped.to_item()).input == tapped.input
    assert "input" not in tapped.public()


def test_a_tap_keeps_the_customer_s_note_trimmed_and_drops_an_empty_one() -> None:
    ask_id = uuid7()
    noted, bare = (
        customer_message(
            CUSTOMER,
            uuid7(),
            message_id,
            "Sí, fui yo",
            at(message_id),
            input={"ask_id": ask_id, "option": "yes", "note": note},
        )
        for message_id, note in ((uuid7(), "  era la gasolina del viaje "), (uuid7(), "   "))
    )

    assert noted.input == {"ask_id": ask_id, "option": "yes", "note": "era la gasolina del viaje"}
    assert bare.input == {"ask_id": ask_id, "option": "yes"}


def test_a_charge_topic_carries_the_card_and_the_charge() -> None:
    message_id = uuid7()
    topic = {"type": "charge", "product_id": uuid7(), "transaction_id": uuid7()}

    opened = customer_message(
        CUSTOMER, uuid7(), message_id, "No reconozco", at(message_id), input={"topic": topic}
    )

    assert opened.input == {"topic": topic}
    assert Message.from_item(opened.to_item()).input == opened.input


@pytest.mark.parametrize(
    "input",
    [
        {"ask_id": "01928f1e-0000-7000-8000-000000000001", "option": "yes", "note": "x" * 141},
        {"ask_id": "01928f1e-0000-7000-8000-000000000001", "option": "yes", "note": 3},
        {"topic": {"type": "charge", "product_id": "01928f1e-0000-7000-8000-000000000001"}},
        {
            "topic": {
                "type": "case",
                "product_id": "01928f1e-0000-7000-8000-000000000001",
                "transaction_id": "01928f1e-0000-7000-8000-000000000002",
            }
        },
        {
            "topic": {
                "type": "charge",
                "product_id": "card-1",
                "transaction_id": "01928f1e-0000-7000-8000-000000000002",
            }
        },
        {
            "topic": {
                "type": "charge",
                "product_id": "01928f1e-0000-7000-8000-000000000001",
                "transaction_id": "01928f1e-0000-7000-8000-000000000002",
            },
            "ask_id": "01928f1e-0000-7000-8000-000000000001",
        },
        "tx-1",
        {"ask_id": "not-a-uuid", "option": "tx-1"},
        {"option": "tx-1"},
        {"ask_id": "01928f1e-0000-7000-8000-000000000001", "option": ""},
        {"ask_id": "01928f1e-0000-7000-8000-000000000001", "option": "x" * 81},
        {"ask_id": "01928f1e-0000-7000-8000-000000000001", "option": 3},
        {"ask_id": "01928f1e-0000-7000-8000-000000000001", "option": "tx-1", "extra": True},
    ],
)
def test_a_tap_of_any_other_shape_is_rejected(input: object) -> None:
    message_id = uuid7()

    with pytest.raises(InvalidMessage):
        customer_message(CUSTOMER, uuid7(), message_id, "Primax", at(message_id), input=input)


def test_only_the_turn_holder_sets_the_status_and_a_new_turn_clears_it(
    aws: Aws, messaging: Messaging
) -> None:
    first = message(uuid7(), uuid7())
    messaging.send(first)
    second = message(first.room_id, uuid7())
    now = at(first.message_id)

    messaging.take_turn(first, now)
    messaging.mark_status(first, "movements")
    messaging.mark_status(second, "cases")
    room = messaging.room(CUSTOMER, first.room_id)
    assert room is not None
    assert room.turn(now) == {"message_id": first.message_id, "status": "movements"}

    messaging.release_turn(first)
    messaging.take_turn(second, now)
    room = messaging.room(CUSTOMER, first.room_id)
    assert room is not None
    assert room.turn(now) == {"message_id": second.message_id, "status": None}
    assert room.turn(now + timedelta(minutes=6)) is None
