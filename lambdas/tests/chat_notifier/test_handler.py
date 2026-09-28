import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import boto3
import pytest

from chat_notifier import handler as notifier
from core.messaging import Message, Messaging, customer_message
from harness import Aws, LambdaContext, uuid7

CUSTOMER = "c0ffee00-0000-4000-8000-000000000001"


@dataclass
class Response:
    status: int
    data: bytes


@dataclass
class FakeHttp:
    rejected_channel: str | None = None
    status: int = 200
    failed: list[Any] = field(default_factory=list)
    requests: list[dict[str, Any]] = field(default_factory=list)

    def request(self, method: str, url: str, body: str, headers: dict[str, str], timeout: float) -> Response:
        payload = json.loads(body)
        self.requests.append({"method": method, "url": url, "body": payload, "headers": headers})
        if payload["channel"] != self.rejected_channel:
            return Response(200, json.dumps({"successful": [], "failed": []}).encode())
        return Response(self.status, json.dumps({"successful": [], "failed": self.failed}).encode())


@pytest.fixture
def http(monkeypatch: pytest.MonkeyPatch) -> FakeHttp:
    fake = FakeHttp()
    publisher = notifier.Publisher("https://realtime.test/event", "us-east-1", boto3.Session(), fake)  # type: ignore[arg-type]
    monkeypatch.setattr(notifier, "_publisher", lambda: publisher)
    return fake


def store(text: str = "hola") -> Message:
    message = customer_message(CUSTOMER, uuid7(), uuid7(), text, datetime.now(UTC))
    Messaging.from_session(boto3.Session()).send(message)
    return message


def test_a_new_message_is_published_to_its_room_channel(
    aws: Aws, http: FakeHttp, context: LambdaContext
) -> None:
    message = store()

    result = notifier.handler(aws.stream(), context)

    assert result == {"batchItemFailures": []}
    [request] = http.requests
    assert request["url"] == "https://realtime.test/event"
    assert request["body"]["channel"] == f"/rooms/{CUSTOMER}/{message.room_id}"
    assert [json.loads(event) for event in request["body"]["events"]] == [message.public()]


def test_the_publish_is_signed_for_appsync(aws: Aws, http: FakeHttp, context: LambdaContext) -> None:
    store()

    notifier.handler(aws.stream(), context)

    headers = http.requests[0]["headers"]
    assert "/us-east-1/appsync/aws4_request" in headers["Authorization"]
    assert "X-Amz-Date" in headers


@pytest.mark.parametrize(("status", "failed"), [(200, [{"identifier": "x", "code": "Denied"}]), (403, [])])
def test_a_rejected_publish_is_reported_as_a_failed_record(
    aws: Aws, http: FakeHttp, context: LambdaContext, status: int, failed: list[Any]
) -> None:
    rejected = store()
    store()
    http.rejected_channel = f"/rooms/{CUSTOMER}/{rejected.room_id}"
    http.status, http.failed = status, failed
    event = aws.stream()

    result = notifier.handler(event, context)

    assert result == {
        "batchItemFailures": [{"itemIdentifier": event["Records"][0]["dynamodb"]["SequenceNumber"]}]
    }
    assert len(http.requests) == 2
