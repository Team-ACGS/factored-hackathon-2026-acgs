from typing import Any

import pytest

from auth import custom_message
from auth.custom_message import EMAILS, KINDS, Kind
from harness import CUSTOMERS_POOL_ID, STAFF_POOL_ID, LambdaContext

LOCALES = sorted(EMAILS)


def trigger(source: str, locale: str | None) -> dict[str, Any]:
    attributes = {"sub": "0f3c5e1a-0000-4000-8000-000000000001", "email": "ana@example.com"}
    if locale is not None:
        attributes["locale"] = locale
    invitation = source == "CustomMessage_AdminCreateUser"
    return {
        "version": "1",
        "region": "us-east-1",
        "userPoolId": STAFF_POOL_ID if invitation else CUSTOMERS_POOL_ID,
        "userName": attributes["sub"],
        "callerContext": {"awsSdkVersion": "aws-sdk-js", "clientId": "client"},
        "triggerSource": source,
        "request": {
            "userAttributes": attributes,
            "codeParameter": "{####}",
            "usernameParameter": "{username}" if invitation else None,
        },
        "response": {"smsMessage": None, "emailMessage": None, "emailSubject": None},
    }


def bodies(kind: Kind) -> dict[str, str]:
    return {locale: EMAILS[locale][kind].body for locale in LOCALES}


@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("source", sorted(KINDS))
def test_every_email_goes_out_in_the_recipient_language_only(
    context: LambdaContext, source: str, locale: str
) -> None:
    response = custom_message.handler(trigger(source, locale), context)["response"]

    kind = KINDS[source]
    assert response["emailSubject"] == EMAILS[locale][kind].subject
    assert "{####}" in response["emailMessage"]
    assert bodies(kind)[locale] in response["emailMessage"]
    assert not any(
        body in response["emailMessage"] for other, body in bodies(kind).items() if other != locale
    )


@pytest.mark.parametrize("locale", LOCALES)
def test_a_staff_invitation_carries_the_username_and_the_temporary_password(
    context: LambdaContext, locale: str
) -> None:
    response = custom_message.handler(trigger("CustomMessage_AdminCreateUser", locale), context)["response"]

    assert "{username}" in response["emailMessage"]
    assert "{####}" in response["emailMessage"]


def test_a_password_reset_does_not_read_as_a_sign_up_code(context: LambdaContext) -> None:
    response = custom_message.handler(trigger("CustomMessage_ForgotPassword", "es"), context)["response"]

    assert EMAILS["es"][Kind.CODE].body not in response["emailMessage"]


@pytest.mark.parametrize("locale", [None, "fr", "es-MX", "PT-br", ""])
@pytest.mark.parametrize("source", ["CustomMessage_SignUp", "CustomMessage_AdminCreateUser"])
def test_a_missing_or_unknown_locale_gets_english(
    context: LambdaContext, source: str, locale: str | None
) -> None:
    response = custom_message.handler(trigger(source, locale), context)["response"]

    assert response["emailSubject"] == EMAILS["en"][KINDS[source]].subject
    assert EMAILS["en"][KINDS[source]].body in response["emailMessage"]
