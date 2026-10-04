import json
import os
from datetime import timedelta
from pathlib import Path
from typing import Any

import boto3
import pytest

from clara_testing.converse import Recorder
from core.graphs.profiles import ModelProfile, profiles
from core.messaging import Message, customer_message
from core.turn import Turn, run_turn
from demo import (
    DEMO,
    FLAGGED,
    FREE,
    KEPT,
    NOT_ME_FREE,
    NOTES,
    NOW,
    RECORDINGS,
    base,
    demo_id,
    demo_turn,
    forget,
    kept,
    planted_charge,
    policy_index,
    quiet_choice,
    tap,
)
from harness import Aws

pytestmark = pytest.mark.skipif(
    os.environ.get("CLARA_LIVE_BEDROCK") != "1",
    reason="calls the real model; run with CLARA_LIVE_BEDROCK=1 and an AWS profile in CLARA_LIVE_PROFILE",
)


def live_turn(aws: Aws, name: str, profile: ModelProfile) -> tuple[Turn, Recorder]:
    message, history = demo_turn(aws, name)
    return record(name, message, history, profile)


def record(
    name: str, message: Message, history: list[Message], profile: ModelProfile, country: str | None = None
) -> tuple[Turn, Recorder]:
    recorder = Recorder(boto3.Session(profile_name=os.environ.get("CLARA_LIVE_PROFILE", "personal")))
    policies = policy_index(country or DEMO[base(name)].country)
    result = run_turn(message, history, NOW, profile=profile, clients=recorder.client, policies=policies)
    if os.environ.get("CLARA_RECORD") == "1" and recorder.exchanges:
        recorder.save(RECORDINGS / profile.key / f"{name}.json")
    transcripts = os.environ.get("CLARA_TRANSCRIPTS")
    if transcripts:
        write_transcript(Path(transcripts) / profile.key, name, message.text, result, opened(message, result))
    return result, recorder


def opened(message: Message, result: Turn) -> list[str]:
    table = boto3.resource("dynamodb").Table(os.environ["TABLE_COMPLAINTS"])
    lines: list[str] = []
    for effect in result.reply.effects:
        if effect["type"] != "case_opened":
            continue
        key = {"customer_id": message.customer_id, "complaint_id": effect["complaint_id"]}
        case: dict[str, Any] = dict(table.get_item(Key=key)["Item"])
        lines += [f"Case summary ({case['summary_source']}): {case['summary']}", ""]
        lines += [f"- {point}" for point in case["summary_points"]]
        lines.append("")
    return lines


