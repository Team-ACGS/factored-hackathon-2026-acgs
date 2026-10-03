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
        *[f"> {part['text']}" for part in result.reply.parts],
        "",
        "```json",
        json.dumps(
            {
                "citations": [c for part in result.reply.parts for c in part["citations"]],
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
