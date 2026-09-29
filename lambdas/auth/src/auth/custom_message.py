from dataclasses import dataclass
from typing import Any

from aws_lambda_powertools.utilities.data_classes.cognito_user_pool_event import CustomMessageTriggerEvent
from aws_lambda_powertools.utilities.typing import LambdaContext

from core.observability import logger, tracer

CODE_EMAILS = {
    "CustomMessage_SignUp",
    "CustomMessage_ResendCode",
    "CustomMessage_ForgotPassword",
    "CustomMessage_UpdateUserAttribute",
    "CustomMessage_VerifyUserAttribute",
}


@dataclass(frozen=True)
class CodeEmail:
    subject: str
    body: str


EMAILS = {
    "en": CodeEmail(
        "Clara: your code",
        "This is your Clara verification code. If you did not ask for it, you can ignore this email.",
    ),
    "es": CodeEmail(
        "Clara: tu código",
        "Este es tu código de verificación de Clara. Si no lo pediste, puedes ignorar este correo.",
    ),
    "pt-BR": CodeEmail(
        "Clara: seu código",
        "Este é o seu código de verificação da Clara. Se você não o solicitou, pode ignorar este e-mail.",
    ),
}


def render(email: CodeEmail, code_parameter: str) -> str:
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:1.5;'
        'color:#1f2937;max-width:480px">'
        f'<p style="font-size:28px;font-weight:bold;letter-spacing:4px;margin:0 0 24px">{code_parameter}</p>'
        f"<p>{email.body}</p>"
        "</div>"
    )


@logger.inject_lambda_context(clear_state=True)
@tracer.capture_lambda_handler(capture_response=False)
def handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    trigger = CustomMessageTriggerEvent(event)
    locale = trigger.request.user_attributes.get("locale")
    email = EMAILS.get(locale or "") if trigger.trigger_source in CODE_EMAILS else None
    logger.info(
        "code email", trigger_source=trigger.trigger_source, locale=locale, localized=email is not None
    )
    if email is not None:
        trigger.response.email_subject = email.subject
        trigger.response.email_message = render(email, trigger.request.code_parameter)
    return event