def write_transcript(folder: Path, name: str, question: str, result: Turn, case: list[str]) -> None:
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
        *case,
        "```json",
        json.dumps(
            {
                "citations": [c for part in result.reply.parts for c in part.get("citations", [])],
                "draft": list(result.reply.draft),
                "effects_detail": list(result.reply.effects),
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
    assert [part["view"] for part in parts_of(first, "view")] == ["movements"]
    planted = planted_charge(aws, question.customer_id)
    assert ask["options"][0]["id"] == planted["transaction_id"]

    tapped, earlier = tap(question, history, first.reply, planted["transaction_id"])
    second, _ = record(f"{name}_tap", tapped, earlier, profile)

    assert second.reply.source in ("composed", "repaired")
    assert "search_movements" not in [call["tool"] for call in second.summary()["tool_calls"]]
    [view] = parts_of(second, "view")
    assert view["view"] == "charge"
    assert view["readings"]["reasons"][0]["reason"] == "score_high"
    assert [part["ask"] for part in parts_of(second, "ask")] == ["was_it_you"]

    quiet = quiet_choice(question, aws, [option["id"] for option in ask["options"]])
    picked, before = tap(question, history, first.reply, quiet)
    third, _ = record(f"{name}_pick", picked, before, profile)

    assert third.reply.source in ("composed", "repaired")
    assert [part["view"] for part in parts_of(third, "view")] == ["charge"]
    assert [part["ask"] for part in parts_of(third, "ask")] == ["recognize_charge"]
    if name in KEPT:
        follow, earlier = kept(picked, before, third.reply, KEPT[name])
        fourth, _ = record(f"{name}_kept", follow, earlier, profile)

        assert fourth.reply.source in ("composed", "repaired")
        assert [part["ask"] for part in parts_of(fourth, "ask")] == ["recognize_charge"]

    said, earlier = tap(picked, before, third.reply, "yes", step=1)
    fifth, _ = record(f"{name}_pick_yes", said, earlier, profile)

    assert fifth.reply.source == "story"
    assert not parts_of(fifth, "ask")

    forget(aws, question.customer_id)
    denied, before_denial = kept(picked, before, third.reply, NOT_ME_FREE[name])
    floored, _ = record(f"{name}_free_no", denied, before_denial, profile)

    assert [part["ask"] for part in parts_of(floored, "ask")] == ["block_card"]

    forget(aws, question.customer_id)
    owned, before_owning = kept(picked, before, third.reply, FREE[name])
    free, _ = record(f"{name}_free", owned, before_owning, profile)

    assert free.reply.source == "story"
    assert free.summary()["writes"] == ["memory:graph"]
    assert not parts_of(free, "ask")


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


@pytest.mark.parametrize("profile", profiles(), ids=lambda row: row.key)
@pytest.mark.parametrize("name", ["topic_es", "topic_pt"])
def test_the_bank_s_charge_button_explains_the_charge_from_history_and_the_bank_asks(
    aws: Aws, name: str, profile: ModelProfile
) -> None:
    result, _ = live_turn(aws, name, profile)

    assert result.reply.source in ("composed", "repaired")
    assert result.summary()["tool_calls"] == []
    assert [part["view"] for part in parts_of(result, "view")] == ["charge"]
    assert [part["ask"] for part in parts_of(result, "ask")] == ["recognize_charge"]


@pytest.mark.parametrize("profile", profiles(), ids=lambda row: row.key)
@pytest.mark.parametrize("name", ["remembered_es", "remembered_pt"])
def test_a_remembered_charge_is_answered_with_the_customer_s_note_and_never_asked_again(
    aws: Aws, name: str, profile: ModelProfile
) -> None:
    result, _ = live_turn(aws, name, profile)

    assert result.reply.source in ("composed", "repaired")
    assert NOTES[DEMO[name].locale] in result.reply.text
    assert not parts_of(result, "ask")


@pytest.mark.parametrize("profile", profiles(), ids=lambda row: row.key)
@pytest.mark.parametrize("name", FLAGGED)
def test_a_flagged_charge_from_the_bank_s_button_is_asked_explained_blocked_and_handed_off(
    aws: Aws, name: str, profile: ModelProfile
) -> None:
    question, history = demo_turn(aws, name)
    first, _ = record(name, question, history, profile)

    assert first.reply.source in ("composed", "repaired")
    assert [part["view"] for part in parts_of(first, "view")] == ["charge"]
    assert [part["ask"] for part in parts_of(first, "ask")] == ["was_it_you"]

    asked_why, earlier = tap(question, history, first.reply, "why")
    why, _ = record(f"{name}_why", asked_why, earlier, profile)

    assert [part["ask"] for part in parts_of(why, "ask")] == ["was_it_you"]

    said_no, before = tap(question, history, first.reply, "no")
    confirm, _ = record(f"{name}_no", said_no, before, profile)

    assert [part["ask"] for part in parts_of(confirm, "ask")] == ["block_card"]

    said_yes, after = tap(said_no, before, confirm.reply, "yes", step=1)
    done, _ = record(f"{name}_block", said_yes, after, profile)

    assert [effect["type"] for effect in done.reply.effects] == ["card_blocked", "case_opened"]
    assert [part["view"] for part in parts_of(done, "view")] == ["case"]


@pytest.mark.parametrize("profile", profiles(), ids=lambda row: row.key)
@pytest.mark.parametrize("name", ["unblock_es", "unblock_pt", "case_es", "case_pt"])
def test_unblock_and_money_get_a_person_and_its_yes_opens_a_service_case(
    aws: Aws, name: str, profile: ModelProfile
) -> None:
    question, history = demo_turn(aws, name)
    first, _ = record(name, question, history, profile)

    assert [part["ask"] for part in parts_of(first, "ask")] == ["talk_to_person"]
    said_yes, earlier = tap(question, history, first.reply, "yes")
    handed, _ = record(f"{name}_yes", said_yes, earlier, profile)

    assert [effect["type"] for effect in handed.reply.effects] == ["case_opened"]


@pytest.mark.parametrize("profile", profiles()[:1], ids=lambda row: row.key)
@pytest.mark.parametrize("locale", ["es", "pt"])
def test_the_deterministic_story_paths_for_the_transcripts(
    aws: Aws, locale: str, profile: ModelProfile
) -> None:
    question, history = demo_turn(aws, f"topic_{locale}")
    asked, _ = record(f"topic_{locale}", question, history, profile)
    said_no, before = tap(question, history, asked.reply, "no")
    card_question, _ = record(f"topic_{locale}_no", said_no, before, profile)
    has_it, after = tap(said_no, before, card_question.reply, "yes", step=1)
    consent, _ = record(f"topic_{locale}_card", has_it, after, profile)
    opened_it, last = tap(has_it, after, consent.reply, "yes", step=2)
    opened, _ = record(f"topic_{locale}_open", opened_it, last, profile)

    assert [effect["type"] for effect in opened.reply.effects] == ["case_opened"]

    lost_text = {"es": "me robaron la tarjeta", "pt": "roubaram o meu cartão"}[locale]
    sent = NOW - timedelta(seconds=2)
    lost_message = customer_message(question.customer_id, demo_id(sent, 0), demo_id(sent, 1), lost_text, sent)
    country = DEMO[f"topic_{locale}"].country
    listed, _ = record(f"lost_{locale}", lost_message, [], profile, country)
    [ask] = parts_of(listed, "ask")
    picked, earlier = tap(lost_message, [], listed.reply, ask["options"][0]["id"])
    confirm, _ = record(f"lost_{locale}_pick", picked, earlier, profile, country)
    said_yes, after_pick = tap(picked, earlier, confirm.reply, "yes", step=1)
    blocked, _ = record(f"lost_{locale}_block", said_yes, after_pick, profile, country)

    assert [effect["type"] for effect in blocked.reply.effects] == ["card_blocked", "case_opened"]


def says_of(result: Turn) -> str:
    return " ".join(part["text"] for part in parts_of(result, "say"))


@pytest.mark.parametrize("profile", profiles(), ids=lambda row: row.key)
@pytest.mark.parametrize("name", ["ten_days_pt", "ten_days_again_pt"])
def test_what_to_do_after_the_bank_s_timeframe_is_answered_with_the_escalation_step_and_its_citation(
    aws: Aws, name: str, profile: ModelProfile
) -> None:
    result, _ = live_turn(aws, name, profile)

    assert result.reply.source in ("composed", "repaired")
    cited = [citation["chunk_id"] for part in parts_of(result, "say") for citation in part["citations"]]
    assert any("-s9-" in chunk for chunk in cited)
    assert all(part["text"].strip() for part in parts_of(result, "say"))


@pytest.mark.parametrize("profile", profiles(), ids=lambda row: row.key)
def test_what_clara_knows_about_the_customer_is_the_fixed_answer(aws: Aws, profile: ModelProfile) -> None:
    result, _ = live_turn(aws, "about_you_pt", profile)

    assert result.reply.source == "say_key"


@pytest.mark.parametrize("profile", profiles(), ids=lambda row: row.key)
@pytest.mark.parametrize("name", ["document_pt", "cannot_tell_pt"])
def test_personal_data_and_what_clara_cannot_tell_are_composed_refusals(
    aws: Aws, name: str, profile: ModelProfile
) -> None:
    result, _ = live_turn(aws, name, profile)

    assert result.reply.source in ("composed", "repaired")
    assert "acesso" in says_of(result)


@pytest.mark.parametrize("profile", profiles(), ids=lambda row: row.key)
def test_a_spanish_message_on_a_portuguese_account_is_answered_in_portuguese(
    aws: Aws, profile: ModelProfile
) -> None:
    result, _ = live_turn(aws, "spanish_pt", profile)

    assert result.reply.source in ("composed", "repaired")
    assert "cartões" in says_of(result) or "cartão" in says_of(result)
    assert "tarjeta" not in says_of(result)


@pytest.mark.parametrize("profile", profiles(), ids=lambda row: row.key)
def test_the_largest_purchase_is_one_row_with_its_view(aws: Aws, profile: ModelProfile) -> None:
    result, _ = live_turn(aws, "largest_pt", profile)

    assert result.reply.source in ("composed", "repaired")
    calls = result.summary()["tool_calls"]
    assert [call["tool"] for call in calls] == ["search_movements"]
    assert [part["view"] for part in parts_of(result, "view")] in (["movement"], ["movements"])


@pytest.mark.parametrize("profile", profiles(), ids=lambda row: row.key)
@pytest.mark.parametrize("name", ["rio_pt", "rio_again_pt"])
def test_where_several_rows_were_is_answered_by_city_counts(
    aws: Aws, name: str, profile: ModelProfile
) -> None:
    result, _ = live_turn(aws, name, profile)

    assert result.reply.source in ("composed", "repaired")
    assert any("by_city}" in part["text"] for part in result.reply.draft if part["type"] == "say")
