import json
import os
from datetime import UTC, datetime
from functools import cache
from typing import TYPE_CHECKING, Any

import boto3
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.batch import BatchProcessor, EventType, process_partial_response
from aws_lambda_powertools.utilities.batch.types import PartialItemFailureResponse
from aws_lambda_powertools.utilities.data_classes.dynamo_db_stream_event import DynamoDBRecord
from aws_lambda_powertools.utilities.typing import LambdaContext

from core.access import customer_session
from core.messaging import Message, Messaging, reply_to
from core.observability import logger, metrics, trace_id, tracer

if TYPE_CHECKING:
    from mypy_boto3_events import EventBridgeClient

SERVICE = "chatbot"

processor = BatchProcessor(event_type=EventType.DynamoDBStreams)


class RoomNotFound(Exception):
    pass


class TurnEventRejected(Exception):
    pass


@cache
def _events() -> "EventBridgeClient":
    return boto3.client("events")


@tracer.capture_method(capture_response=False)
def answer(record: DynamoDBRecord) -> None:
    stream = record.dynamodb
    if stream is None:
        raise ValueError("stream record without dynamodb data")
    message = Message.from_item(stream.new_image)
    logger.append_keys(
        customer_id=message.customer_id, room_id=message.room_id, message_id=message.message_id
    )
    if message.sender_type != "customer":
        logger.info("skipped, not a customer message", sender_type=message.sender_type)
        return

    messaging = Messaging.from_session(customer_session(message.customer_id, SERVICE))
    room = messaging.room(message.customer_id, message.room_id)
    if room is None:
        raise RoomNotFound(message.room_id)
    if room.delegated_to_human:
        logger.info("skipped, room delegated to a human")
        metrics.add_metric(name="TurnsSkippedDelegated", unit=MetricUnit.Count, value=1)
        return

    reply, created = messaging.write(reply_to(message, "assistant", message.text, datetime.now(UTC)))
    _turn_completed(message, reply)
    logger.info("turn completed", reply_id=reply.message_id, first_write=created)
    metrics.add_metric(name="TurnsCompleted", unit=MetricUnit.Count, value=1)


def _turn_completed(message: Message, reply: Message) -> None:
    detail = {
        "customer_id": message.customer_id,
        "room_id": message.room_id,
        "message_id": message.message_id,
        "reply_message_id": reply.message_id,
        "trace_id": trace_id(),
    }
    response = _events().put_events(
        Entries=[
            {
                "EventBusName": os.environ["EVENT_BUS_NAME"],
                "Source": os.environ["EVENT_SOURCE"],
                "DetailType": "turn.completed",
                "Detail": json.dumps(detail),
            }
        ]
    )
    if response.get("FailedEntryCount"):
        raise TurnEventRejected(response["Entries"][0].get("ErrorCode", "unknown"))


@logger.inject_lambda_context(clear_state=True)
@tracer.capture_lambda_handler(capture_response=False)
@metrics.log_metrics
def handler(event: dict[str, Any], context: LambdaContext) -> PartialItemFailureResponse:
    return process_partial_response(event=event, record_handler=answer, processor=processor, context=context)
