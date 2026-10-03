import io
import json
import uuid
from datetime import UTC, datetime
from typing import Any

import boto3
import pytest

from chatbot import llm, turn
from chatbot.handler import handler
from core.facts.values import Trace
from core.ids import successor
from core.messaging import Message, Messaging, customer_message, reply_to
from core.observability import tracer
from harness import Aws, LambdaContext, uuid7

CUSTOMER = "c0ffee00-0000-4000-8000-000000000001"


def customer_says(text: str, room_id: str | None = None) -> Message:
    message = customer_message(CUSTOMER, room_id or uuid7(), uuid7(), text, datetime.now(UTC))
    Messaging.from_dynamodb(boto3.resource("dynamodb")).send(message)
    return message


def delegate(aws: Aws, room_id: str) -> None:
    aws.rooms.update_item(
        Key={"customer_id": CUSTOMER, "room_id": room_id},
        UpdateExpression="SET delegated_to_human = :yes",
        ExpressionAttributeValues={":yes": True},
    )


class FakeChatModel:
    def __init__(self, say: str) -> None:
        self.say = say
        self.requests: list[dict[str, Any]] = []

    def invoke_model(self, **request: Any) -> dict[str, Any]:
        self.requests.append(request)
        response = {"content": [{"type": "text", "text": json.dumps({"say": self.say})}]}
        return {"body": io.BytesIO(json.dumps(response).encode())}


def configure_policy_llm(monkeypatch: pytest.MonkeyPatch, say: str) -> FakeChatModel:
    model = FakeChatModel(say)
    monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")
    monkeypatch.setattr(llm, "bedrock_runtime", lambda: model)

    def retrieve_policy(state: turn.TurnState, context: Any) -> None:
        assert state.ledger is not None
        state.ledger.add("policy_chunk", {"chunk_id": Trace("policy-1")}, prefix="p")

    monkeypatch.setattr(turn, "retrieve", retrieve_policy)
    return model


@pytest.mark.skip(reason="El handler ya no responde copiando el texto del cliente")
def test_a_customer_message_gets_an_echo_right_after_it(aws: Aws, context: LambdaContext) -> None:
    message = customer_says("no reconozco este cargo")

    result = handler(aws.stream(), context)

    assert result == {"batchItemFailures": []}
    [reply] = [Message.from_item(item) for item in aws.message_items() if item["sender_type"] == "assistant"]
    assert reply.text == "no reconozco este cargo"
    assert reply.message_id == str(successor(uuid.UUID(message.message_id)))
    assert reply.sent_at == message.sent_at


def test_a_policy_question_uses_the_grounded_llm_reply(
    aws: Aws, context: LambdaContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = configure_policy_llm(monkeypatch, "Consulta el documento de referencia [p:policy-1].")
    customer_says("¿Cuál es el plazo de respuesta de la política?")

    result = handler(aws.stream(), context)

    [reply] = [Message.from_item(item) for item in aws.message_items() if item["sender_type"] == "assistant"]
    assert result == {"batchItemFailures": []}
    assert reply.text == "Consulta el documento de referencia."
    assert model.requests[0]["modelId"] == "test-model"


def test_an_ungrounded_llm_reply_is_replaced_with_a_fallback(
    aws: Aws, context: LambdaContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure_policy_llm(monkeypatch, "El plazo es 42 días.")
    customer_says("¿Cuál es el plazo de respuesta de la política?")

    handler(aws.stream(), context)

    [reply] = [Message.from_item(item) for item in aws.message_items() if item["sender_type"] == "assistant"]
    assert "42" not in reply.text


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
    Messaging.from_dynamodb(boto3.resource("dynamodb")).write(
        reply_to(message, "assistant", "hola", datetime.now(UTC))
    )

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
    Messaging.from_dynamodb(boto3.resource("dynamodb")).write(orphan)
    customer_says("hola")
    event = aws.stream()

    result = handler(event, context)

    assert result == {
        "batchItemFailures": [{"itemIdentifier": event["Records"][0]["dynamodb"]["SequenceNumber"]}]
    }
    assert [item["sender_type"] for item in aws.message_items()].count("assistant") == 1


def test_the_reply_carries_the_origin_trace_and_the_turn_is_annotated_with_it(
    aws: Aws, context: LambdaContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    annotations: list[tuple[str, object]] = []
    monkeypatch.setattr(tracer, "put_annotation", lambda key, value: annotations.append((key, value)))
    message = customer_message(CUSTOMER, uuid7(), uuid7(), "hola", datetime.now(UTC), "1-6abbeeb1-origin")
    Messaging.from_dynamodb(boto3.resource("dynamodb")).send(message)

    handler(aws.stream(), context)

    [reply] = [item for item in aws.message_items() if item["sender_type"] == "assistant"]
    assert reply["origin_trace_id"] == "1-6abbeeb1-origin"
    assert annotations == [("origin_trace_id", "1-6abbeeb1-origin")]
