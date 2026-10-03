import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from moto.iam.access_control import IAMPolicy, PermissionResult

from clara_testing import FakeBedrockRuntime, FakeS3Vectors, local_embedder, local_index
from clara_testing.converse import FakeConverse, ManualClock, reply, response, throttled, tool_use
from core import access
from core.access import READ_ONLY_POLICY
from core.countries import zone
from core.facts.render import format_money
from core.graphs.open_mode import INPUT_TOKEN_CAP, MAX_STEPS, MAX_TOOL_CALLS, TURN_SECONDS
from core.graphs.prompt import CONTEXT_FIELDS, SYSTEM
from core.messaging import Message, customer_message
from core.policies import chunk_id, policy_facts
from core.retrieval import NON_FILTERABLE, ChunkRecord, PolicySearch, VectorRetriever
from core.turn import Turn, run_turn
from core.vectors import SEARCH_DOCUMENT, Vector
from harness import Aws, DemoAccount, demo_account, uuid7

NOW = datetime(2026, 9, 20, 17, 0, tzinfo=UTC)
CUSTOMER = "c0ffee00-0000-4000-8000-0000000000a1"
THIS_MONTH = {"from": "2026-09-01", "to": "2026-09-20"}
LAST_MONTH = {"from": "2026-08-01", "to": "2026-08-31"}
PRIMAX = {"merchant": "Primax", "period": THIS_MONTH, "compare_period": LAST_MONTH}
SPEND = "f6"
CHUNK = chunk_id("pe-dispute-lifecycle", 2, policy_facts()["PE"].version, 3, 1)


@pytest.fixture
def account(aws: Aws) -> DemoAccount:
    return demo_account(aws, CUSTOMER, "PE", "es", NOW - timedelta(hours=1))


