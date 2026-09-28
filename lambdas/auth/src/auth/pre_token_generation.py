from typing import Any

from aws_lambda_powertools.utilities.data_classes.cognito_user_pool_event import (
    PreTokenGenerationV2TriggerEvent,
)
from aws_lambda_powertools.utilities.typing import LambdaContext

from core.observability import logger, tracer


@logger.inject_lambda_context(clear_state=True)
@tracer.capture_lambda_handler(capture_response=False)
def handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    trigger = PreTokenGenerationV2TriggerEvent(event)
    logger.info(
        "token issued",
        trigger_source=trigger.trigger_source,
        user_pool_id=trigger.user_pool_id,
        client_id=trigger.caller_context.client_id,
    )
    return event
