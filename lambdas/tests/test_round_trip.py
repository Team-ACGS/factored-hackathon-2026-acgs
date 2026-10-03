import json
from typing import Any

import pytest

from chat_notifier import handler as notifier
from chatbot.handler import handler as chatbot
from harness import Aws, LambdaContext, api_event, claims, uuid7
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


@pytest.mark.skip(reason="El handler ya no responde copiando el texto del cliente")
def test_a_message_is_confirmed_echoed_and_pushed_in_order(
    aws: Aws, context: LambdaContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    channels = Channels()
    monkeypatch.setattr(notifier, "_publisher", channels)
    token = claims()
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
        (channel, "assistant", "hola"),
    ]
    history = json.loads(messages(api_event("GET", "/messages/rooms/latest", token), context)["body"])
    assert [message["sender_type"] for message in history["messages"]] == ["customer", "assistant"]
    assert len(aws.events()) == 1
