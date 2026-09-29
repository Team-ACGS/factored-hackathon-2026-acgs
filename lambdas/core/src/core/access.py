import os
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from functools import cached_property
from typing import TYPE_CHECKING, Any

import boto3
from botocore.credentials import ReadOnlyCredentials

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource

MAX_SESSIONS = 128
REFRESH_MARGIN = timedelta(minutes=2)

STAFF_ROLE_ENV = {
    "agents": "ROLE_AGENT_ARN",
    "officers": "ROLE_OFFICER_ARN",
    "analysts": "ROLE_ANALYST_ARN",
}


class Pool(StrEnum):
    CUSTOMERS = "customers"
    STAFF = "staff"


class AccessDenied(Exception):
    pass


@dataclass(frozen=True)
class Principal:
    pool: Pool
    subject: str
    groups: frozenset[str]

    @classmethod
    def from_claims(cls, claims: Mapping[str, Any]) -> "Principal":
        pools = {os.environ["CUSTOMERS_POOL_ID"]: Pool.CUSTOMERS, os.environ["STAFF_POOL_ID"]: Pool.STAFF}
        pool = pools.get(str(claims.get("iss", "")).rsplit("/", 1)[-1])
        subject = claims.get("sub")
        if pool is None or not isinstance(subject, str) or not subject:
            raise AccessDenied("token from an unknown pool")
        return cls(pool=pool, subject=subject, groups=_groups(claims.get("cognito:groups")))


class RoleSession:
    def __init__(self, credentials: ReadOnlyCredentials, expires_at: datetime) -> None:
        self.credentials = credentials
        self.expires_at = expires_at

    @cached_property
    def dynamodb(self) -> "DynamoDBServiceResource":
        return boto3.resource(
            "dynamodb",
            aws_access_key_id=self.credentials.access_key,
            aws_secret_access_key=self.credentials.secret_key,
            aws_session_token=self.credentials.token,
        )


AssumeRequest = tuple[str, str, tuple[tuple[str, str], ...]]

_sts = boto3.client("sts")
_sessions: OrderedDict[AssumeRequest, RoleSession] = OrderedDict()


def customer_session(customer_id: str, service: str) -> RoleSession:
    return _assume(
        os.environ["ROLE_CUSTOMER_ARN"],
        f"{service}-{customer_id}",
        (("customer_id", customer_id),),
    )


def session_for(principal: Principal, service: str) -> RoleSession:
    if principal.pool is Pool.CUSTOMERS:
        return customer_session(principal.subject, service)
    roles = [env for group, env in STAFF_ROLE_ENV.items() if group in principal.groups]
    if len(roles) != 1:
        raise AccessDenied("a staff token must carry exactly one group")
    return _assume(os.environ[roles[0]], f"{service}-{principal.subject}", ())


def _assume(role_arn: str, session_name: str, tags: tuple[tuple[str, str], ...]) -> RoleSession:
    name = session_name[:64]
    key: AssumeRequest = (role_arn, name, tags)
    cached = _sessions.get(key)
    if cached is not None and datetime.now(UTC) + REFRESH_MARGIN < cached.expires_at:
        _sessions.move_to_end(key)
        return cached
    request: dict[str, Any] = {"RoleArn": role_arn, "RoleSessionName": name, "DurationSeconds": 900}
    if tags:
        request["Tags"] = [{"Key": tag, "Value": value} for tag, value in tags]
    credentials = _sts.assume_role(**request)["Credentials"]
    fresh = RoleSession(
        ReadOnlyCredentials(
            credentials["AccessKeyId"], credentials["SecretAccessKey"], credentials["SessionToken"]
        ),
        credentials["Expiration"],
    )
    _sessions[key] = fresh
    _sessions.move_to_end(key)
    while len(_sessions) > MAX_SESSIONS:
        _sessions.popitem(last=False)
    return fresh


def _groups(claim: object) -> frozenset[str]:
    if isinstance(claim, list):
        return frozenset(str(group) for group in claim)
    if isinstance(claim, str):
        return frozenset(part for part in claim.strip("[]").replace(",", " ").split() if part)
    return frozenset()
