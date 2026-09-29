from typing import Any

import pytest

from auth import custom_message
from harness import CUSTOMERS_POOL_ID, LambdaContext

BODIES = {locale: email.body for locale, email in custom_message.EMAILS.items()}


def trigger(source: str, locale: str | None) -> dict[str, Any]:
    attributes = {"sub": "0f3c5e1a-0000-4000-8000-000000000001", "email": "ana@example.com"}
    if locale is not None:
        attributes["locale"] = locale
    return {
        "version": "1",
        "region": "us-east-1",
        "userPoolId": CUSTOMERS_POOL_ID,
        "userName": attributes["sub"],
        "callerContext": {"awsSdkVersion": "aws-sdk-js", "clientId": "customer-client"},
        "triggerSource": source,
        "request": {"userAttributes": attributes, "codeParameter": "{####}", "usernameParameter": None},
        "response": {"smsMessage": None, "emailMessage": None, "emailSubject": None},
    }


@pytest.mark.parametrize("locale", ["en", "es", "pt-BR"])
@pytest.mark.parametrize(
    "source", ["CustomMessage_SignUp", "CustomMessage_ResendCode", "CustomMessage_ForgotPassword"]
)
def test_a_code_email_is_sent_in_the_customer_language_only(
    context: LambdaContext, source: str, locale: str
) -> None:
    response = custom_message.handler(trigger(source, locale), context)["response"]

    assert response["emailSubject"] == custom_message.EMAILS[locale].subject
    assert "{####}" in response["emailMessage"]
    assert BODIES[locale] in response["emailMessage"]
    assert not any(body in response["emailMessage"] for other, body in BODIES.items() if other != locale)


@pytest.mark.parametrize("locale", [None, "fr", "es-MX", ""])
def test_a_missing_or_unknown_locale_falls_back_to_the_trilingual_template(
    context: LambdaContext, locale: str | None
) -> None:
    response = custom_message.handler(trigger("CustomMessage_SignUp", locale), context)["response"]

    assert response == {"smsMessage": None, "emailMessage": None, "emailSubject": None}


def test_an_invitation_keeps_the_pool_template(context: LambdaContext) -> None:
    response = custom_message.handler(trigger("CustomMessage_AdminCreateUser", "es"), context)["response"]

    assert response["emailMessage"] is None