@pytest.fixture
def assumed(aws: Aws, monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    assume_role = access._sts.assume_role

    def recording(**request: Any) -> Any:
        requests.append(request)
        return assume_role(**request)

    monkeypatch.setattr(access._sts, "assume_role", recording)
    return requests


def says(text: str) -> Message:
    sent = NOW - timedelta(seconds=1)
    return customer_message(CUSTOMER, uuid7(), uuid7(int(sent.timestamp() * 1000)), text, sent)


def turn(
    model: FakeConverse, text: str = "¿Cuánto gasté en Primax este mes vs el pasado?", **options: Any
) -> Turn:
    return run_turn(says(text), [], NOW, clients=model.client, **options)


def spent(account: DemoAccount, start: str, end: str) -> Decimal:
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    return sum(
        (
            Decimal(item["amount"])
            for item in account.transactions
            if item["merchant_name"] == "Primax"
            and item["transaction_status"] in ("Approved", "Pending")
            and first
            <= datetime.fromisoformat(item["transaction_date"]).astimezone(zone("PE")).date()
            <= last
        ),
        Decimal(0),
    )


def spend_answer() -> str:
    return (
        f"Este mes gastaste {{{SPEND}.total}} en {{{SPEND}.merchant}} y el mes pasado "
        f"{{{SPEND}.compare_total}}: {{{SPEND}.delta}} de diferencia."
    )


def last_tool_result(request: dict[str, Any]) -> dict[str, Any]:
    [block] = [block for block in request["messages"][-1]["content"] if "toolResult" in block]
    result: dict[str, Any] = block["toolResult"]
    return result


def test_the_answer_states_the_two_totals_and_the_difference_read_from_the_account(
    account: DemoAccount,
) -> None:
    model = FakeConverse([response(tool_use("spend_summary", PRIMAX)), reply(spend_answer())])

    result = turn(model)

    current = spent(account, "2026-09-01", "2026-09-20")
    previous = spent(account, "2026-08-01", "2026-08-31")
    assert current
    assert previous
    assert result.reply.source == "composed"
    assert result.reply.text == (
        f"Este mes gastaste {format_money(current, 'PEN', 'es')} en Primax y el mes pasado "
        f"{format_money(previous, 'PEN', 'es')}: {format_money(abs(current - previous), 'PEN', 'es')} "
        "de diferencia."
    )
    assert result.reply.parts == (
        {"type": "say", "text": result.reply.text, "facts": [SPEND], "citations": []},
    )
    assert [fact["id"] for fact in result.reply.facts] == [SPEND]
    assert result.reply.draft == ({"type": "say", "text": spend_answer()},)


def test_a_value_the_model_typed_is_sent_back_once_with_the_errors_and_the_repair_is_kept(
    account: DemoAccount,
) -> None:
    model = FakeConverse(
        [
            response(tool_use("spend_summary", PRIMAX)),
            reply("Este mes gastaste S/ 120 en Primax."),
            reply(spend_answer()),
        ]
    )

    result = turn(model)

    repair = last_tool_result(model.requests[2])
    assert repair["status"] == "error"
    codes = {error["code"] for error in json.loads(repair["content"][0]["text"])["errors"]}
    assert codes == {"digit_outside_reference", "currency_outside_reference"}
    assert result.reply.source == "repaired"
    check = result.summary()["check"]
    assert check["result"] == "repaired"
    assert set(check["errors"]) == codes


def test_a_second_check_failure_falls_back_to_the_template_from_what_was_read(account: DemoAccount) -> None:
    model = FakeConverse(
        [
            response(tool_use("spend_summary", PRIMAX)),
            reply("Gastaste 120 soles."),
            reply("Gastaste ciento veinte soles, garantizado."),
        ]
    )

    result = turn(model)

    current = spent(account, "2026-09-01", "2026-09-20")
    assert result.reply.source == "fallback"
    assert result.reply.text.startswith(
        f"Gastaste {format_money(current, 'PEN', 'es')}, del 1 al 20 de septiembre"
    )
    assert "120" not in result.reply.text
    assert all(part["type"] == "say" for part in result.reply.parts)
    assert result.summary()["check"]["result"] == "failed"
    assert len(model.requests) == 3


def test_an_unknown_reference_never_reaches_the_customer(account: DemoAccount) -> None:
    model = FakeConverse([reply("Tu saldo es {f99.total}."), reply("Tu saldo es {f98.total}.")])

    result = turn(model, "¿cuál es mi saldo?")

    assert result.reply.source == "fallback"
    assert "{" not in result.reply.text


def test_the_steps_budget_forces_the_reply_on_the_last_step(account: DemoAccount) -> None:
    model = FakeConverse(
        [
            response(tool_use("list_cards", {})),
            response(tool_use("recurring_charges", {})),
            response(tool_use("spend_summary", PRIMAX)),
            reply("Listo."),
        ]
    )

    result = turn(model)

    choices = [request["toolConfig"]["toolChoice"] for request in model.requests]
    assert choices == [{"any": {}}] * (MAX_STEPS - 1) + [{"tool": {"name": "reply"}}]
    assert result.reply.source == "composed"
    assert result.summary()["steps"] == MAX_STEPS


def test_a_model_that_never_replies_stops_after_the_steps_budget(account: DemoAccount) -> None:
    model = FakeConverse([response(tool_use("list_cards", {})) for _ in range(MAX_STEPS + 2)])

    result = turn(model)

    assert len(model.requests) == MAX_STEPS
    assert result.reply.source == "fallback"
    assert result.summary()["exhausted"] == "steps"


def test_up_to_eight_tool_calls_run_and_the_next_step_must_reply(account: DemoAccount) -> None:
    calls = [tool_use("recurring_charges", {}) for _ in range(MAX_TOOL_CALLS)]
    model = FakeConverse([response(*calls), reply("Listo.")])

    result = turn(model)

    assert [call["outcome"] for call in result.summary()["tool_calls"]] == ["ok"] * MAX_TOOL_CALLS
    assert model.requests[1]["toolConfig"]["toolChoice"] == {"tool": {"name": "reply"}}
    assert result.reply.source == "composed"


def test_a_ninth_tool_call_is_refused(account: DemoAccount) -> None:
    calls = [tool_use("recurring_charges", {}) for _ in range(MAX_TOOL_CALLS + 1)]
    model = FakeConverse([response(*calls), reply("Listo.")])

    result = turn(model)

    outcomes = [call["outcome"] for call in result.summary()["tool_calls"]]
    assert outcomes == ["ok"] * MAX_TOOL_CALLS + ["budget"]
    statuses = [block["toolResult"]["status"] for block in model.requests[1]["messages"][-1]["content"]]
    assert statuses == ["success"] * MAX_TOOL_CALLS + ["error"]


def test_a_turn_inside_the_time_budget_bounds_each_call_by_what_is_left(account: DemoAccount) -> None:
    clock = ManualClock()
    model = FakeConverse(
        [response(tool_use("spend_summary", PRIMAX)), reply(spend_answer())], clock=clock, latency=4
    )

    result = turn(model, clock=clock)

    assert result.reply.source == "composed"
    assert model.timeouts == [TURN_SECONDS, TURN_SECONDS - 4]


def test_a_turn_out_of_time_answers_from_what_it_read(account: DemoAccount) -> None:
    clock = ManualClock()
    model = FakeConverse(
        [response(tool_use("spend_summary", PRIMAX)), reply(spend_answer())], clock=clock, latency=10.5
    )

    result = turn(model, clock=clock)

    assert len(model.requests) == 1
    assert result.summary()["exhausted"] == "time"
    assert result.reply.source == "fallback"
    assert result.reply.text.startswith("Gastaste ")


def test_the_input_token_cap_stops_the_next_call(account: DemoAccount) -> None:
    within = FakeConverse(
        [
            response(tool_use("spend_summary", PRIMAX), input_tokens=INPUT_TOKEN_CAP // 2),
            reply(spend_answer()),
        ]
    )
    over = FakeConverse(
        [response(tool_use("spend_summary", PRIMAX), input_tokens=INPUT_TOKEN_CAP), reply(spend_answer())]
    )

    assert turn(within).reply.source == "composed"
    capped = turn(over)
    assert len(over.requests) == 1
    assert capped.summary()["exhausted"] == "input_tokens"
    assert capped.reply.source == "fallback"


def test_a_throttled_call_is_retried_once_then_the_turn_says_it_could_not_check(account: DemoAccount) -> None:
    retried = FakeConverse([throttled(), reply("Hola, ¿en qué te ayudo?")])
    down = FakeConverse([throttled(), throttled()])

    assert turn(retried, "hola").reply.source == "composed"
    result = turn(down, "hola")
    assert result.summary()["exhausted"] == "model_unavailable"
    assert (
        result.reply.text
        == "No pude revisar eso ahora. ¿Quieres intentarlo de nuevo o hablar con una persona?"
    )


def test_the_graph_reads_only_with_the_read_only_session_policy(
    account: DemoAccount, assumed: list[dict[str, Any]]
) -> None:
    access._sessions.clear()
    model = FakeConverse(
        [response(tool_use("spend_summary", PRIMAX), tool_use("case_status", {})), reply("Listo.")]
    )

    turn(model)

    assert assumed
    assert all(request["Policy"] == READ_ONLY_POLICY for request in assumed)
    policy = IAMPolicy(READ_ONLY_POLICY)
    for table in ("messages", "rooms", "products", "transactions", "complaints"):
        arn = f"arn:aws:dynamodb:us-east-1:123456789012:table/clara-test-{table}"
        for action in ("dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem"):
            assert policy.is_action_permitted(action, arn) != PermissionResult.PERMITTED


def test_nothing_volatile_sits_before_the_cache_point(aws: Aws) -> None:
    demo_account(aws, CUSTOMER, "PE", "es", NOW - timedelta(hours=1), given_name="Ana")
    other = "c0ffee00-0000-4000-8000-0000000000b2"
    demo_account(aws, other, "BR", "pt-BR", NOW - timedelta(days=20), given_name="João")
    first = FakeConverse([response(tool_use("spend_summary", PRIMAX)), reply("Listo.")])
    second = FakeConverse([reply("Pronto.")])

    turn(first)
    sent = NOW + timedelta(days=3)
    message = customer_message(other, uuid7(), uuid7(int(sent.timestamp() * 1000)), "oi", sent)
    run_turn(message, [], sent + timedelta(seconds=1), clients=second.client)

    prefixes = {_cached_prefix(request) for request in first.requests + second.requests}
    assert len(prefixes) == 1
    [prefix] = prefixes
    assert len(prefix) > 4 * 1024 * 2
    for volatile in ("Ana", "João", "2026-09-20", "2026-09-23", "Primax", CUSTOMER, other):
        assert volatile not in prefix
    for request in first.requests + second.requests:
        system = request["system"]
        assert [list(block) for block in system] == [["text"], ["cachePoint"], ["text"]]
        assert system[0]["text"] == SYSTEM


def _cached_prefix(request: dict[str, Any]) -> str:
    system = request["system"]
    point = next(index for index, block in enumerate(system) if "cachePoint" in block)
    return json.dumps({"tools": request["toolConfig"]["tools"], "system": system[:point]}, ensure_ascii=False)


def test_the_context_carries_only_the_manifest_fields_and_tool_results_are_tagged_untrusted(
    account: DemoAccount,
) -> None:
    model = FakeConverse([response(tool_use("spend_summary", PRIMAX)), reply("Listo.")])

    turn(model)

    context = model.requests[0]["system"][2]["text"]
    fields = json.loads(context.split("\n", 2)[2])
    assert tuple(sorted(fields)) == tuple(sorted(CONTEXT_FIELDS))
    assert fields["given_name"] == "Ana"
    assert fields["locale"] == "es"
    assert fields["today"] == "2026-09-20"
    assert [fact["kind"] for fact in fields["cards"]] == ["card", "card", "card", "cards"]
    every_request = json.dumps(model.requests, ensure_ascii=False)
    assert f"{CUSTOMER}@example.com" not in every_request
    assert "fraud_score" not in every_request
    assert json.loads(last_tool_result(model.requests[1])["content"][0]["text"])["untrusted"] is True


def test_the_last_three_exchanges_are_in_the_context(account: DemoAccount) -> None:
    room = uuid7()
    history = []
    for index in range(8):
        at = NOW - timedelta(minutes=10 - index)
        question = customer_message(
            CUSTOMER, room, uuid7(int(at.timestamp() * 1000)), f"pregunta {index}", at
        )
        history.append(question)
    message = customer_message(CUSTOMER, room, uuid7(int(NOW.timestamp() * 1000)), "y ahora?", NOW)
    model = FakeConverse([reply("Listo.")])

    run_turn(message, [*history, message], NOW, clients=model.client)

    context = json.loads(model.requests[0]["system"][2]["text"].split("\n", 2)[2])
    assert [entry["text"] for entry in context["exchanges"]] == [f"pregunta {index}" for index in range(2, 8)]


def test_about_you_is_rendered_by_code_from_the_profile_and_the_cards(account: DemoAccount) -> None:
    model = FakeConverse([reply(say_key="about_you")])

    result = turn(model, "¿qué sabes de mí?")

    assert result.reply.source == "say_key"
    assert result.reply.text.startswith(
        "Eres Ana, cliente de LATAM Bank en Perú.\n\nTienes 3 tarjetas: la de crédito"
    )


def test_a_reply_sent_with_other_tools_waits_for_their_results(account: DemoAccount) -> None:
    model = FakeConverse(
        [
            response(tool_use("spend_summary", PRIMAX), tool_use("reply", {"say": ["Listo."]})),
            reply(spend_answer()),
        ]
    )

    result = turn(model)

    results = [block["toolResult"] for block in model.requests[1]["messages"][-1]["content"]]
    assert [entry["status"] for entry in results] == ["success", "error"]
    assert result.reply.source == "composed"


def test_the_turn_summary_carries_no_text_and_no_arguments(account: DemoAccount) -> None:
    model = FakeConverse(
        [
            response(tool_use("spend_summary", PRIMAX), cache_read=0, cache_write=2000),
            reply(spend_answer(), cache_read=2000),
        ]
    )

    summary = turn(model).summary()

    assert summary["tokens"]["cache_read"] == 2000
    assert [(call["tool"], call["outcome"]) for call in summary["tool_calls"]] == [("spend_summary", "ok")]
    serialized = json.dumps(summary)
    assert "Primax" not in serialized
    assert "gastaste" not in serialized.lower()


def policy_index() -> PolicySearch:
    bedrock, vectors = FakeBedrockRuntime(), FakeS3Vectors(NON_FILTERABLE)
    facts = policy_facts()["PE"]
    document = "pe-dispute-lifecycle"
    record = ChunkRecord(
        chunk_id=CHUNK,
        country="PE",
        language=facts.language,
        group="disputes",
        topic="dispute_lifecycle",
        doc_type="procedure",
        doc_id=document,
        version=2,
        facts_version=facts.version,
        effective_date=date(2026, 9, 1),
        section="Plazos de revisión",
        title="Ciclo de una aclaración",
        text="El banco revisa tu aclaración y te responde dentro del plazo de revisión.",
        figures={"claims.review_time": facts.specs["claims.review_time"]},
        page_start=4,
        page_end=5,
        url=f"https://docs.test/PE/{document}-v2-f{facts.version}.pdf",
        content_hash="hash",
    )
    [embedding] = local_embedder(bedrock).embed([record.text], SEARCH_DOCUMENT)
    local_index(vectors).put([Vector(record.chunk_id, embedding, record.metadata())])
    retriever = VectorRetriever(local_embedder(bedrock), local_index(vectors))
    return PolicySearch(retriever, {"es": 0.0, "pt": 0.0, "en": 0.0}, "docs.test")


def test_a_case_answer_cites_the_bank_s_process_with_the_document_and_its_page(account: DemoAccount) -> None:
    claim = account.claim
    assert claim is not None
    model = FakeConverse(
        [
            response(
                tool_use("case_status", {}),
                tool_use("search_policies", {"query": "cuándo me devuelven la plata de mi aclaración"}),
            ),
            reply(
                "Tu aclaración {f6.case_id} está {f6.stage}.",
                "Según el proceso del banco, la revisión toma hasta "
                f"{{p1.figures.claims.review_time}} [p:{CHUNK}].",
            ),
        ]
    )

    result = turn(model, "¿cuándo me devuelven la plata de mi aclaración?", policies=policy_index())

    assert result.reply.source == "composed"
    case, process = result.reply.parts
    assert case["citations"] == []
    assert process["citations"] == [
        {
            "chunk_id": CHUNK,
            "title": "Ciclo de una aclaración",
            "page": 4,
            "url": f"https://docs.test/PE/pe-dispute-lifecycle-v2-f{policy_facts()['PE'].version}.pdf#page=4",
        }
    ]
    assert f"[p:{CHUNK}]" not in process["text"]
    assert {fact["id"] for fact in result.reply.facts} == {"f6", "p1"}
