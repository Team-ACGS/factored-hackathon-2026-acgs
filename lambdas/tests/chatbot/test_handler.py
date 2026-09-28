import uuid
from datetime import UTC, datetime

import boto3

from chatbot.handler import handler
from core.ids import successor
from core.messaging import Message, Messaging, customer_message, reply_to
from harness import Aws, LambdaContext, uuid7

CUSTOMER = "c0ffee00-0000-4000-8000-000000000001"


def customer_says(text: str, room_id: str | None = None) -> Message:
    message = customer_message(CUSTOMER, room_id or uuid7(), uuid7(), text, datetime.now(UTC))
    Messaging.from_session(boto3.Session()).send(message)
    return message


def delegate(aws: Aws, room_id: str) -> None:
    aws.rooms.update_item(
        Key={"customer_id": CUSTOMER, "room_id": room_id},
        UpdateExpression="SET delegated_to_human = :yes",
        ExpressionAttributeValues={":yes": True},
    )


def test_a_customer_message_gets_an_echo_right_after_it(aws: Aws, context: LambdaContext) -> None:
    message = customer_says("no reconozco este cargo")

    result = handler(aws.stream(), context)

    assert result == {"batchItemFailures": []}
    [reply] = [Message.from_item(item) for item in aws.message_items() if item["sender_type"] == "assistant"]
    assert reply.text == "no reconozco este cargo"
    assert reply.message_id == str(successor(uuid.UUID(message.message_id)))
    assert reply.sent_at == message.sent_at


def test_the_turn_event_carries_ids_and_never_the_text(aws: Aws, context: LambdaContext) -> None:
    message = customer_says("mi tarjeta termina en 4242")

    handler(aws.stream(), context)

    [event] = aws.events()
    assert event["source"] == "clara.chatbot"
    assert event["detail-type"] == "turn.completed"
    assert event["detail"]["message_id"] == message.message_id
    assert event["detail"]["room_id"] == message.room_id
    assert event["detail"]["reply_message_id"] == str(successor(uuid.UUID(message.message_id)))
    assert "trace_id" in event["detail"]
    assert "4242" not in str(event)


def test_a_room_delegated_to_a_human_gets_no_echo(aws: Aws, context: LambdaContext) -> None:
    room_id = uuid7()
    customer_says("hola", room_id)
    delegate(aws, room_id)
    customer_says("sigo aquí", room_id)

    handler(aws.stream(), context)

    assert {item["sender_type"] for item in aws.message_items()} == {"customer"}
    assert aws.events() == []


def test_clara_never_answers_her_own_messages(aws: Aws, context: LambdaContext) -> None:
    message = customer_says("hola")
    aws.stream()
    Messaging.from_session(boto3.Session()).write(reply_to(message, "assistant", "hola", datetime.now(UTC)))

    result = handler(aws.stream(), context)

    assert result == {"batchItemFailures": []}
    assert len(aws.message_items()) == 2
    assert aws.events() == []


def test_a_redelivered_record_does_not_write_a_second_reply(aws: Aws, context: LambdaContext) -> None:
    customer_says("hola")
    event = aws.stream()

    handler(event, context)
    handler(event, context)

    assert [item["sender_type"] for item in aws.message_items()].count("assistant") == 1


def test_a_record_that_fails_is_reported_alone(aws: Aws, context: LambdaContext) -> None:
    orphan = customer_message(CUSTOMER, uuid7(), uuid7(), "hola", datetime.now(UTC))
    Messaging.from_session(boto3.Session()).write(orphan)
    customer_says("hola")
    event = aws.stream()

    result = handler(event, context)

    assert result == {
        "batchItemFailures": [{"itemIdentifier": event["Records"][0]["dynamodb"]["SequenceNumber"]}]
    }
    assert [item["sender_type"] for item in aws.message_items()].count("assistant") == 1
