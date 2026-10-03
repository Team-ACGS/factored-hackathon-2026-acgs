import json
import os
from pathlib import Path
from typing import Any

import boto3
import pytest

from clara_testing.converse import Recorder
from core.graphs.profiles import ModelProfile, profiles
from core.turn import Turn, run_turn
from demo import DEMO, NOW, RECORDINGS, demo_turn_message, policy_index
from harness import Aws

pytestmark = pytest.mark.skipif(
    os.environ.get("CLARA_LIVE_BEDROCK") != "1",
    reason="calls the real model; run with CLARA_LIVE_BEDROCK=1 and an AWS profile in CLARA_LIVE_PROFILE",
)


def live_turn(aws: Aws, name: str, profile: ModelProfile) -> tuple[Turn, Recorder]:
    message = demo_turn_message(aws, name)
    recorder = Recorder(boto3.Session(profile_name=os.environ.get("CLARA_LIVE_PROFILE", "personal")))
    policies = policy_index(DEMO[name][0])
    result = run_turn(message, [], NOW, profile=profile, clients=recorder.client, policies=policies)
    if os.environ.get("CLARA_RECORD") == "1":
        recorder.save(RECORDINGS / profile.key / f"{name}.json")
    transcripts = os.environ.get("CLARA_TRANSCRIPTS")
    if transcripts:
        write_transcript(Path(transcripts) / profile.key, name, message.text, result)
    return result, recorder


def write_transcript(folder: Path, name: str, question: str, result: Turn) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = result.summary()
    lines = [
        f"## {name}",
        "",
        f"Customer: {question}",
        "",
        f"Clara ({summary['source']}, {summary['duration_ms']} ms):",
        "",
        *[
            f"> {part['text']}" if part["type"] == "say" else f"[{json.dumps(part, ensure_ascii=False)}]"
            for part in result.reply.parts
        ],
        "",
        "```json",
        json.dumps(
            {
                "citations": [c for part in result.reply.parts for c in part.get("citations", [])],
                "draft": list(result.reply.draft),
                **summary,
            },
            ensure_ascii=False,
            indent=1,
        ),
        "```",
        "",
    ]
    (folder / f"{name}.md").write_text("\n".join(lines))


def test_the_second_supervisor_step_of_the_default_model_reads_the_cached_prefix(aws: Aws) -> None:
    result, _ = live_turn(aws, "spend_es", profiles()[0])

    steps = [step for step in result.summary()["timings"] if step["node"] == "supervisor"]
    assert len(steps) >= 2
    assert steps[1]["cache_read"] > 0


@pytest.mark.parametrize("profile", profiles(), ids=lambda row: row.key)
@pytest.mark.parametrize("name", ["spend_es", "spend_pt"])
def test_a_spend_question_answers_with_the_two_totals_read_by_the_tool(
    aws: Aws, name: str, profile: ModelProfile
) -> None:
    result, _ = live_turn(aws, name, profile)

    assert result.reply.source in ("composed", "repaired")
    spend = [fact for fact in result.reply.facts if fact["kind"] == "spend"]
    assert spend
    assert {"total", "compare_total"} <= set(spend[0]["fields"])


@pytest.mark.parametrize("profile", profiles(), ids=lambda row: row.key)
@pytest.mark.parametrize("name", ["case_es", "case_pt"])
def test_a_case_question_states_the_case_and_cites_the_bank_s_process(
    aws: Aws, name: str, profile: ModelProfile
) -> None:
    result, _ = live_turn(aws, name, profile)

    assert result.reply.source in ("composed", "repaired")
    kinds = {fact["kind"] for fact in result.reply.facts}
    assert {"case", "policy_chunk"} <= kinds
    assert any(part["citations"] for part in result.reply.parts)


def parts_of(result: Turn, kind: str) -> list[dict[str, Any]]:
    return [part for part in result.reply.parts if part["type"] == kind]


@pytest.mark.parametrize("profile", profiles(), ids=lambda row: row.key)
@pytest.mark.parametrize("name", ["movements_es", "visa_es"])
def test_a_long_movements_question_is_composed_with_the_movements_view_or_a_choice(
    aws: Aws, name: str, profile: ModelProfile
) -> None:
    result, _ = live_turn(aws, name, profile)

    assert result.reply.source in ("composed", "repaired")
    views = [part["view"] for part in parts_of(result, "view")]
    asks = [part["ask"] for part in parts_of(result, "ask")]
    assert views == ["movements"] or asks == ["which_one"]


@pytest.mark.parametrize("profile", profiles(), ids=lambda row: row.key)
def test_a_cards_question_shows_the_cards_view(aws: Aws, profile: ModelProfile) -> None:
    result, _ = live_turn(aws, "cards_pt", profile)

    assert result.reply.source in ("composed", "repaired")
    assert [part["view"] for part in parts_of(result, "view")] == ["cards"]


@pytest.mark.parametrize("profile", profiles(), ids=lambda row: row.key)
def test_a_single_charge_question_shows_a_charge_or_asks_which_one(aws: Aws, profile: ModelProfile) -> None:
    result, _ = live_turn(aws, "charge_pt", profile)

    assert result.reply.source in ("composed", "repaired")
    views = [part["view"] for part in parts_of(result, "view")]
    asks = [part["ask"] for part in parts_of(result, "ask")]
    assert set(views) & {"charge", "movement", "movements", "history"} or asks == ["which_one"]
