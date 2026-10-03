import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from chat_notifier import handler as notifier
from chatbot.handler import handler as chatbot
from clara_testing.converse import FakeConverse, reply
from core import turn
from harness import Aws, LambdaContext, api_event, claims, demo_account, uuid7
from messages.handler import handler as messages


class Channels:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, Any]]] = []

    def publish(self, channel: str, events: list[dict[str, str]]) -> None:
        self.published.extend((channel, event) for event in events)


def customer_records(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "Records": [
            record
            for record in event["Records"]
            if record["eventName"] == "INSERT"
            and record["dynamodb"]["NewImage"]["sender_type"] == {"S": "customer"}
        ]
    }


def test_a_message_is_confirmed_answered_and_pushed_in_order(
    aws: Aws, context: LambdaContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    channels = Channels()
    monkeypatch.setattr(notifier, "_publisher", channels)
    token = claims()
    demo_account(aws, token["sub"], "PE", "es", datetime.now(UTC) - timedelta(hours=1))
    model = FakeConverse([reply("Hola, ¿en qué te ayudo?")])
    monkeypatch.setattr(turn, "bedrock_clients", model.client)
    room_id, message_id = uuid7(), uuid7()
    body = {"room_id": room_id, "message_id": message_id, "text": "hola"}

    confirmed = messages(api_event("POST", "/messages", token, body), context)
    retried = messages(api_event("POST", "/messages", token, body), context)
    customer_insert = aws.stream()
    notifier.handler(customer_insert, context)
    chatbot(customer_records(customer_insert), context)
    reply_insert = aws.stream()
    notifier.handler(reply_insert, context)
    assert customer_records(reply_insert) == {"Records": []}

    assert (confirmed["statusCode"], retried["statusCode"]) == (201, 200)
    channel = f"/rooms/{token['sub']}/{room_id}"
    assert [(name, event["sender_type"], event["text"]) for name, event in channels.published] == [
        (channel, "customer", "hola"),
        (channel, "assistant", "Hola, ¿en qué te ayudo?"),
    ]
    say = {"type": "say", "text": "Hola, ¿en qué te ayudo?", "facts": [], "citations": []}
    assert channels.published[1][1]["parts"] == [say]
    history = json.loads(messages(api_event("GET", "/messages/rooms/latest", token), context)["body"])
    assert [message["sender_type"] for message in history["messages"]] == ["customer", "assistant"]
    assert history["messages"][1]["parts"] == [say]
    assert len(aws.events()) == 1
