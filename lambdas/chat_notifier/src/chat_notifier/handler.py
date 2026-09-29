import json
import os
from typing import Any

import boto3
import urllib3
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.batch import BatchProcessor, EventType, process_partial_response
from aws_lambda_powertools.utilities.batch.types import PartialItemFailureResponse
from aws_lambda_powertools.utilities.data_classes.dynamo_db_stream_event import DynamoDBRecord
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

from core.messaging import Message
from core.observability import annotate_origin, logger, metrics, tracer

processor = BatchProcessor(event_type=EventType.DynamoDBStreams)


class PublishRejected(Exception):
    pass


class Publisher:
    def __init__(self, url: str, region: str, session: boto3.Session, http: urllib3.PoolManager) -> None:
        self._url = url
        self._region = region
        self._session = session
        self._http = http

    @tracer.capture_method(capture_response=False)
    def publish(self, channel: str, events: list[dict[str, str]]) -> None:
        credentials = self._session.get_credentials()
        if credentials is None:
            raise PublishRejected("no credentials to sign with")
        body = json.dumps({"channel": channel, "events": [json.dumps(event) for event in events]})
        request = AWSRequest(
            method="POST", url=self._url, data=body, headers={"Content-Type": "application/json"}
        )
        SigV4Auth(credentials, "appsync", self._region).add_auth(request)
        response = self._http.request(
            "POST", self._url, body=body, headers=dict(request.headers.items()), timeout=5.0
        )
        if response.status != 200:
            raise PublishRejected(f"status {response.status}")
        failed = json.loads(response.data).get("failed")
        if failed:
            raise PublishRejected(json.dumps(failed))


_publisher = Publisher(
    os.environ["REALTIME_HTTP_URL"], os.environ["AWS_REGION"], boto3.Session(), urllib3.PoolManager()
)


def channel_for(message: Message) -> str:
    return f"/{os.environ['REALTIME_NAMESPACE']}/{message.customer_id}/{message.room_id}"


@tracer.capture_method(capture_response=False)
def notify(record: DynamoDBRecord) -> None:
    stream = record.dynamodb
    if stream is None:
        raise ValueError("stream record without dynamodb data")
    message = Message.from_item(stream.new_image)
    annotate_origin(message.origin_trace_id)
    _publisher.publish(channel_for(message), [message.public()])
    logger.info(
        "message published",
        customer_id=message.customer_id,
        room_id=message.room_id,
        message_id=message.message_id,
        sender_type=message.sender_type,
    )
    metrics.add_metric(name="MessagesPublished", unit=MetricUnit.Count, value=1)


@logger.inject_lambda_context(clear_state=True)
@tracer.capture_lambda_handler(capture_response=False)
@metrics.log_metrics
def handler(event: dict[str, Any], context: LambdaContext) -> PartialItemFailureResponse:
    return process_partial_response(event=event, record_handler=notify, processor=processor, context=context)
