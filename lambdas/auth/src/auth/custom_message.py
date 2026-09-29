from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from aws_lambda_powertools.utilities.data_classes.cognito_user_pool_event import CustomMessageTriggerEvent
from aws_lambda_powertools.utilities.typing import LambdaContext

from core.observability import logger, tracer


class Kind(StrEnum):
    CODE = "code"
    RESET = "reset"
    INVITATION = "invitation"


KINDS = {
    "CustomMessage_SignUp": Kind.CODE,
    "CustomMessage_ResendCode": Kind.CODE,
    "CustomMessage_UpdateUserAttribute": Kind.CODE,
    "CustomMessage_VerifyUserAttribute": Kind.CODE,
    "CustomMessage_Authentication": Kind.CODE,
    "CustomMessage_ForgotPassword": Kind.RESET,
    "CustomMessage_AdminCreateUser": Kind.INVITATION,
}

DEFAULT_LOCALE = "en"


@dataclass(frozen=True)
class Email:
    subject: str
    body: str


EMAILS: dict[str, dict[Kind, Email]] = {
    "en": {
        Kind.CODE: Email(
            "Clara: your code",
            "This is your Clara verification code. If you did not ask for it, you can ignore this email.",
        ),
        Kind.RESET: Email(
            "Clara: reset your password",
            "Use this code to reset your Clara password. "
            "If you did not ask for it, you can ignore this email.",
        ),
        Kind.INVITATION: Email(
            "Clara: your staff account",
            "Your Clara staff account is ready. Sign in with this email and the temporary password above, "
            "then choose your own password within 3 days.",
        ),
    },
    "es": {
        Kind.CODE: Email(
            "Clara: tu código",
            "Este es tu código de verificación de Clara. Si no lo pediste, puedes ignorar este correo.",
        ),
        Kind.RESET: Email(
            "Clara: restablece tu contraseña",
            "Usa este código para restablecer tu contraseña de Clara. "
            "Si no lo pediste, puedes ignorar este correo.",
        ),
        Kind.INVITATION: Email(
            "Clara: tu cuenta de staff",
            "Tu cuenta de staff de Clara está lista. "
            "Inicia sesión con este correo y la contraseña temporal de arriba, "
            "y elige tu propia contraseña en un plazo de 3 días.",
        ),
    },
    "pt-BR": {
        Kind.CODE: Email(
            "Clara: seu código",
            "Este é o seu código de verificação da Clara. Se você não o solicitou, pode ignorar este e-mail.",
        ),
        Kind.RESET: Email(
            "Clara: redefina sua senha",
            "Use este código para redefinir sua senha da Clara. "
            "Se você não o solicitou, pode ignorar este e-mail.",
        ),
        Kind.INVITATION: Email(
            "Clara: sua conta de equipe",
            "Sua conta de equipe da Clara está pronta. Entre com este e-mail e a senha temporária acima e "
            "escolha sua própria senha em até 3 dias.",
        ),
    },
}

FRAME = (
    '<div style="font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:1.5;'
    'color:#1f2937;max-width:480px">'
)


def render(kind: Kind, email: Email, code: str, username: str | None) -> str:
    if kind is Kind.INVITATION:
        secret = (
            f'<p>{username}<br><span style="font-size:22px;font-weight:bold;letter-spacing:2px">'
            f"{code}</span></p>"
        )
    else:
        secret = f'<p style="font-size:28px;font-weight:bold;letter-spacing:4px;margin:0 0 24px">{code}</p>'
    return f"{FRAME}{secret}<p>{email.body}</p></div>"


@logger.inject_lambda_context(clear_state=True)
@tracer.capture_lambda_handler(capture_response=False)
def handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    trigger = CustomMessageTriggerEvent(event)
    requested = trigger.request.user_attributes.get("locale")
    locale = requested if requested in EMAILS else DEFAULT_LOCALE
    kind = KINDS.get(trigger.trigger_source, Kind.CODE)
    email = EMAILS[locale][kind]
    logger.info(
        "custom message", trigger_source=trigger.trigger_source, locale=locale, requested_locale=requested
    )
    trigger.response.email_subject = email.subject
    trigger.response.email_message = render(
        kind, email, trigger.request.code_parameter, event["request"].get("usernameParameter")
    )
    return event
