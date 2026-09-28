import json
import secrets
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

import boto3

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import Table
    from mypy_boto3_sqs import SQSClient

ACCOUNT = "123456789012"
CUSTOMERS_POOL_ID = "us-east-1_customers"
STAFF_POOL_ID = "us-east-1_staff"

ENVIRONMENT = {
    "AWS_ACCESS_KEY_ID": "testing",
    "AWS_SECRET_ACCESS_KEY": "testing",
    "AWS_SESSION_TOKEN": "testing",
    "AWS_DEFAULT_REGION": "us-east-1",
    "AWS_REGION": "us-east-1",
    "POWERTOOLS_SERVICE_NAME": "test",
    "POWERTOOLS_METRICS_NAMESPACE": "Clara/Test",
    "POWERTOOLS_TRACE_DISABLED": "true",
    "TABLE_ROOMS": "clara-test-rooms",
    "TABLE_MESSAGES": "clara-test-messages",
    "ROLE_CUSTOMER_ARN": f"arn:aws:iam::{ACCOUNT}:role/clara-test-role-customer",
    "ROLE_AGENT_ARN": f"arn:aws:iam::{ACCOUNT}:role/clara-test-role-agent",
    "ROLE_OFFICER_ARN": f"arn:aws:iam::{ACCOUNT}:role/clara-test-role-officer",
    "ROLE_ANALYST_ARN": f"arn:aws:iam::{ACCOUNT}:role/clara-test-role-analyst",
    "CUSTOMERS_POOL_ID": CUSTOMERS_POOL_ID,
    "STAFF_POOL_ID": STAFF_POOL_ID,
    "EVENT_BUS_NAME": "clara-test",
    "EVENT_SOURCE": "clara.chatbot",
    "REALTIME_HTTP_URL": "https://realtime.test/event",
    "REALTIME_NAMESPACE": "rooms",
}


def uuid7(at_ms: int | None = None) -> str:
    milliseconds = int(time.time() * 1000) if at_ms is None else at_ms
    random = secrets.randbits(74)
    value = (
        (milliseconds << 80)
        | (0x7 << 76)
        | ((random >> 62) << 64)
        | (0b10 << 62)
        | (random & ((1 << 62) - 1))
    )
    return str(uuid.UUID(int=value))


def claims(
    pool_id: str = CUSTOMERS_POOL_ID, sub: str | None = None, groups: str | None = None
) -> dict[str, str]:
    token = {"iss": f"https://cognito-idp.us-east-1.amazonaws.com/{pool_id}", "sub": sub or str(uuid.uuid4())}
    if groups is not None:
        token["cognito:groups"] = groups
    return token


def api_event(method: str, path: str, token: dict[str, str], body: object = None) -> dict[str, Any]:
    return {
        "resource": "/messages/{proxy+}" if path != "/messages" else "/messages",
        "path": path,
        "httpMethod": method,
        "headers": {"Content-Type": "application/json", "Origin": "https://factoredai.sdfles.com"},
        "multiValueHeaders": {},
        "queryStringParameters": None,
        "multiValueQueryStringParameters": None,
        "pathParameters": None,
        "stageVariables": None,
        "requestContext": {
            "requestId": str(uuid.uuid4()),
            "path": path,
            "httpMethod": method,
            "stage": "prd",
            "authorizer": {"claims": token},
        },
        "body": None if body is None else json.dumps(body),
        "isBase64Encoded": False,
    }


@dataclass
class LambdaContext:
    function_name: str = "clara-test"
    memory_limit_in_mb: int = 512
    invoked_function_arn: str = f"arn:aws:lambda:us-east-1:{ACCOUNT}:function:clara-test"
    aws_request_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class Aws:
    rooms: "Table"
    messages: "Table"
    turn_events: "SQSClient"
    turn_events_url: str
    _consumed: int = 0

    def stream(self) -> dict[str, Any]:
        streams = boto3.client("dynamodbstreams")
        arn = self.messages.latest_stream_arn
        records: list[dict[str, Any]] = []
        for shard in streams.describe_stream(StreamArn=arn)["StreamDescription"]["Shards"]:
            iterator = streams.get_shard_iterator(
                StreamArn=arn, ShardId=shard["ShardId"], ShardIteratorType="TRIM_HORIZON"
            )["ShardIterator"]
            records.extend(cast(list[dict[str, Any]], streams.get_records(ShardIterator=iterator)["Records"]))
        fresh = records[self._consumed :]
        self._consumed = len(records)
        for record in fresh:
            record["eventSourceARN"] = arn
            record["dynamodb"].pop("ApproximateCreationDateTime", None)
        return {"Records": fresh}

    def events(self) -> list[dict[str, Any]]:
        received = self.turn_events.receive_message(QueueUrl=self.turn_events_url, MaxNumberOfMessages=10)
        return [json.loads(message["Body"]) for message in received.get("Messages", [])]

    def room_items(self) -> list[dict[str, Any]]:
        return self.rooms.scan()["Items"]

    def message_items(self) -> list[dict[str, Any]]:
        return self.messages.scan()["Items"]
