import json
from typing import Any

import pytest
from botocore.exceptions import ClientError

from auth import post_confirmation, pre_token_generation
from core.access import RoleSession, customer_session
from harness import CUSTOMERS_POOL_ID, Aws, LambdaContext

SUB = "0f3c5e1a-0000-4000-8000-000000000001"


def trigger(source: str, **attributes: str) -> dict[str, Any]:
    return {
        "version": "1",
        "region": "us-east-1",
        "userPoolId": CUSTOMERS_POOL_ID,
        "userName": SUB,
        "callerContext": {"awsSdkVersion": "aws-sdk-js", "clientId": "customer-client"},
        "triggerSource": source,
        "request": {
            "userAttributes": {"sub": SUB, "email": "ana@example.com", "email_verified": "true", **attributes}
        },
        "response": {},
    }


@pytest.fixture
def sessions(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    tagged: list[str] = []

    def recording(customer_id: str, service: str) -> RoleSession:
        tagged.append(customer_id)
        return customer_session(customer_id, service)

    monkeypatch.setattr(post_confirmation, "customer_session", recording)
    return tagged


def test_a_confirmed_sign_up_creates_the_customer_keyed_by_sub(
    aws: Aws, context: LambdaContext, sessions: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    event = trigger("PostConfirmation_ConfirmSignUp")

    assert post_confirmation.handler(event, context) == event

    [customer] = aws.customers.scan()["Items"]
    assert customer["customer_id"] == SUB
    assert customer["email"] == "ana@example.com"
    assert str(customer["created_at"]).endswith("Z")
    assert sessions == [SUB]
    output = capsys.readouterr().out
    assert '"SignUps"' in output
    assert "ana@example.com" not in output


def test_a_sign_up_with_a_name_stores_it_trimmed(aws: Aws, context: LambdaContext) -> None:
    post_confirmation.handler(trigger("PostConfirmation_ConfirmSignUp", given_name="  Sebastián "), context)

    [customer] = aws.customers.scan()["Items"]
    assert customer["given_name"] == "Sebastián"


@pytest.mark.parametrize("given_name", ["   ", "A" * 51])
def test_a_name_outside_one_to_fifty_characters_is_dropped_without_failing(
    aws: Aws, context: LambdaContext, given_name: str
) -> None:
    event = trigger("PostConfirmation_ConfirmSignUp", given_name=given_name)

    assert post_confirmation.handler(event, context) == event

    [customer] = aws.customers.scan()["Items"]
    assert "given_name" not in customer


def test_a_second_confirmation_changes_nothing(aws: Aws, context: LambdaContext) -> None:
    post_confirmation.handler(trigger("PostConfirmation_ConfirmSignUp"), context)
    first = aws.customers.scan()["Items"]

    post_confirmation.handler(trigger("PostConfirmation_ConfirmSignUp"), context)

    assert aws.customers.scan()["Items"] == first


def test_a_password_reset_confirmation_writes_nothing(
    aws: Aws, context: LambdaContext, sessions: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    post_confirmation.handler(trigger("PostConfirmation_ConfirmForgotPassword"), context)

    assert aws.customers.scan()["Items"] == []
    assert sessions == []
    assert '"SignUps"' not in capsys.readouterr().out


def test_a_failed_write_fails_the_confirmation(aws: Aws, context: LambdaContext) -> None:
    aws.customers.delete()

    with pytest.raises(ClientError):
        post_confirmation.handler(trigger("PostConfirmation_ConfirmSignUp"), context)


def test_pre_token_generation_returns_the_event_unchanged(context: LambdaContext) -> None:
    event = trigger("TokenGeneration_Authentication")
    before = json.dumps(event, sort_keys=True)

    assert pre_token_generation.handler(event, context) == json.loads(before)
