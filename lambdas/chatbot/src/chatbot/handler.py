import json
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import boto3
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.batch import BatchProcessor, EventType, process_partial_response
from aws_lambda_powertools.utilities.batch.types import PartialItemFailureResponse
from aws_lambda_powertools.utilities.data_classes.dynamo_db_stream_event import DynamoDBRecord
from aws_lambda_powertools.utilities.typing import LambdaContext

from core.access import customer_session
from core.messaging import Message, Messaging, reply_key, reply_to
from core.observability import annotate_origin, logger, metrics, trace_id, tracer
from core.turn import run_turn

if TYPE_CHECKING:
    from mypy_boto3_events import EventBridgeClient

SERVICE = "chatbot"

processor = BatchProcessor(event_type=EventType.DynamoDBStreams)
_events: "EventBridgeClient" = boto3.client("events")


class RoomNotFound(Exception):
    pass


class TurnEventRejected(Exception):
    pass


@tracer.capture_method(capture_response=False)
def answer(record: DynamoDBRecord) -> None:
    stream = record.dynamodb
    if stream is None:
        raise ValueError("stream record without dynamodb data")
    message = Message.from_item(stream.new_image)
    annotate_origin(message.origin_trace_id)
    logger.append_keys(
        customer_id=message.customer_id, room_id=message.room_id, message_id=message.message_id
    )
    if message.sender_type != "customer":
        logger.info("skipped, not a customer message", sender_type=message.sender_type)
        return

    messaging = Messaging.from_dynamodb(customer_session(message.customer_id, SERVICE).dynamodb)
    room = messaging.room(message.customer_id, message.room_id)
    if room is None:
        raise RoomNotFound(message.room_id)
    if room.delegated_to_human:
        logger.info("skipped, room delegated to a human")
        metrics.add_metric(name="TurnsSkippedDelegated", unit=MetricUnit.Count, value=1)
        return

    stored = messaging.stored(message.customer_id, reply_key(message))
    if stored is not None:
        _turn_completed(message, stored, {"route": "replayed", "source": stored.source})
        logger.info("skipped, reply already stored", reply_id=stored.message_id)
        metrics.add_metric(name="TurnsReplayed", unit=MetricUnit.Count, value=1)
        return

    messaging.take_turn(message, datetime.now(UTC))
    try:
        history = messaging.history(message.customer_id, message.room_id)
        turn = run_turn(message, history, datetime.now(UTC))
        answer = turn.reply
        reply, created = messaging.write(
            reply_to(
                message,
                "assistant",
                answer.text,
                datetime.now(UTC),
                answer.parts,
                answer.facts,
                answer.draft,
                answer.source,
            )
        )
        summary = turn.summary()
        _turn_completed(message, reply, summary)
    finally:
        messaging.release_turn(message)
    logger.info("turn completed", reply_id=reply.message_id, first_write=created, **summary)
    metrics.add_metric(name="TurnsCompleted", unit=MetricUnit.Count, value=1)
    metrics.add_metric(name="TurnMilliseconds", unit=MetricUnit.Milliseconds, value=turn.duration_ms)
    if answer.source == "fallback":
        metrics.add_metric(name="TurnsFallback", unit=MetricUnit.Count, value=1)


def _turn_completed(message: Message, reply: Message, summary: dict[str, Any]) -> None:
    detail = {
        "customer_id": message.customer_id,
        "room_id": message.room_id,
        "message_id": message.message_id,
        "reply_message_id": reply.message_id,
        "trace_id": trace_id(),
        **summary,
    }
    response = _events.put_events(
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
