from typing import Any

from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.batch import BatchProcessor, EventType, process_partial_response
from aws_lambda_powertools.utilities.batch.types import PartialItemFailureResponse
from aws_lambda_powertools.utilities.data_classes.dynamo_db_stream_event import DynamoDBRecord
from aws_lambda_powertools.utilities.typing import LambdaContext

from core.messaging import Message
from core.observability import annotate_origin, logger, metrics, tracer
from core.realtime import Publisher, room_channel

processor = BatchProcessor(event_type=EventType.DynamoDBStreams)


_publisher = Publisher.from_env(timeout=5.0)


@tracer.capture_method(capture_response=False)
def notify(record: DynamoDBRecord) -> None:
    stream = record.dynamodb
    if stream is None:
        raise ValueError("stream record without dynamodb data")
    message = Message.from_item(stream.new_image)
    annotate_origin(message.origin_trace_id)
    _publisher.publish(room_channel(message.customer_id, message.room_id), [message.public()])
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
