import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import boto3

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


def customer_session(customer_id: str, service: str) -> boto3.Session:
    return _assume(
        os.environ["ROLE_CUSTOMER_ARN"],
        f"{service}-{customer_id}",
        [{"Key": "customer_id", "Value": customer_id}],
    )


def session_for(principal: Principal, service: str) -> boto3.Session:
    if principal.pool is Pool.CUSTOMERS:
        return customer_session(principal.subject, service)
    roles = [env for group, env in STAFF_ROLE_ENV.items() if group in principal.groups]
    if len(roles) != 1:
        raise AccessDenied("a staff token must carry exactly one group")
    return _assume(os.environ[roles[0]], f"{service}-{principal.subject}", [])


def _assume(role_arn: str, session_name: str, tags: list[dict[str, str]]) -> boto3.Session:
    request: dict[str, Any] = {
        "RoleArn": role_arn,
        "RoleSessionName": session_name[:64],
        "DurationSeconds": 900,
    }
    if tags:
        request["Tags"] = tags
    credentials = boto3.client("sts").assume_role(**request)["Credentials"]
    return boto3.Session(
        aws_access_key_id=credentials["AccessKeyId"],
        aws_secret_access_key=credentials["SecretAccessKey"],
        aws_session_token=credentials["SessionToken"],
    )


def _groups(claim: object) -> frozenset[str]:
    if isinstance(claim, list):
        return frozenset(str(group) for group in claim)
    if isinstance(claim, str):
        return frozenset(part for part in claim.strip("[]").replace(",", " ").split() if part)
    return frozenset()
