import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import boto3
import pytest
from aws_lambda_powertools.utilities.batch.exceptions import BatchProcessingError

from chatbot import handler as chatbot
from chatbot.handler import handler
from clara_testing.converse import FakeConverse, reply, response, tool_use
from core import turn as turn_module
from core.ids import format_instant, successor
from core.messaging import Message, Messaging, customer_message, reply_to
from core.observability import tracer
from core.realtime import Publisher
from harness import Aws, LambdaContext, demo_account, uuid7

CUSTOMER = "c0ffee00-0000-4000-8000-000000000001"
OTHER_MESSAGE = "01928f1e-0000-7000-8000-000000000001"


@pytest.fixture
def model(aws: Aws, monkeypatch: pytest.MonkeyPatch) -> FakeConverse:
    demo_account(aws, CUSTOMER, "PE", "es", datetime.now(UTC) - timedelta(hours=1))
    fake = FakeConverse([reply("Hola Ana, ¿en qué te ayudo con tus tarjetas?")])
    monkeypatch.setattr(turn_module, "bedrock_clients", fake.client)
    return fake


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


def mark(aws: Aws, room_id: str, message_id: str, started_at: datetime) -> None:
    aws.rooms.update_item(
        Key={"customer_id": CUSTOMER, "room_id": room_id},
        UpdateExpression="SET turn_message_id = :message, turn_started_at = :at",
        ExpressionAttributeValues={":message": message_id, ":at": format_instant(started_at)},
    )


def replies(aws: Aws) -> list[Message]:
    return [Message.from_item(item) for item in aws.message_items() if item["sender_type"] == "assistant"]


def test_a_customer_message_gets_clara_s_reply_right_after_it(
    aws: Aws, context: LambdaContext, model: FakeConverse
) -> None:
    message = customer_says("hola")

    result = handler(aws.stream(), context)

    assert result == {"batchItemFailures": []}
    [answer] = replies(aws)
    assert answer.message_id == str(successor(uuid.UUID(message.message_id)))
    assert answer.sent_at == message.sent_at
    assert answer.text == "Hola Ana, ¿en qué te ayudo con tus tarjetas?"
    assert answer.parts == ({"type": "say", "text": answer.text, "facts": [], "citations": []},)
    assert answer.source == "composed"
    assert answer.public()["parts"] == list(answer.parts)
    assert {"draft", "facts", "source"}.isdisjoint(answer.public())


def test_the_turn_event_carries_ids_and_measures_and_never_the_text(
    aws: Aws, context: LambdaContext, model: FakeConverse
) -> None:
    message = customer_says("mi tarjeta termina en 4242")

    handler(aws.stream(), context)

    [event] = aws.events()
    detail = event["detail"]
    assert event["source"] == "clara.chatbot"
    assert event["detail-type"] == "turn.completed"
    assert detail["message_id"] == message.message_id
    assert detail["reply_message_id"] == str(successor(uuid.UUID(message.message_id)))
    assert detail["route"] == "open_mode"
    assert (detail["model"], detail["prompt"]) == ("us.anthropic.claude-sonnet-4-6", "system.v3")
    assert Decimal(detail["cost_usd"]) > 0
    assert detail["steps"] == 1
    assert detail["check"] == {"result": "pass", "errors": [], "tidied": {}}
    assert set(detail["tokens"]) == {"input_tokens", "output_tokens", "cache_read", "cache_write"}
    assert [step["node"] for step in detail["timings"]] == ["supervisor", "facts_check"]
    assert "trace_id" in detail
    assert "4242" not in json.dumps(event)
    assert "Hola" not in json.dumps(event)


def test_a_room_delegated_to_a_human_gets_no_reply(
    aws: Aws, context: LambdaContext, model: FakeConverse
) -> None:
    room_id = uuid7()
    customer_says("hola", room_id)
    delegate(aws, room_id)
    customer_says("sigo aquí", room_id)

    handler(aws.stream(), context)

    assert {item["sender_type"] for item in aws.message_items()} == {"customer"}
    assert aws.events() == []
    assert model.requests == []


def test_clara_never_answers_her_own_messages(aws: Aws, context: LambdaContext, model: FakeConverse) -> None:
    message = customer_says("hola")
    aws.stream()
    Messaging.from_dynamodb(boto3.resource("dynamodb")).write(
        reply_to(message, "assistant", "hola", datetime.now(UTC))
    )

    result = handler(aws.stream(), context)

    assert result == {"batchItemFailures": []}
    assert len(aws.message_items()) == 2
    assert aws.events() == []


def test_a_redelivered_record_runs_no_second_turn_and_reports_the_stored_reply(
    aws: Aws, context: LambdaContext, model: FakeConverse
) -> None:
    customer_says("hola")
    event = aws.stream()

    handler(event, context)
    handler(event, context)

    assert len(replies(aws)) == 1
    assert len(model.requests) == 1
    first, second = aws.events()
    assert first["detail"]["reply_message_id"] == second["detail"]["reply_message_id"]
    assert second["detail"]["route"] == "replayed"


def test_a_fresh_turn_mark_of_another_message_makes_the_record_retry(
    aws: Aws, context: LambdaContext, model: FakeConverse
) -> None:
    room_id = uuid7()
    customer_says("hola", room_id)
    mark(aws, room_id, OTHER_MESSAGE, datetime.now(UTC) - timedelta(minutes=4))

    with pytest.raises(BatchProcessingError, match="TurnInProgress"):
        handler(aws.stream(), context)

    assert model.requests == []
    assert replies(aws) == []
    [room] = aws.room_items()
    assert room["turn_message_id"] == OTHER_MESSAGE


