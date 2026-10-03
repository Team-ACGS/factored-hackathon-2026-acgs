import re
from decimal import Decimal
from pathlib import Path

import pytest

from clara_testing.converse import FakeConverse, reply
from core.graphs.model import chat_model
from core.graphs.profiles import ModelProfile, UnknownModel, profile_for, profiles

LOCALS = Path(__file__).parents[3] / "infra" / "environments" / "prd" / "locals.tf"


def test_a_model_without_a_row_fails_loudly() -> None:
    with pytest.raises(UnknownModel, match=r"profiles\.toml"):
        profile_for("us.anthropic.claude-sonnet-5")


def test_the_model_terraform_selects_has_a_profile() -> None:
    [selected] = re.findall(r'bedrock_inference_profile_id\s*=\s*"([^"]+)"', LOCALS.read_text())

    assert profile_for(selected) is profiles()[0]


def test_every_profile_has_a_prompt_and_a_unique_key() -> None:
    assert len({row.key for row in profiles()}) == len(profiles())
    assert all(row.system_prompt.startswith("You are Clara") for row in profiles())


def test_the_cost_of_a_turn_counts_fresh_cached_and_written_input_apart() -> None:
    sonnet = profile_for("us.anthropic.claude-sonnet-4-6")
    steps = [{"input_tokens": 5000, "cache_read": 3000, "cache_write": 1000, "output_tokens": 200}]

    expected = (
        1000 * Decimal("3.30") + 3000 * Decimal("0.33") + 1000 * Decimal("4.125") + 200 * Decimal("16.50")
    ) / 10**6
    assert sonnet.cost(steps) == expected


@pytest.mark.parametrize("row", profiles(), ids=lambda row: row.key)
def test_each_profile_sends_only_the_options_its_model_takes(row: ModelProfile) -> None:
    profile = row
    fake = FakeConverse([reply("hola")])

    chat_model(fake.client(10), profile).invoke("hola")

    [request] = fake.requests
    assert request["modelId"] == profile.id
    assert request["inferenceConfig"]["maxTokens"] == profile.max_output_tokens
    fields = request.get("additionalModelRequestFields", {})
    assert fields == ({"output_config": {"effort": profile.effort}} if profile.effort else {})
