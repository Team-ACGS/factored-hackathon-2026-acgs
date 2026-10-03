import json
import os
from collections.abc import Iterator
from typing import TYPE_CHECKING

import boto3
import pytest
from moto import mock_aws

from harness import ENVIRONMENT, Aws, LambdaContext

if TYPE_CHECKING:
    from moto.core.config import DefaultConfig
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table

os.environ.update(ENVIRONMENT)


LIVE_BEDROCK = os.environ.get("CLARA_LIVE_BEDROCK") == "1"
PASSTHROUGH: "DefaultConfig | None" = (
    {"core": {"passthrough": {"urls": [r"https://bedrock-runtime\.[a-z0-9-]+\.amazonaws\.com/.*"]}}}
    if LIVE_BEDROCK
    else None
)


@pytest.fixture
def aws() -> Iterator[Aws]:
    with mock_aws(config=PASSTHROUGH):
        dynamodb = boto3.resource("dynamodb")
        customers = dynamodb.create_table(
            TableName=ENVIRONMENT["TABLE_CUSTOMERS"],
            KeySchema=[{"AttributeName": "customer_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "customer_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        products = dynamodb.create_table(
            TableName=ENVIRONMENT["TABLE_PRODUCTS"],
            KeySchema=[
                {"AttributeName": "customer_id", "KeyType": "HASH"},
                {"AttributeName": "product_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "customer_id", "AttributeType": "S"},
                {"AttributeName": "product_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        transactions = dynamodb.create_table(
            TableName=ENVIRONMENT["TABLE_TRANSACTIONS"],
            KeySchema=[
                {"AttributeName": "customer_id", "KeyType": "HASH"},
                {"AttributeName": "transaction_key", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "customer_id", "AttributeType": "S"},
                {"AttributeName": "transaction_key", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        rooms = dynamodb.create_table(
            TableName=ENVIRONMENT["TABLE_ROOMS"],
            KeySchema=[
                {"AttributeName": "customer_id", "KeyType": "HASH"},
                {"AttributeName": "room_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "customer_id", "AttributeType": "S"},
                {"AttributeName": "room_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        messages = dynamodb.create_table(
            TableName=ENVIRONMENT["TABLE_MESSAGES"],
            KeySchema=[
                {"AttributeName": "customer_id", "KeyType": "HASH"},
                {"AttributeName": "message_key", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "customer_id", "AttributeType": "S"},
                {"AttributeName": "message_key", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
            StreamSpecification={"StreamEnabled": True, "StreamViewType": "NEW_IMAGE"},
        )
        complaints = _keyed_table(dynamodb, ENVIRONMENT["TABLE_COMPLAINTS"], "complaint_id")
        memory = _keyed_table(dynamodb, ENVIRONMENT["TABLE_MEMORY"], "memory_key")

        sqs = boto3.client("sqs")
        queue_url = sqs.create_queue(QueueName="turn-events")["QueueUrl"]
        queue_arn = sqs.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["QueueArn"])["Attributes"][
            "QueueArn"
        ]
        events = boto3.client("events")
        events.create_event_bus(Name=ENVIRONMENT["EVENT_BUS_NAME"])
        events.put_rule(
            Name="turns",
            EventBusName=ENVIRONMENT["EVENT_BUS_NAME"],
            EventPattern=json.dumps({"source": [ENVIRONMENT["EVENT_SOURCE"]]}),
        )
        events.put_targets(
            Rule="turns",
            EventBusName=ENVIRONMENT["EVENT_BUS_NAME"],
            Targets=[{"Id": "queue", "Arn": queue_arn}],
        )

        yield Aws(
            customers=customers,
            products=products,
            transactions=transactions,
            rooms=rooms,
            messages=messages,
            complaints=complaints,
            memory=memory,
            turn_events=sqs,
            turn_events_url=queue_url,
        )

    from core import access

    access._sessions.clear()


def _keyed_table(dynamodb: "DynamoDBServiceResource", name: str, range_key: str) -> "Table":
    return dynamodb.create_table(
        TableName=name,
        KeySchema=[
            {"AttributeName": "customer_id", "KeyType": "HASH"},
            {"AttributeName": range_key, "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "customer_id", "AttributeType": "S"},
            {"AttributeName": range_key, "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )


@pytest.fixture
def context() -> LambdaContext:
    return LambdaContext()
