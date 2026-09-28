import json
from typing import Any

import pytest

from auth import post_confirmation, pre_token_generation
from harness import CUSTOMERS_POOL_ID, LambdaContext


def trigger(source: str) -> dict[str, Any]:
    return {
        "version": "1",
        "region": "us-east-1",
        "userPoolId": CUSTOMERS_POOL_ID,
        "userName": "0f3c5e1a-0000-4000-8000-000000000001",
        "callerContext": {"awsSdkVersion": "aws-sdk-js", "clientId": "customer-client"},
        "triggerSource": source,
        "request": {
            "userAttributes": {
                "sub": "0f3c5e1a-0000-4000-8000-000000000001",
                "email": "ana@example.com",
                "email_verified": "true",
            }
        },
        "response": {},
    }


def test_post_confirmation_returns_the_event_and_counts_a_sign_up(
    context: LambdaContext, capsys: pytest.CaptureFixture[str]
) -> None:
    event = trigger("PostConfirmation_ConfirmSignUp")

    assert post_confirmation.handler(event, context) == event

    output = capsys.readouterr().out
    assert '"SignUps"' in output
    assert "ana@example.com" not in output


def test_a_password_reset_confirmation_is_not_a_sign_up(
    context: LambdaContext, capsys: pytest.CaptureFixture[str]
) -> None:
    post_confirmation.handler(trigger("PostConfirmation_ConfirmForgotPassword"), context)

    assert '"SignUps"' not in capsys.readouterr().out


def test_pre_token_generation_returns_the_event_unchanged(context: LambdaContext) -> None:
    event = trigger("TokenGeneration_Authentication")
    before = json.dumps(event, sort_keys=True)

    assert pre_token_generation.handler(event, context) == json.loads(before)