def test_a_turn_mark_older_than_five_minutes_is_taken_over_and_cleared(
    aws: Aws, context: LambdaContext, model: FakeConverse
) -> None:
    room_id = uuid7()
    customer_says("hola", room_id)
    mark(aws, room_id, OTHER_MESSAGE, datetime.now(UTC) - timedelta(minutes=5, seconds=1))

    result = handler(aws.stream(), context)

    assert result == {"batchItemFailures": []}
    assert len(replies(aws)) == 1
    [room] = aws.room_items()
    assert "turn_message_id" not in room
    assert "turn_started_at" not in room


def test_the_turn_mark_is_cleared_when_the_reply_cannot_be_written(
    aws: Aws, context: LambdaContext, model: FakeConverse, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refused(self: Messaging, message: Message) -> tuple[Message, bool]:
        raise RuntimeError("write refused")

    customer_says("hola")
    event = aws.stream()
    monkeypatch.setattr(Messaging, "write", refused)

    with pytest.raises(BatchProcessingError, match="write refused"):
        handler(event, context)

    [room] = aws.room_items()
    assert "turn_message_id" not in room


def test_a_graph_that_crashes_still_replies_from_what_was_read(
    aws: Aws, context: LambdaContext, model: FakeConverse
) -> None:
    model.responses[:] = [RuntimeError("boom")]
    customer_says("hola")

    result = handler(aws.stream(), context)

    assert result == {"batchItemFailures": []}
    [answer] = replies(aws)
    assert answer.source == "fallback"
    assert answer.text == "No pude revisar eso ahora. Intenta de nuevo en un momento."
    [event] = aws.events()
    assert event["detail"]["exhausted"] == "crashed"


def test_a_record_that_fails_is_reported_alone(aws: Aws, context: LambdaContext, model: FakeConverse) -> None:
    orphan = customer_message(CUSTOMER, uuid7(), uuid7(), "hola", datetime.now(UTC))
    Messaging.from_dynamodb(boto3.resource("dynamodb")).write(orphan)
    customer_says("hola")
    event = aws.stream()

    result = handler(event, context)

    assert result == {
        "batchItemFailures": [{"itemIdentifier": event["Records"][0]["dynamodb"]["SequenceNumber"]}]
    }
    assert len(replies(aws)) == 1


def test_the_reply_carries_the_origin_trace_and_the_turn_is_annotated_with_it(
    aws: Aws, context: LambdaContext, model: FakeConverse, monkeypatch: pytest.MonkeyPatch
) -> None:
    annotations: list[tuple[str, object]] = []
    monkeypatch.setattr(tracer, "put_annotation", lambda key, value: annotations.append((key, value)))
    message = customer_message(CUSTOMER, uuid7(), uuid7(), "hola", datetime.now(UTC), "1-6abbeeb1-origin")
    Messaging.from_dynamodb(boto3.resource("dynamodb")).send(message)

    handler(aws.stream(), context)

    [answer] = [item for item in aws.message_items() if item["sender_type"] == "assistant"]
    assert answer["origin_trace_id"] == "1-6abbeeb1-origin"
    assert annotations == [("origin_trace_id", "1-6abbeeb1-origin")]


@dataclass
class Published:
    status: int = 200
    events: list[dict[str, Any]] = field(default_factory=list)

    def request(self, method: str, url: str, body: str, headers: dict[str, str], timeout: object) -> Any:
        payload = json.loads(body)
        self.events.extend(
            {"channel": payload["channel"], **json.loads(event)} for event in payload["events"]
        )
        return SimpleNamespace(status=self.status, data=b'{"failed": []}')


@pytest.fixture
def published(monkeypatch: pytest.MonkeyPatch) -> Published:
    fake = Published()
    publisher = Publisher("https://realtime.test/event", "us-east-1", boto3.Session(), fake, 0.5)  # type: ignore[arg-type]
    monkeypatch.setattr(chatbot, "_publisher", publisher)
    return fake


def reading_model(aws: Aws, monkeypatch: pytest.MonkeyPatch, seen: list[Any]) -> None:
    demo_account(aws, CUSTOMER, "PE", "es", datetime.now(UTC) - timedelta(hours=1))
    fake = FakeConverse([response(tool_use("case_status", {})), reply("Listo.")])
    original = fake.client

    def watching(remaining: float) -> Any:
        rooms = aws.room_items()
        seen.append(rooms[0].get("turn_status") if rooms else None)
        return original(remaining)

    monkeypatch.setattr(turn_module, "bedrock_clients", watching)


def test_each_tool_round_publishes_a_status_to_the_room_and_marks_the_turn(
    aws: Aws, context: LambdaContext, monkeypatch: pytest.MonkeyPatch, published: Published
) -> None:
    seen: list[Any] = []
    reading_model(aws, monkeypatch, seen)
    message = customer_says("¿cómo va mi aclaración?")

    handler(aws.stream(), context)

    assert published.events == [
        {
            "channel": f"/rooms/{CUSTOMER}/{message.room_id}",
            "type": "status",
            "id": f"{message.message_id}#1",
            "room_id": message.room_id,
            "message_id": message.message_id,
            "round": 1,
            "status": "cases",
        }
    ]
    assert seen == [None, "cases"]
    [room] = aws.room_items()
    assert "turn_status" not in room


def test_a_status_the_channel_refuses_still_marks_the_turn_and_never_fails_it(
    aws: Aws, context: LambdaContext, monkeypatch: pytest.MonkeyPatch, published: Published
) -> None:
    published.status = 500
    seen: list[Any] = []
    reading_model(aws, monkeypatch, seen)
    customer_says("¿cómo va mi aclaración?")

    result = handler(aws.stream(), context)

    assert result == {"batchItemFailures": []}
    assert [reply.text for reply in replies(aws)] == ["Listo."]
    assert seen == [None, "cases"]
