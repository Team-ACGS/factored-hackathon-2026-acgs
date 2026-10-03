import json
import secrets
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
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
    "TABLE_CUSTOMERS": "clara-test-customers",
    "TABLE_PRODUCTS": "clara-test-products",
    "TABLE_TRANSACTIONS": "clara-test-transactions",
    "TABLE_ROOMS": "clara-test-rooms",
    "TABLE_MESSAGES": "clara-test-messages",
    "TABLE_COMPLAINTS": "clara-test-complaints",
    "TABLE_MEMORY": "clara-test-memory",
    "ROLE_CUSTOMER_ARN": f"arn:aws:iam::{ACCOUNT}:role/clara-test-role-customer",
    "ROLE_AGENT_ARN": f"arn:aws:iam::{ACCOUNT}:role/clara-test-role-agent",
    "ROLE_OFFICER_ARN": f"arn:aws:iam::{ACCOUNT}:role/clara-test-role-officer",
    "ROLE_ANALYST_ARN": f"arn:aws:iam::{ACCOUNT}:role/clara-test-role-analyst",
    "CUSTOMERS_POOL_ID": CUSTOMERS_POOL_ID,
    "STAFF_POOL_ID": STAFF_POOL_ID,
    "EVENT_BUS_NAME": "clara-test",
    "EVENT_SOURCE": "clara.chatbot",
    "BEDROCK_MODEL_ID": "us.anthropic.claude-sonnet-4-6",
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


def api_event(
    method: str, path: str, token: dict[str, str], body: object = None, query: dict[str, str] | None = None
) -> dict[str, Any]:
    prefix = "/" + path.strip("/").split("/", 1)[0]
    return {
        "resource": f"{prefix}/{{proxy+}}" if path != prefix else prefix,
        "path": path,
        "httpMethod": method,
        "headers": {"Content-Type": "application/json", "Origin": "https://factoredai.sdfles.com"},
        "multiValueHeaders": {},
        "queryStringParameters": query,
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
    customers: "Table"
    products: "Table"
    transactions: "Table"
    rooms: "Table"
    messages: "Table"
    complaints: "Table"
    memory: "Table"
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


@dataclass(frozen=True)
class DemoAccount:
    customer_id: str
    country: str
    cards: list[dict[str, Any]]
    transactions: list[dict[str, Any]]
    claim: dict[str, Any] | None


def demo_account(
    aws: Aws,
    customer_id: str,
    country: str,
    language: str,
    anchor: datetime,
    given_name: str | None = "Ana",
) -> DemoAccount:
    from crud.catalog import COUNTRIES
    from crud.generator import Claim, generate

    account = generate(Claim(customer_id, COUNTRIES[country], anchor))
    customer: dict[str, Any] = {
        "customer_id": customer_id,
        "email": f"{customer_id}@example.com",
        "created_at": "2026-01-01T00:00:00.000Z",
        "country": country,
        "language": language,
    }
    if given_name:
        customer["given_name"] = given_name
    aws.customers.put_item(Item=customer)
    for card in account.cards:
        aws.products.put_item(Item=card)
    for item in account.transactions:
        aws.transactions.put_item(Item=item)
    if account.claim:
        aws.complaints.put_item(Item=account.claim)
    return DemoAccount(customer_id, country, account.cards, account.transactions, account.claim)
