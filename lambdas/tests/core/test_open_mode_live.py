import json
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import boto3
import pytest

from clara_testing import FakeBedrockRuntime, FakeS3Vectors, local_embedder, local_index
from clara_testing.converse import Recorder
from core.messaging import customer_message
from core.policies import chunk_id, policy_facts
from core.retrieval import NON_FILTERABLE, ChunkRecord, PolicySearch, VectorRetriever
from core.turn import Turn, run_turn
from core.vectors import SEARCH_DOCUMENT, Vector
from harness import Aws, demo_account, uuid7

pytestmark = pytest.mark.skipif(
    os.environ.get("CLARA_LIVE_BEDROCK") != "1",
    reason="calls the real model; run with CLARA_LIVE_BEDROCK=1 and an AWS profile in CLARA_LIVE_PROFILE",
)

NOW = datetime(2026, 9, 20, 17, 0, tzinfo=UTC)
RECORDINGS = Path(__file__).parent / "recordings"
PROCESS = {
    "PE": (
        "es",
        "Ciclo de una aclaración",
        "El banco revisa tu aclaración y te responde dentro del plazo de revisión de "
        "{{policy.claims.review_time}}.",
    ),
    "BR": (
        "pt",
        "Ciclo de uma contestação",
        "O banco analisa a sua contestação e responde dentro do prazo de análise de "
        "{{policy.claims.review_time}}.",
    ),
}
DEMO = {
    "spend_es": ("PE", "es", "¿Cuánto gasté en Primax este mes vs el pasado?"),
    "case_es": ("PE", "es", "¿cuándo me devuelven la plata de mi aclaración?"),
    "spend_pt": ("BR", "pt-BR", "Quanto gastei no Ipiranga este mês comparado com o mês passado?"),
    "case_pt": ("BR", "pt-BR", "quando vou receber o dinheiro da minha contestação?"),
}


def policy_index(country: str) -> PolicySearch:
    bedrock, vectors = FakeBedrockRuntime(), FakeS3Vectors(NON_FILTERABLE)
    facts = policy_facts()[country]
    language, title, template = PROCESS[country]
    document = f"{country.lower()}-dispute-lifecycle"
    record = ChunkRecord(
        chunk_id=chunk_id(document, 2, facts.version, 3, 1),
        country=country,
        language=facts.language,
        group="disputes",
        topic="dispute_lifecycle",
        doc_type="procedure",
        doc_id=document,
        version=2,
        facts_version=facts.version,
        effective_date=date(2026, 9, 1),
        section=title,
        title=title,
        text=template.replace("{{policy.claims.review_time}}", "…"),
        figures={"claims.review_time": facts.specs["claims.review_time"]},
        page_start=4,
        page_end=5,
        url=f"https://docs.factoredai.sdfles.com/{country}/{document}-v2-f{facts.version}.pdf",
        content_hash=language,
    )
    [embedding] = local_embedder(bedrock).embed([record.text], SEARCH_DOCUMENT)
    local_index(vectors).put([Vector(record.chunk_id, embedding, record.metadata())])
    return PolicySearch(
        VectorRetriever(local_embedder(bedrock), local_index(vectors)),
        {"es": 0.0, "pt": 0.0, "en": 0.0},
        "docs.factoredai.sdfles.com",
    )


def live_turn(aws: Aws, name: str) -> tuple[Turn, Recorder]:
    country, language, text = DEMO[name]
    customer_id = f"c0ffee00-0000-4000-8000-{list(DEMO).index(name) + 1:012d}"
    demo_account(aws, customer_id, country, language, NOW - timedelta(hours=1))
    recorder = Recorder(boto3.Session(profile_name=os.environ.get("CLARA_LIVE_PROFILE", "personal")))
    sent = NOW - timedelta(seconds=1)
    message = customer_message(customer_id, uuid7(), uuid7(int(sent.timestamp() * 1000)), text, sent)
    result = run_turn(message, [], NOW, clients=recorder.client, policies=policy_index(country))
    if os.environ.get("CLARA_RECORD") == "1":
        recorder.save(RECORDINGS / f"{name}.json")
    transcripts = os.environ.get("CLARA_TRANSCRIPTS")
    if transcripts:
        write_transcript(Path(transcripts), name, text, result)
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


def test_the_second_supervisor_step_reads_the_cached_prefix(aws: Aws) -> None:
    result, _ = live_turn(aws, "spend_es")

    steps = [step for step in result.summary()["timings"] if step["node"] == "supervisor"]
    assert len(steps) >= 2
    assert steps[1]["cache_read"] > 0


@pytest.mark.parametrize("name", ["spend_es", "spend_pt"])
def test_a_spend_question_answers_with_the_two_totals_read_by_the_tool(aws: Aws, name: str) -> None:
    result, _ = live_turn(aws, name)

    assert result.reply.source in ("composed", "repaired")
    spend = [fact for fact in result.reply.facts if fact["kind"] == "spend"]
    assert spend
    assert {"total", "compare_total"} <= set(spend[0]["fields"])


@pytest.mark.parametrize("name", ["case_es", "case_pt"])
def test_a_case_question_states_the_case_and_cites_the_bank_s_process(aws: Aws, name: str) -> None:
    result, _ = live_turn(aws, name)

    assert result.reply.source in ("composed", "repaired")
    kinds = {fact["kind"] for fact in result.reply.facts}
    assert {"case", "policy_chunk"} <= kinds
    assert any(part["citations"] for part in result.reply.parts)
