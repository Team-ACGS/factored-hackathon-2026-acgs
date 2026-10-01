from datetime import UTC, datetime
from typing import Any

from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.data_classes.cognito_user_pool_event import PostConfirmationTriggerEvent
from aws_lambda_powertools.utilities.typing import LambdaContext

from core.access import customer_session
from core.customers import create_customer
from core.ids import format_instant
from core.observability import logger, metrics, tracer

SERVICE = "auth"
SIGN_UP = "PostConfirmation_ConfirmSignUp"
MAX_GIVEN_NAME = 50


@logger.inject_lambda_context(clear_state=True)
@tracer.capture_lambda_handler(capture_response=False)
@metrics.log_metrics
def handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    trigger = PostConfirmationTriggerEvent(event)
    customer_id = trigger.request.user_attributes["sub"]
    logger.append_keys(customer_id=customer_id, trigger_source=trigger.trigger_source)
    if trigger.trigger_source != SIGN_UP:
        logger.info("user confirmed, nothing to create")
        return event

    created = create_customer(
        customer_session(customer_id, SERVICE).dynamodb,
        customer_id,
        trigger.request.user_attributes["email"],
        format_instant(datetime.now(UTC)),
        _given_name(trigger.request.user_attributes.get("given_name")),
    )
    logger.info("customer signed up", first_write=created)
    if created:
        metrics.add_metric(name="SignUps", unit=MetricUnit.Count, value=1)
    return event


def _given_name(value: str | None) -> str | None:
    name = (value or "").strip()
    return name if 1 <= len(name) <= MAX_GIVEN_NAME else None
