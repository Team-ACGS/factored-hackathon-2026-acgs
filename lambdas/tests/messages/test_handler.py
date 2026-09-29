import json
from typing import Any

import pytest

from core.observability import tracer
from harness import STAFF_POOL_ID, Aws, LambdaContext, api_event, claims, uuid7
from messages.handler import handler


def call(event: dict[str, Any], context: LambdaContext) -> tuple[int, dict[str, Any], dict[str, list[str]]]:
    response = handler(event, context)
    return response["statusCode"], json.loads(response["body"] or "null"), response["multiValueHeaders"]


def send(token: dict[str, str], body: object, context: LambdaContext) -> tuple[int, dict[str, Any]]:
    status, payload, _ = call(api_event("POST", "/messages", token, body), context)
    return status, payload


def test_a_message_is_stored_under_the_token_subject_never_the_body(aws: Aws, context: LambdaContext) -> None:
    token = claims(sub="customer-1")
    room_id, message_id = uuid7(), uuid7()

    status, payload = send(
        token,
        {"room_id": room_id, "message_id": message_id, "text": " hola ", "customer_id": "other"},
        context,
    )

    assert status == 201
    assert payload["message"]["message_id"] == message_id
    assert payload["message"]["text"] == "hola"
    assert payload["message"]["sender_type"] == "customer"
    [item] = aws.message_items()
    assert item["customer_id"] == "customer-1"
    [room] = aws.room_items()
    assert (room["customer_id"], room["room_id"]) == ("customer-1", room_id)


def test_a_retried_post_confirms_without_writing_twice(aws: Aws, context: LambdaContext) -> None:
    token = claims()
    body = {"room_id": uuid7(), "message_id": uuid7(), "text": "hola"}

    first_status, first = send(token, body, context)
    retry_status, retry = send(token, body, context)

    assert (first_status, retry_status) == (201, 200)
    assert retry == first
    assert len(aws.message_items()) == 1


def test_a_stale_message_id_is_rejected(aws: Aws, context: LambdaContext) -> None:
    stale = uuid7(1_000_000_000_000)

    status, _ = send(claims(), {"room_id": uuid7(), "message_id": stale, "text": "hola"}, context)

    assert status == 400
    assert aws.message_items() == []


def test_a_body_without_the_required_fields_is_rejected(aws: Aws, context: LambdaContext) -> None:
    status, _ = send(claims(), {"room_id": uuid7(), "text": "hola"}, context)

    assert status == 400


def test_a_staff_token_cannot_send(aws: Aws, context: LambdaContext) -> None:
    token = claims(STAFF_POOL_ID, groups="agents")

    status, _ = send(token, {"room_id": uuid7(), "message_id": uuid7(), "text": "hola"}, context)

    assert status == 403
    assert aws.message_items() == []


def test_the_latest_room_comes_back_with_its_history_in_order(aws: Aws, context: LambdaContext) -> None:
    token = claims()
    room_id = uuid7()
    ids = [uuid7(), uuid7(), uuid7()]
    for message_id in reversed(ids):
        send(token, {"room_id": room_id, "message_id": message_id, "text": "hola"}, context)

    status, payload, _ = call(api_event("GET", "/messages/rooms/latest", token), context)

    assert status == 200
    assert payload["room"]["room_id"] == room_id
    assert [message["message_id"] for message in payload["messages"]] == sorted(ids)
    assert payload["server_time"].endswith("Z")


def test_another_customers_room_is_never_returned(aws: Aws, context: LambdaContext) -> None:
    send(claims(sub="customer-1"), {"room_id": uuid7(), "message_id": uuid7(), "text": "hola"}, context)

    status, payload, _ = call(api_event("GET", "/messages/rooms/latest", claims(sub="customer-2")), context)

    assert status == 200
    assert payload == {"room": None, "messages": [], "server_time": payload["server_time"]}


def test_responses_carry_cors_headers(aws: Aws, context: LambdaContext) -> None:
    _, _, headers = call(api_event("GET", "/messages/rooms/latest", claims()), context)

    assert headers["Access-Control-Allow-Origin"] == ["*"]


def test_a_message_stores_the_root_of_its_first_trace_and_never_returns_it(
    aws: Aws, context: LambdaContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    annotations: list[tuple[str, object]] = []
    monkeypatch.setattr(tracer, "put_annotation", lambda key, value: annotations.append((key, value)))
    body = {"room_id": uuid7(), "message_id": uuid7(), "text": "hola"}
    monkeypatch.setenv("_X_AMZN_TRACE_ID", "Root=1-6abbeeb1-first;Parent=4f25c32c;Sampled=1")
    _, first = send(claims(sub="customer-1"), body, context)
    monkeypatch.setenv("_X_AMZN_TRACE_ID", "Root=1-6abbeeb2-retry;Parent=4f25c32d;Sampled=1")

    status, retry = send(claims(sub="customer-1"), body, context)

    assert status == 200
    [item] = aws.message_items()
    assert item["origin_trace_id"] == "1-6abbeeb1-first"
    assert "origin_trace_id" not in first["message"]
    assert "origin_trace_id" not in retry["message"]
    assert annotations == [("origin_trace_id", "1-6abbeeb1-first")] * 2


def test_a_message_without_a_trace_stores_no_origin(
    aws: Aws, context: LambdaContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("_X_AMZN_TRACE_ID", raising=False)

    send(claims(), {"room_id": uuid7(), "message_id": uuid7(), "text": "hola"}, context)

    [item] = aws.message_items()
    assert "origin_trace_id" not in item
