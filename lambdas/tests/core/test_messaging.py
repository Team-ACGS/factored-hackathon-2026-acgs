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
