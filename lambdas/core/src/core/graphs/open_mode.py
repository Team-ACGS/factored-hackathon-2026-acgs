import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache
from operator import add
from typing import TYPE_CHECKING, Annotated, Any, Literal, TypedDict

from botocore.exceptions import BotoCoreError, ClientError
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.messages.tool import ToolCall
from langchain_core.runnables import Runnable
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from core import answers
from core.answers import SayKey
from core.facts import Part, Say, check, fallback
from core.facts.values import Ledger
from core.graphs.model import Clients, bedrock_clients, chat_model
from core.graphs.prompt import MAX_SAY_CHARS, MAX_SAYS, REPLY, SYSTEM, Context, tool_result, tool_specs
from core.replies import Reply, Source, compose
from core.tools import TOOLS, ToolContext, call

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime import BedrockRuntimeClient

MAX_STEPS = 4
MAX_TOOL_CALLS = 8
TURN_SECONDS = 12.0
INPUT_TOKEN_CAP = 60_000
MIN_CALL_SECONDS = 2.0
MODEL_ATTEMPTS = 2
RECURSION_LIMIT = 4 * MAX_STEPS + 4
RETRYABLE = frozenset(
    {
        "ThrottlingException",
        "ServiceUnavailableException",
        "InternalServerException",
        "ModelNotReadyException",
    }
)
CACHE_POINT = {"cachePoint": {"type": "default"}}

Exhausted = Literal["steps", "time", "input_tokens", "model_unavailable", "no_reply"]
Next = Literal["tools", "facts_check", "supervisor", "fallback", "finalize"]


class ModelUnavailable(Exception):
    pass


class ReplyArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    say: tuple[str, ...] | None = Field(None, min_length=1, max_length=MAX_SAYS)
    say_key: SayKey | None = None

    @model_validator(mode="after")
    def one_kind(self) -> "ReplyArgs":
        if (self.say is None) == (self.say_key is None):
            raise ValueError("pass either say or say_key")
        if self.say is not None and any(not text.strip() or len(text) > MAX_SAY_CHARS for text in self.say):
            raise ValueError(f"each say is 1 to {MAX_SAY_CHARS} characters")
        return self


@dataclass
class Metrics:
    steps: list[dict[str, Any]] = field(default_factory=list)
    tools: list[dict[str, Any]] = field(default_factory=list)
    check_errors: list[str] = field(default_factory=list)
    exhausted: Exhausted | None = None

    def tokens(self) -> dict[str, int]:
        keys = ("input_tokens", "output_tokens", "cache_read", "cache_write")
        return {key: sum(int(step.get(key, 0)) for step in self.steps) for key in keys}


@dataclass
class OpenModeRun:
    text: str
    context: Context
    ledger: Ledger
    tools: ToolContext
    clients: Clients = bedrock_clients
    clock: Callable[[], float] = time.monotonic
    model_id: str | None = None
    started: float = 0.0
    model_steps: int = 0
    tool_calls: int = 0
    repairs: int = 0
    input_tokens: int = 0
    tool_facts: list[str] = field(default_factory=list)
    metrics: Metrics = field(default_factory=Metrics)
    reply: Reply | None = None

    def remaining(self) -> float:
        return TURN_SECONDS - (self.clock() - self.started)

    def system(self) -> SystemMessage:
        return SystemMessage(content=[{"type": "text", "text": SYSTEM}, CACHE_POINT, self.context.block()])


class State(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add]
    next: Next
    parts: list[Part]
    source: Source


