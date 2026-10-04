import json
import os
from pathlib import Path
from typing import Any

import boto3
import pytest

from clara_testing.converse import Recorder
from core.graphs.profiles import ModelProfile, profiles
from core.messaging import Message
from core.turn import Turn, run_turn
from demo import DEMO, NOW, RECORDINGS, demo_turn, planted_charge, policy_index, tap
from harness import Aws

pytestmark = pytest.mark.skipif(
    os.environ.get("CLARA_LIVE_BEDROCK") != "1",
    reason="calls the real model; run with CLARA_LIVE_BEDROCK=1 and an AWS profile in CLARA_LIVE_PROFILE",
)


def live_turn(aws: Aws, name: str, profile: ModelProfile) -> tuple[Turn, Recorder]:
    message, history = demo_turn(aws, name)
    return record(name, message, history, profile)


def record(
    name: str, message: Message, history: list[Message], profile: ModelProfile
) -> tuple[Turn, Recorder]:
    recorder = Recorder(boto3.Session(profile_name=os.environ.get("CLARA_LIVE_PROFILE", "personal")))
    policies = policy_index(DEMO[name.removesuffix("_tap")].country)
    result = run_turn(message, history, NOW, profile=profile, clients=recorder.client, policies=policies)
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


@pytest.mark.parametrize("profile", profiles(), ids=lambda row: row.key)
@pytest.mark.parametrize("name", ["unrecognized_es", "unrecognized_pt"])
def test_an_unrecognized_charge_is_picked_from_the_newest_movements_and_its_tap_shows_the_alert(
    aws: Aws, name: str, profile: ModelProfile
) -> None:
    question, history = demo_turn(aws, name)
    first, _ = record(name, question, history, profile)

    assert first.reply.source in ("composed", "repaired")
    [ask] = parts_of(first, "ask")
    assert ask["ask"] == "which_one"
    assert len(ask["options"]) == 5
    assert not parts_of(first, "view")
    planted = planted_charge(aws, question.customer_id)
    assert ask["options"][0]["id"] == planted["transaction_id"]

    tapped, earlier = tap(question, history, first.reply, planted["transaction_id"])
    second, _ = record(f"{name}_tap", tapped, earlier, profile)

    assert second.reply.source in ("composed", "repaired")
    assert "search_movements" not in [call["tool"] for call in second.summary()["tool_calls"]]
    [view] = parts_of(second, "view")
    assert view["view"] == "charge"
    assert view["readings"]["reasons"][0]["reason"] == "score_high"


@pytest.mark.parametrize("profile", profiles(), ids=lambda row: row.key)
@pytest.mark.parametrize("name", ["cancel_es", "cancel_again_es"])
def test_cancelling_a_card_answers_from_the_blocking_policy_and_names_the_series_by_reference(
    aws: Aws, name: str, profile: ModelProfile
) -> None:
    result, _ = live_turn(aws, name, profile)

    assert result.reply.source in ("composed", "repaired")
    cited = [citation["chunk_id"] for part in parts_of(result, "say") for citation in part["citations"]]
    assert any("blocked-card-effects" in chunk for chunk in cited)


@pytest.mark.parametrize("profile", profiles(), ids=lambda row: row.key)
@pytest.mark.parametrize("name", ["that_one_es", "what_now_es"])
def test_the_follow_ups_of_the_second_prd_session_answer_composed(
    aws: Aws, name: str, profile: ModelProfile
) -> None:
    result, _ = live_turn(aws, name, profile)

    assert result.reply.source in ("composed", "repaired")
