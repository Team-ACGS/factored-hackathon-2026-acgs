import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
import pytest

from core import access
from core.access import AccessDenied, Pool, Principal, RoleSession, customer_session, session_for
from harness import CUSTOMERS_POOL_ID, STAFF_POOL_ID, Aws, claims


@dataclass
class Sts:
    requests: list[dict[str, Any]] = field(default_factory=list)
    lifetime: timedelta | None = None


@pytest.fixture
def sts(aws: Aws, monkeypatch: pytest.MonkeyPatch) -> Sts:
    recorded = Sts()
    assume_role = access._sts.assume_role

    def recording(**request: Any) -> Any:
        recorded.requests.append(request)
        response = assume_role(**request)
        if recorded.lifetime is not None:
            response["Credentials"]["Expiration"] = datetime.now(UTC) + recorded.lifetime
        return response

    monkeypatch.setattr(access._sts, "assume_role", recording)
    return recorded


def assumed_arn(session: RoleSession) -> str:
    sts = boto3.client(
        "sts",
        aws_access_key_id=session.credentials.access_key,
        aws_secret_access_key=session.credentials.secret_key,
        aws_session_token=session.credentials.token,
    )
    return sts.get_caller_identity()["Arn"]


def staff(sub: str, group: str) -> Principal:
    return Principal.from_claims(claims(STAFF_POOL_ID, sub=sub, groups=group))


def test_a_customers_token_is_a_customer_identified_by_its_sub() -> None:
    principal = Principal.from_claims(claims(CUSTOMERS_POOL_ID, sub="c1"))

    assert principal.pool is Pool.CUSTOMERS
    assert principal.subject == "c1"


def test_a_token_from_an_unknown_pool_is_denied() -> None:
    with pytest.raises(AccessDenied):
        Principal.from_claims(claims("us-east-1_other"))


@pytest.mark.parametrize(
    ("claim", "groups"), [("agents", {"agents"}), ("[agents officers]", {"agents", "officers"})]
)
def test_staff_groups_are_read_from_the_claim(claim: str, groups: set[str]) -> None:
    assert Principal.from_claims(claims(STAFF_POOL_ID, groups=claim)).groups == groups


def test_a_customer_session_is_tagged_with_the_customer_id(aws: Aws) -> None:
    principal = Principal.from_claims(claims(CUSTOMERS_POOL_ID, sub="c1"))

    assert assumed_arn(session_for(principal, "test")).endswith(
        ":assumed-role/clara-test-role-customer/test-c1"
    )


def test_a_staff_session_assumes_the_role_of_its_group(aws: Aws) -> None:
    principal = Principal.from_claims(claims(STAFF_POOL_ID, sub="s1", groups="officers"))

    assert assumed_arn(session_for(principal, "test")).endswith(
        ":assumed-role/clara-test-role-officer/test-s1"
    )


@pytest.mark.parametrize("groups", ["", "agents,officers"])
def test_a_staff_token_without_exactly_one_group_is_denied(aws: Aws, groups: str) -> None:
    with pytest.raises(AccessDenied):
        session_for(Principal.from_claims(claims(STAFF_POOL_ID, groups=groups)), "test")


def test_a_warm_environment_assumes_the_role_once_per_customer(sts: Sts) -> None:
    first = customer_session("c1", "test")
    second = customer_session("c1", "test")

    assert len(sts.requests) == 1
    assert second is first
    assert second.dynamodb is first.dynamodb


def test_two_customers_in_one_environment_get_their_own_tagged_sessions(sts: Sts) -> None:
    first = customer_session("c1", "test")
    second = customer_session("c2", "test")

    assert [request["Tags"] for request in sts.requests] == [
        [{"Key": "customer_id", "Value": "c1"}],
        [{"Key": "customer_id", "Value": "c2"}],
    ]
    assert assumed_arn(first).endswith(":assumed-role/clara-test-role-customer/test-c1")
    assert assumed_arn(second).endswith(":assumed-role/clara-test-role-customer/test-c2")
    assert customer_session("c1", "test") is first


def test_the_same_person_under_another_role_gets_a_session_of_that_role(sts: Sts) -> None:
    agent = session_for(staff("s1", "agents"), "test")
    officer = session_for(staff("s1", "officers"), "test")

    assert len(sts.requests) == 2
    assert assumed_arn(agent).endswith(":assumed-role/clara-test-role-agent/test-s1")
    assert assumed_arn(officer).endswith(":assumed-role/clara-test-role-officer/test-s1")


def test_credentials_inside_the_refresh_margin_are_renewed(sts: Sts) -> None:
    sts.lifetime = access.REFRESH_MARGIN - timedelta(seconds=1)
    expiring = customer_session("c1", "test")

    renewed = customer_session("c1", "test")

    assert len(sts.requests) == 2
    assert renewed is not expiring


def test_credentials_outside_the_refresh_margin_are_reused(sts: Sts) -> None:
    sts.lifetime = access.REFRESH_MARGIN + timedelta(seconds=30)
    customer_session("c1", "test")

    customer_session("c1", "test")

    assert len(sts.requests) == 1


def test_the_cache_forgets_the_least_recently_used_session(sts: Sts, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(access, "MAX_SESSIONS", 2)
    for customer_id in ("c1", "c2", "c1", "c3", "c1", "c2"):
        customer_session(customer_id, "test")

    assert [request["Tags"][0]["Value"] for request in sts.requests] == ["c1", "c2", "c3", "c2"]


def test_each_session_signs_its_table_calls_with_its_own_role_credentials(sts: Sts) -> None:
    sessions = [customer_session("c1", "test"), customer_session("c2", "test")]
    signed: list[str] = []
    for session in sessions:
        session.dynamodb.meta.client.meta.events.register_first(
            "before-send", lambda request, **_: signed.append(str(request.headers["Authorization"]))
        )
        session.dynamodb.Table(os.environ["TABLE_CUSTOMERS"]).get_item(Key={"customer_id": "c1"})

    assert sessions[0].credentials.access_key != sessions[1].credentials.access_key
    for session, header in zip(sessions, signed, strict=True):
        assert f"Credential={session.credentials.access_key}/" in header
