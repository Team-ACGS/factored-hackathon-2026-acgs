import pytest

from core.cases import case_code, case_type


@pytest.mark.parametrize(
    ("complaint_id", "opened_at", "code"),
    [
        ("0199a3f2-5c1e-7b4d-9a2e-3f6c8d1e2a4b", "2026-09-12T15:04:05.123Z", "CLR-2026-821217"),
        ("0193f1aa-0000-7000-8000-000000000001", "2027-01-01T00:00:00.000Z", "CLR-2027-732441"),
    ],
)
def test_the_case_code_equals_the_apps_claim_id(complaint_id: str, opened_at: str, code: str) -> None:
    assert case_code(complaint_id, opened_at) == code


@pytest.mark.parametrize(
    ("area", "kind"), [("fraud", "fraud"), ("claims", "claim"), ("service", "service"), ("Tarjetas", "claim")]
)
def test_the_case_type_comes_from_the_area(area: str, kind: str) -> None:
    assert case_type(area) == kind
