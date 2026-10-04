import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from moto.iam.access_control import IAMPolicy, PermissionResult

from clara_testing import FakeBedrockRuntime, FakeS3Vectors, local_embedder, local_index
from clara_testing.converse import FakeConverse, ManualClock, reply, response, throttled, tool_use
from core import access, observability
from core.access import READ_ONLY_POLICY
from core.countries import zone
from core.facts.render import format_money
from core.graphs import open_mode
from core.graphs.open_mode import INPUT_TOKEN_CAP, MAX_STEPS, MAX_TOOL_CALLS, TURN_SECONDS
from core.graphs.profiles import profiles
from core.graphs.prompt import CONTEXT_FIELDS
from core.messaging import Message, customer_message, reply_to
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
DEFAULT = profiles()[0]
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
    return run_turn(says(text), [], NOW, profile=DEFAULT, clients=model.client, **options)


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
    assert result.reply.text == "No pude revisar eso ahora. Intenta de nuevo en un momento."


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
    run_turn(message, [], sent + timedelta(seconds=1), profile=DEFAULT, clients=second.client)

    prefixes = {_cached_prefix(request) for request in first.requests + second.requests}
    assert len(prefixes) == 1
    [prefix] = prefixes
    assert len(prefix) > 4 * 1024 * 2
    for volatile in ("Ana", "João", "2026-09-20", "2026-09-23", "Primax", CUSTOMER, other):
        assert volatile not in prefix
    for request in first.requests + second.requests:
        system = request["system"]
        assert [list(block) for block in system] == [["text"], ["cachePoint"], ["text"]]
        assert system[0]["text"] == DEFAULT.system_prompt


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

    run_turn(message, [*history, message], NOW, profile=DEFAULT, clients=model.client)

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


