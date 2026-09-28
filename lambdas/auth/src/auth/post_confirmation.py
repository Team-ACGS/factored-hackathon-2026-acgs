from typing import Any

from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.data_classes.cognito_user_pool_event import PostConfirmationTriggerEvent
from aws_lambda_powertools.utilities.typing import LambdaContext

from core.observability import logger, metrics, tracer

SIGN_UP = "PostConfirmation_ConfirmSignUp"


@logger.inject_lambda_context(clear_state=True)
@tracer.capture_lambda_handler(capture_response=False)
@metrics.log_metrics
def handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    trigger = PostConfirmationTriggerEvent(event)
    logger.info(
        "user confirmed",
        trigger_source=trigger.trigger_source,
        user_pool_id=trigger.user_pool_id,
        customer_id=trigger.request.user_attributes.get("sub"),
    )
    if trigger.trigger_source == SIGN_UP:
        metrics.add_metric(name="SignUps", unit=MetricUnit.Count, value=1)
    return event
