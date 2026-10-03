import json
from datetime import UTC, datetime
from typing import Any

from aws_lambda_powertools.event_handler import APIGatewayRestResolver, CORSConfig, Response, content_types
from aws_lambda_powertools.event_handler.exceptions import BadRequestError, ForbiddenError
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext

from core.access import AccessDenied, Pool, Principal, customer_session
from core.ids import format_instant
from core.messaging import InvalidMessage, Messaging, customer_message
from core.observability import annotate_origin, logger, metrics, trace_id, tracer

SERVICE = "messages"

app = APIGatewayRestResolver(cors=CORSConfig(allow_origin="*", max_age=300))


def _customer() -> Principal:
    claims = app.current_event.request_context.authorizer.claims or {}
    try:
        principal = Principal.from_claims(claims)
    except AccessDenied as error:
        raise ForbiddenError(str(error)) from error
    if principal.pool is not Pool.CUSTOMERS:
        raise ForbiddenError("only customers send messages")
    logger.append_keys(customer_id=principal.subject)
    return principal


def _messaging(principal: Principal) -> Messaging:
    return Messaging.from_dynamodb(customer_session(principal.subject, SERVICE).dynamodb)


def _body() -> dict[str, Any]:
    try:
        body = json.loads(app.current_event.body or "")
    except json.JSONDecodeError as error:
        raise BadRequestError("body is not JSON") from error
    if not isinstance(body, dict):
        raise BadRequestError("body is not an object")
    return body


@app.post("/messages")
@tracer.capture_method(capture_response=False)
def send_message() -> Response[str]:
    principal = _customer()
    body = _body()
    fields = {name: body.get(name) for name in ("room_id", "message_id", "text")}
    if not all(isinstance(value, str) for value in fields.values()):
        raise BadRequestError("room_id, message_id and text are required strings")
    try:
        message = customer_message(
            principal.subject,
            str(fields["room_id"]),
            str(fields["message_id"]),
            str(fields["text"]),
            datetime.now(UTC),
            trace_id(),
            body.get("input"),
        )
    except InvalidMessage as error:
        raise BadRequestError(str(error)) from error
    stored, created = _messaging(principal).send(message)
    annotate_origin(stored.origin_trace_id)
    logger.info("message stored", room_id=stored.room_id, message_id=stored.message_id, first_write=created)
    metrics.add_metric(name="MessagesSent" if created else "MessagesRetried", unit=MetricUnit.Count, value=1)
    return Response(
        status_code=201 if created else 200,
        content_type=content_types.APPLICATION_JSON,
        body=json.dumps({"message": stored.public()}),
    )


@app.get("/messages/rooms/latest")
@tracer.capture_method(capture_response=False)
def latest_room() -> dict[str, Any]:
    principal = _customer()
    messaging = _messaging(principal)
    room = messaging.latest_room(principal.subject)
    history = messaging.history(principal.subject, room.room_id) if room else []
    now = datetime.now(UTC)
    return {
        "room": room.public() if room else None,
        "messages": [message.public() for message in history],
        "turn": room.turn(now) if room else None,
        "server_time": format_instant(now),
    }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST, clear_state=True)
@tracer.capture_lambda_handler(capture_response=False)
@metrics.log_metrics
def handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    return app.resolve(event, context)