def test_a_crash_inside_the_graph_answers_from_what_was_read_and_is_counted(
    account: DemoAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    counted: list[str] = []
    monkeypatch.setattr(observability.metrics, "add_metric", lambda name, **_: counted.append(name))

    def broken(*_: object) -> list[object]:
        raise KeyError("boom")

    monkeypatch.setattr(open_mode, "check", broken)
    model = FakeConverse([response(tool_use("spend_summary", PRIMAX)), reply(spend_answer())])

    result = turn(model)

    current = spent(account, "2026-09-01", "2026-09-20")
    assert result.reply.source == "fallback"
    assert result.reply.text.startswith(f"Gastaste {format_money(current, 'PEN', 'es')}")
    assert result.summary()["exhausted"] == "crashed"
    assert counted == ["TurnsCrashed"]


SEARCH: dict[str, Any] = {
    "merchant": "Primax",
    "date_from": "2026-08-01",
    "date_to": "2026-09-20",
    "limit": 2,
}
SIMILAR: dict[str, Any] = {"merchant": "Primax", "date_from": "2026-09-11", "date_to": "2026-09-12"}


def reply_with(say: str, **extra: Any) -> dict[str, Any]:
    return response(tool_use("reply", {"say": [say], **extra}))


def primax_rows(account: DemoAccount, search: dict[str, Any] = SEARCH) -> list[dict[str, Any]]:
    first, last = date.fromisoformat(search["date_from"]), date.fromisoformat(search["date_to"])
    rows = [
        item
        for item in account.transactions
        if item["merchant_name"] == "Primax"
        and first <= datetime.fromisoformat(item["transaction_date"]).astimezone(zone("PE")).date() <= last
    ]
    return sorted(rows, key=lambda item: (item["transaction_date"], item["transaction_id"]), reverse=True)


def test_a_movements_answer_carries_the_view_of_the_rows_read_with_their_cards(account: DemoAccount) -> None:
    model = FakeConverse(
        [
            response(tool_use("search_movements", SEARCH)),
            reply_with("Encontré {f8.count}.", view={"type": "movements", "facts": ["f8"]}),
        ]
    )

    result = turn(model, "¿Qué compras hice en Primax?")

    [view] = [part for part in result.reply.parts if part["type"] == "view"]
    rows = primax_rows(account)
    assert view["items"] == [
        {"product_id": row["product_id"], "transaction_id": row["transaction_id"]} for row in rows[:2]
    ]
    assert view["readings"]["count"] == f"{len(rows)} movimientos"
    assert {"type": "view", "view": "movements", "facts": ["f8"]} in result.reply.draft
    assert "f8" in [fact["id"] for fact in result.reply.facts]


def test_a_view_of_a_fact_not_read_this_turn_is_sent_back_and_never_reaches_the_client(
    account: DemoAccount,
) -> None:
    model = FakeConverse(
        [
            response(tool_use("search_movements", SEARCH)),
            reply_with("Encontré {f8.count}.", view={"type": "movements", "facts": ["f42"]}),
            reply_with("Encontré {f8.count}.", view={"type": "charge", "facts": ["f6"]}),
        ]
    )

    result = turn(model, "¿Qué compras hice en Primax?")

    repair = json.loads(last_tool_result(model.requests[2])["content"][0]["text"])
    assert [error["code"] for error in repair["errors"]] == ["view_fact_unknown"]
    assert result.reply.source == "fallback"
    assert result.summary()["check"]["errors"] == ["view_fact_unknown", "view_fact_unfit"]
    assert all(part.get("view") != "charge" for part in result.reply.parts)


def test_an_ask_outside_allowed_asks_never_reaches_the_client(account: DemoAccount) -> None:
    model = FakeConverse(
        [
            response(tool_use("search_movements", SEARCH)),
            reply_with("Encontré {f8.count}.", ask={"type": "show", "facts": ["f6"]}),
            reply_with("Encontré {f8.count}.", ask={"type": "which_one", "facts": ["f6"]}),
        ]
    )

    result = turn(model, "¿Qué compras hice en Primax?")

    assert result.summary()["check"]["errors"] == ["ask_fact_unfit", "ask_options_count"]
    assert result.reply.source == "fallback"
    assert not [part for part in result.reply.parts if part["type"] == "ask"]


def test_two_matching_charges_yield_which_one_and_the_tap_resolves_it_without_a_second_search(
    account: DemoAccount,
) -> None:
    rows = primax_rows(account, SIMILAR)
    asking = FakeConverse(
        [
            response(tool_use("search_movements", SIMILAR)),
            reply_with(
                "Veo estos cargos en {f6.merchant}, ¿cuál es?",
                ask={"type": "which_one", "facts": ["f6", "f7"]},
            ),
        ]
    )
    question = says("¿Qué es este cargo de Primax?")
    first = run_turn(question, [], NOW, profile=DEFAULT, clients=asking.client)

    [ask] = [part for part in first.reply.parts if part["type"] == "ask"]
    assert ask["prompt"] == "¿Cuál es?"
    assert [option["id"] for option in ask["options"]] == [row["transaction_id"] for row in rows[:2]]
    assert ask["options"][0]["label"].startswith(
        f"Primax · {format_money(Decimal(rows[0]['amount']), 'PEN', 'es')} · "
    )
    asked = reply_to(
        question, "assistant", first.reply.text, NOW, first.reply.parts, first.reply.facts, first.reply.draft
    )
    tapped_at = NOW - timedelta(milliseconds=500)
    tap = customer_message(
        CUSTOMER,
        question.room_id,
        uuid7(int(tapped_at.timestamp() * 1000)),
        ask["options"][1]["label"],
        tapped_at,
        input={"ask_id": asked.message_id, "option": rows[1]["transaction_id"]},
    )
    answering = FakeConverse([reply_with("Es tu compra en {f6.charge.merchant} por {f6.charge.amount}.")])

    second = run_turn(tap, [question, asked], NOW, profile=DEFAULT, clients=answering.client)

    context = json.loads(answering.requests[0]["system"][2]["text"].split("\n", 2)[2])
    assert context["choice"]["ask"] == "which_one"
    assert context["choice"]["option"] == rows[1]["transaction_id"]
    assert context["choice"]["facts"][0]["kind"] == "charge"
    assert second.route == "choice"
    assert second.summary()["tool_calls"] == []
    assert second.reply.text == (
        f"Es tu compra en Primax por {format_money(Decimal(rows[1]['amount']), 'PEN', 'es')}."
    )


def test_a_stale_or_unknown_tap_is_free_text(account: DemoAccount) -> None:
    question = says("¿Qué es este cargo de Primax?")
    asking = FakeConverse(
        [
            response(tool_use("search_movements", SIMILAR)),
            reply_with("¿Cuál?", ask={"type": "which_one", "facts": ["f6", "f7"]}),
        ]
    )
    first = run_turn(question, [], NOW, profile=DEFAULT, clients=asking.client)
    asked = reply_to(
        question, "assistant", first.reply.text, NOW, first.reply.parts, first.reply.facts, first.reply.draft
    )
    tapped_at = NOW - timedelta(milliseconds=500)

    for chosen in (
        {"ask_id": uuid7(), "option": primax_rows(account, SIMILAR)[0]["transaction_id"]},
        {"ask_id": asked.message_id, "option": "tx-9"},
    ):
        tap = customer_message(
            CUSTOMER,
            question.room_id,
            uuid7(int(tapped_at.timestamp() * 1000)),
            "esa",
            tapped_at,
            input=chosen,
        )
        model = FakeConverse([reply("Listo.")])
        result = run_turn(tap, [question, asked], NOW, profile=DEFAULT, clients=model.client)
        assert result.route == "open_mode"
        context = json.loads(model.requests[0]["system"][2]["text"].split("\n", 2)[2])
        assert context["choice"] is None


def test_each_tool_round_announces_one_status_from_its_tool_family(account: DemoAccount) -> None:
    announced: list[tuple[str, int]] = []
    model = FakeConverse(
        [
            response(tool_use("search_movements", SEARCH), tool_use("spend_summary", PRIMAX)),
            response(tool_use("search_policies", {"query": "¿cuánto demora una aclaración?"})),
            reply("Listo."),
        ]
    )

    result = turn(model, on_status=lambda status, round_: announced.append((status, round_)))

    assert announced == [("movements", 1), ("policies", 2)]
    assert [step["node"] for step in result.summary()["timings"]].count("status") == 2


def test_a_failing_status_never_fails_the_turn(account: DemoAccount) -> None:
    def broken(status: str, round_: int) -> None:
        raise TimeoutError("realtime is slow")

    model = FakeConverse([response(tool_use("spend_summary", PRIMAX)), reply(spend_answer())])

    result = turn(model, on_status=broken)

    assert result.reply.source == "composed"


def test_the_model_sees_five_rows_of_a_search_and_is_told_how_many_it_does_not(account: DemoAccount) -> None:
    model = FakeConverse([response(tool_use("search_movements", {**SEARCH, "limit": 25})), reply("Listo.")])

    turn(model, "¿Qué compras hice en Primax?")

    result = json.loads(last_tool_result(model.requests[1])["content"][0]["text"])
    rows = primax_rows(account)
    assert [fact["kind"] for fact in result["facts"]].count("movement") == 5
    assert (result["rows_shown"], result["rows_not_shown"]) == (5, len(rows) - 5)


def test_a_search_the_model_limited_is_told_how_many_matches_it_did_not_read(account: DemoAccount) -> None:
    model = FakeConverse([response(tool_use("search_movements", SEARCH)), reply("Listo.")])

    turn(model, "¿Qué compras hice en Primax?")

    result = json.loads(last_tool_result(model.requests[1])["content"][0]["text"])
    assert (result["rows_shown"], result["rows_not_shown"]) == (2, len(primax_rows(account)) - 2)


def test_a_show_tap_gives_the_model_the_same_five_rows_and_the_rest_by_count(account: DemoAccount) -> None:
    question = says("¿Cuánto gasté en Primax?")
    asking = FakeConverse(
        [
            response(tool_use("spend_summary", PRIMAX)),
            reply_with(spend_answer(), ask={"type": "show", "facts": [SPEND]}),
        ]
    )
    first = run_turn(question, [], NOW, profile=DEFAULT, clients=asking.client)
    asked = reply_to(
        question, "assistant", first.reply.text, NOW, first.reply.parts, first.reply.facts, first.reply.draft
    )
    tapped_at = NOW - timedelta(milliseconds=500)
    tap = customer_message(
        CUSTOMER,
        question.room_id,
        uuid7(int(tapped_at.timestamp() * 1000)),
        "Ver esos movimientos",
        tapped_at,
        input={"ask_id": asked.message_id, "option": "movements"},
    )
    model = FakeConverse([reply("Listo.")])

    run_turn(tap, [question, asked], NOW, profile=DEFAULT, clients=model.client)

    choice = json.loads(model.requests[0]["system"][2]["text"].split("\n", 2)[2])["choice"]
    assert [fact["kind"] for fact in choice["facts"]].count("movement") == 5
    assert choice["rows_shown"] == 5
    assert choice["rows_not_shown"] > 0


def test_the_turn_summary_counts_what_code_tidied_before_the_check(account: DemoAccount) -> None:
    model = FakeConverse(
        [response(tool_use("spend_summary", PRIMAX)), reply(f"Hiciste {{{SPEND}.count}} compras — en total.")]
    )

    summary = turn(model).summary()

    assert summary["check"]["tidied"] == {"doubled_noun": 1, "dash": 1}
    assert summary["source"] == "composed"


def test_which_one_over_some_of_more_matching_charges_is_sent_back(account: DemoAccount) -> None:
    model = FakeConverse(
        [
            response(tool_use("search_movements", SEARCH)),
            reply_with("¿Cuál es?", ask={"type": "which_one", "facts": ["f6", "f7"]}),
            reply_with("Encontré {f8.count}; dime la fecha o el monto del cargo."),
        ]
    )

    result = turn(model, "¿Qué es este cargo de Primax?")

    assert result.summary()["check"]["errors"] == ["ask_options_partial"]
    assert result.reply.source == "repaired"


def broken_replies() -> list[dict[str, Any]]:
    return [reply("Gastaste 120 soles."), reply("Gastaste ciento veinte soles.")]


def test_the_fallback_of_a_movements_question_emits_no_memory_line(account: DemoAccount) -> None:
    model = FakeConverse(
        [response(tool_use("search_movements", SEARCH), tool_use("recall", {})), *broken_replies()]
    )

    result = turn(model, "¿Qué compras hice en Primax?")

    assert result.reply.source == "fallback"
    assert result.reply.text.startswith(f"Encontré {len(primax_rows(account))} movimientos")
    assert "contado" not in result.reply.text
    assert "nota" not in result.reply.text


def test_the_fallback_answers_from_the_last_tool_round_only(account: DemoAccount) -> None:
    model = FakeConverse(
        [
            response(tool_use("spend_summary", PRIMAX)),
            response(tool_use("search_movements", SEARCH)),
            *broken_replies(),
        ]
    )

    result = turn(model, "¿Qué compras hice en Primax?")

    assert result.reply.source == "fallback"
    assert "Gastaste" not in result.reply.text
    assert result.reply.text.startswith("Encontré")


def test_a_policy_search_without_match_stands_alone_in_the_fallback(account: DemoAccount) -> None:
    strict = policy_index()
    model = FakeConverse(
        [
            response(
                tool_use("search_policies", {"query": "¿Qué pasa si cancelo mi tarjeta?"}),
                tool_use("recurring_charges", {}),
            ),
            *broken_replies(),
        ]
    )

    result = turn(
        model,
        "¿Qué pasa si cancelo mi tarjeta?",
        policies=PolicySearch(strict.retriever, {"es": 0.99, "pt": 0.99, "en": 0.99}, "docs.test"),
    )

    assert result.reply.source == "fallback"
    assert result.reply.text == "No tengo información del banco sobre eso."


def test_a_repair_names_every_error_of_a_reply_that_mixes_them(account: DemoAccount) -> None:
    model = FakeConverse(
        [
            response(tool_use("search_movements", SEARCH)),
            reply_with(
                "Es una de hoy, {f8.count}.",
                view={"type": "movements", "facts": ["f8"]},
                ask={"type": "show", "facts": ["f6"]},
            ),
            reply_with("Encontré {f8.count}.", view={"type": "movements", "facts": ["f8"]}),
        ]
    )

    result = turn(model, "es una de hoy")

    repair = json.loads(last_tool_result(model.requests[2])["content"][0]["text"])
    codes = [error["code"] for error in repair["errors"]]
    assert set(codes) >= {"date_outside_reference", "show_with_view"}
    assert all(code in repair["instruction"] for code in codes)
    assert result.reply.source == "repaired"


def test_an_unrecognized_charge_is_picked_from_the_newest_movements_and_the_tap_opens_its_charge(
    account: DemoAccount,
) -> None:
    newest = sorted(
        account.transactions, key=lambda item: (item["transaction_date"], item["transaction_id"])
    )[-5:][::-1]
    asking = FakeConverse(
        [
            response(tool_use("search_movements", {"limit": 5})),
            reply_with(
                "Estos son tus movimientos más recientes, ¿cuál no reconoces? Si no está, dime su fecha.",
                ask={"type": "which_one", "facts": ["f6", "f7", "f8", "f9", "f10"]},
            ),
        ]
    )
    question = says("hay una transacción que no reconozco")
    first = run_turn(question, [], NOW, profile=DEFAULT, clients=asking.client)

    note = json.loads(last_tool_result(asking.requests[1])["content"][0]["text"])["note"]
    assert "which_one" in note
    assert first.reply.source == "composed"
    [ask] = [part for part in first.reply.parts if part["type"] == "ask"]
    assert [option["id"] for option in ask["options"]] == [row["transaction_id"] for row in newest]
    asked = reply_to(
        question, "assistant", first.reply.text, NOW, first.reply.parts, first.reply.facts, first.reply.draft
    )
    tapped_at = NOW - timedelta(milliseconds=500)
    tap = customer_message(
        CUSTOMER,
        question.room_id,
        uuid7(int(tapped_at.timestamp() * 1000)),
        ask["options"][2]["label"],
        tapped_at,
        input={"ask_id": asked.message_id, "option": newest[2]["transaction_id"]},
    )
    answering = FakeConverse(
        [reply_with("Es tu compra en {f6.charge.merchant}.", view={"type": "charge", "facts": ["f6"]})]
    )

    second = run_turn(tap, [question, asked], NOW, profile=DEFAULT, clients=answering.client)

    assert second.summary()["tool_calls"] == []
    [view] = [part for part in second.reply.parts if part["type"] == "view"]
    assert view["view"] == "charge"
    assert view["items"] == [
        {"product_id": newest[2]["product_id"], "transaction_id": newest[2]["transaction_id"]}
    ]
