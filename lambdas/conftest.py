import json
import os
from collections.abc import Iterator

import boto3
import pytest
from moto import mock_aws

from harness import ENVIRONMENT, Aws, LambdaContext

os.environ.update(ENVIRONMENT)


@pytest.fixture
def aws() -> Iterator[Aws]:
    with mock_aws():
        dynamodb = boto3.resource("dynamodb")
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

        yield Aws(rooms=rooms, messages=messages, turn_events=sqs, turn_events_url=queue_url)

    from chat_notifier import handler as notifier
    from chatbot import handler as chatbot

    chatbot._events.cache_clear()
    notifier._publisher.cache_clear()


@pytest.fixture
def context() -> LambdaContext:
    return LambdaContext()
