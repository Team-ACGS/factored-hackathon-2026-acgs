import pytest

from core.access import AccessDenied, Pool, Principal, session_for
from harness import CUSTOMERS_POOL_ID, STAFF_POOL_ID, Aws, claims


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

    identity = session_for(principal, "test").client("sts").get_caller_identity()

    assert identity["Arn"].endswith(":assumed-role/clara-test-role-customer/test-c1")


def test_a_staff_session_assumes_the_role_of_its_group(aws: Aws) -> None:
    principal = Principal.from_claims(claims(STAFF_POOL_ID, sub="s1", groups="officers"))

    identity = session_for(principal, "test").client("sts").get_caller_identity()

    assert identity["Arn"].endswith(":assumed-role/clara-test-role-officer/test-s1")


@pytest.mark.parametrize("groups", ["", "agents,officers"])
def test_a_staff_token_without_exactly_one_group_is_denied(aws: Aws, groups: str) -> None:
    with pytest.raises(AccessDenied):
        session_for(Principal.from_claims(claims(STAFF_POOL_ID, groups=groups)), "test")