def supervisor(state: State, runtime: Runtime[OpenModeRun]) -> State:
    run = runtime.context
    reason = _exhausted(run)
    if reason is not None:
        run.metrics.exhausted = reason
        return {"next": "fallback"}
    forced = run.model_steps == MAX_STEPS - 1 or run.tool_calls >= MAX_TOOL_CALLS
    started = run.clock()
    try:
        message = _invoke(run, state["messages"], forced)
    except ModelUnavailable:
        run.metrics.exhausted = "model_unavailable"
        return {"next": "fallback"}
    run.model_steps += 1
    usage = message.usage_metadata or {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    details = usage.get("input_token_details") or {}
    run.input_tokens += usage["input_tokens"]
    run.metrics.steps.append(
        {
            "node": "supervisor",
            "ms": round((run.clock() - started) * 1000),
            "forced_reply": forced,
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
            "cache_read": details.get("cache_read", 0),
            "cache_write": details.get("cache_creation", 0),
        }
    )
    calls = message.tool_calls
    if not calls:
        run.metrics.exhausted = "no_reply"
        return {"next": "fallback"}
    if len(calls) == 1 and calls[0]["name"] == REPLY:
        return {"messages": [message], "next": "facts_check"}
    return {"messages": [message], "next": "tools"}


def tools(state: State, runtime: Runtime[OpenModeRun]) -> State:
    run = runtime.context
    last = state["messages"][-1]
    assert isinstance(last, AIMessage)
    return {"messages": [_run_tool(run, tool_call) for tool_call in last.tool_calls], "next": "supervisor"}


def facts_check(state: State, runtime: Runtime[OpenModeRun]) -> State:
    run = runtime.context
    last = state["messages"][-1]
    assert isinstance(last, AIMessage)
    reply_call = last.tool_calls[0]
    started = run.clock()
    parts, source, errors = _checked(run, reply_call)
    run.metrics.steps.append({"node": "facts_check", "ms": round((run.clock() - started) * 1000)})
    if not errors:
        return {"parts": parts, "source": source, "next": "finalize"}
    run.metrics.check_errors.extend(error["code"] for error in errors)
    if run.repairs or run.model_steps >= MAX_STEPS or run.remaining() < MIN_CALL_SECONDS:
        return {"next": "fallback"}
    run.repairs += 1
    content = json.dumps({"errors": errors, "instruction": "Call reply again with every error fixed."})
    repair = ToolMessage(content=content, tool_call_id=reply_call["id"], status="error")
    return {"messages": [repair], "next": "supervisor"}


def fallback_answer(state: State, runtime: Runtime[OpenModeRun]) -> State:
    run = runtime.context
    read = Ledger(run.ledger.country, run.ledger.now, {i: run.ledger.facts[i] for i in run.tool_facts})
    parts: list[Part] = [
        part for part in fallback("answer", read, run.context.locale) if isinstance(part, Say)
    ]
    return {"parts": parts, "source": "fallback", "next": "finalize"}


def finalize(state: State, runtime: Runtime[OpenModeRun]) -> State:
    run = runtime.context
    run.reply = compose(state["parts"], run.ledger, run.context.locale, state["source"])
    return {}


def _next(state: State) -> Next:
    return state["next"]


@cache
def graph() -> Any:
    builder = StateGraph(State, context_schema=OpenModeRun)
    builder.add_node("supervisor", supervisor)
    builder.add_node("tools", tools)
    builder.add_node("facts_check", facts_check)
    builder.add_node("fallback", fallback_answer)
    builder.add_node("finalize", finalize)
    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges("supervisor", _next, ["tools", "facts_check", "fallback"])
    builder.add_edge("tools", "supervisor")
    builder.add_conditional_edges("facts_check", _next, ["finalize", "supervisor", "fallback"])
    builder.add_edge("fallback", "finalize")
    builder.add_edge("finalize", END)
    return builder.compile()


def run_open_mode(run: OpenModeRun) -> Reply:
    run.started = run.clock()
    graph().invoke(
        {"messages": [HumanMessage(content=run.text)]},
        context=run,
        config={"recursion_limit": RECURSION_LIMIT},
    )
    assert run.reply is not None
    return run.reply


def _exhausted(run: OpenModeRun) -> Exhausted | None:
    if run.model_steps >= MAX_STEPS:
        return "steps"
    if run.remaining() < MIN_CALL_SECONDS:
        return "time"
    if run.input_tokens >= INPUT_TOKEN_CAP:
        return "input_tokens"
    return None


@cache
def _bound(client: "BedrockRuntimeClient", model_id: str | None, forced: bool) -> Runnable[Any, BaseMessage]:
    return chat_model(client, model_id).bind_tools(tool_specs(), tool_choice=REPLY if forced else "any")


def _invoke(run: OpenModeRun, messages: list[BaseMessage], forced: bool) -> AIMessage:
    for attempt in range(MODEL_ATTEMPTS):
        model = _bound(run.clients(run.remaining()), run.model_id, forced)
        try:
            message = model.invoke([run.system(), *messages])
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code", "")
            if code in RETRYABLE and attempt + 1 < MODEL_ATTEMPTS and run.remaining() >= MIN_CALL_SECONDS:
                continue
            raise ModelUnavailable(code) from error
        except (BotoCoreError, ValueError) as error:
            raise ModelUnavailable(type(error).__name__) from error
        assert isinstance(message, AIMessage)
        return message
    raise ModelUnavailable("attempts")


def _run_tool(run: OpenModeRun, tool_call: ToolCall) -> ToolMessage:
    name, tool_call_id = tool_call["name"], str(tool_call["id"])
    if name == REPLY:
        return _refused(run, name, tool_call_id, "ignored", "Call reply alone, after reading the results.")
    if run.tool_calls >= MAX_TOOL_CALLS:
        return _refused(run, name, tool_call_id, "budget", "The tool budget is used up; reply now.")
    if run.remaining() <= 0:
        return _refused(run, name, tool_call_id, "time", "The time budget is used up; reply now.")
    started = run.clock()
    result = call(name, tool_call["args"], run.tools, run.ledger)
    run.tool_calls += 1
    run.tool_facts.extend(result.ids)
    facts = run.ledger.payload(result.ids)
    error = next((fact for fact in facts if fact["kind"] == "error"), None)
    outcome = str(error["fields"]["error"]["value"]) if error else "ok"
    run.metrics.tools.append(
        {
            "tool": name if name in TOOLS else "unknown",
            "outcome": outcome,
            "ms": round((run.clock() - started) * 1000),
        }
    )
    return ToolMessage(
        content=tool_result(facts), tool_call_id=tool_call_id, status="error" if error else "success"
    )


def _refused(run: OpenModeRun, name: str, tool_call_id: str, outcome: str, detail: str) -> ToolMessage:
    run.metrics.tools.append(
        {"tool": name if name in TOOLS or name == REPLY else "unknown", "outcome": outcome, "ms": 0}
    )
    return ToolMessage(
        content=json.dumps({"error": outcome, "detail": detail}), tool_call_id=tool_call_id, status="error"
    )


def _checked(run: OpenModeRun, reply_call: ToolCall) -> tuple[list[Part], Source, list[dict[str, Any]]]:
    locale = run.context.locale
    try:
        args = ReplyArgs.model_validate(reply_call["args"])
    except ValidationError as error:
        detail = "; ".join(issue["msg"] for issue in error.errors()[:3])
        return [], "composed", [{"code": "invalid_reply", "text": "", "instruction": detail}]
    if args.say_key is not None:
        parts = answers.say_key(args.say_key, run.ledger, locale)
        source: Source = "say_key"
    else:
        parts = [Say(text) for text in args.say or ()]
        source = "repaired" if run.repairs else "composed"
    errors = check(parts, run.ledger, locale)
    return (
        parts,
        source,
        [{"code": error.code, "text": error.text, "instruction": error.instruction} for error in errors],
    )
