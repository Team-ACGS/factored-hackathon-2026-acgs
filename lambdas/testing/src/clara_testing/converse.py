import copy
import json
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache, cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from botocore.validate import ParamValidator

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime import BedrockRuntimeClient

MAX_CACHE_POINTS = 4

Response = dict[str, Any]


def tool_use(name: str, arguments: Mapping[str, Any], tool_use_id: str | None = None) -> dict[str, Any]:
    return {
        "toolUse": {
            "toolUseId": tool_use_id or f"tooluse_{uuid.uuid4().hex[:20]}",
            "name": name,
            "input": dict(arguments),
        }
    }


def response(
    *blocks: Mapping[str, Any],
    input_tokens: int = 1200,
    output_tokens: int = 80,
    cache_read: int = 0,
    cache_write: int = 0,
) -> Response:
    uses_tools = any("toolUse" in block for block in blocks)
    return {
        "output": {"message": {"role": "assistant", "content": [dict(block) for block in blocks]}},
        "stopReason": "tool_use" if uses_tools else "end_turn",
        "usage": {
            "inputTokens": input_tokens,
            "outputTokens": output_tokens,
            "totalTokens": input_tokens + cache_read + cache_write + output_tokens,
            "cacheReadInputTokens": cache_read,
            "cacheWriteInputTokens": cache_write,
        },
        "metrics": {"latencyMs": 900},
    }


def reply(*say: str, say_key: str | None = None, **usage: int) -> Response:
    arguments: dict[str, Any] = {"say_key": say_key} if say_key else {"say": list(say)}
    return response(tool_use("reply", arguments), **usage)


def composed(*say: str, **usage: int) -> Response:
    return response(tool_use("say", {"say": list(say)}), **usage)


def throttled() -> ClientError:
    return ClientError({"Error": {"Code": "ThrottlingException", "Message": "Too many requests"}}, "Converse")


class ConverseShapeError(AssertionError):
    pass


@dataclass
class ManualClock:
    now: float = 0.0

    def __call__(self) -> float:
        return self.now


@dataclass
class FakeConverse:
    responses: list[Response | Exception]
    requests: list[dict[str, Any]] = field(default_factory=list)
    timeouts: list[float] = field(default_factory=list)
    clock: ManualClock | None = None
    latency: float = 0.0

    @classmethod
    def replay(cls, path: Path) -> "FakeConverse":
        recording = json.loads(path.read_text())
        return cls([exchange["response"] for exchange in recording["exchanges"]])

    @cached_property
    def _client(self) -> "BedrockRuntimeClient":
        client = offline_client()
        client.converse = self.converse  # type: ignore[method-assign,assignment]
        return client

    def client(self, remaining: float) -> "BedrockRuntimeClient":
        self.timeouts.append(remaining)
        return self._client

    def converse(self, **request: Any) -> Response:
        validate(request)
        self.requests.append(copy.deepcopy(request))
        if self.clock is not None:
            self.clock.now += self.latency
        if not self.responses:
            raise ConverseShapeError("no recorded response left for this call")
        answer = self.responses.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return copy.deepcopy(answer)


def validate(request: Mapping[str, Any]) -> None:
    operation = _operation()
    report = ParamValidator().validate(dict(request), operation.input_shape)
    if report.has_errors():
        raise ConverseShapeError(report.generate_report())
    points = sum(1 for block in _blocks(request) if "cachePoint" in block)
    if points > MAX_CACHE_POINTS:
        raise ConverseShapeError(f"{points} cache points, at most {MAX_CACHE_POINTS}")
    _tool_results_follow_tool_uses(request["messages"])


def offline_client() -> "BedrockRuntimeClient":
    return boto3.client(
        "bedrock-runtime",
        region_name="us-east-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",  # noqa: S106
    )


@cache
def _operation() -> Any:
    return offline_client().meta.service_model.operation_model("Converse")


def _blocks(request: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    blocks: list[Mapping[str, Any]] = list(request.get("system", []))
    blocks.extend(request.get("toolConfig", {}).get("tools", []))
    for message in request["messages"]:
        blocks.extend(message["content"])
    return blocks


def _tool_results_follow_tool_uses(messages: Sequence[Mapping[str, Any]]) -> None:
    for index, message in enumerate(messages):
        if message["role"] != "assistant":
            continue
        uses = {block["toolUse"]["toolUseId"] for block in message["content"] if "toolUse" in block}
        if not uses:
            continue
        if index + 1 >= len(messages):
            raise ConverseShapeError("a toolUse is the last message")
        following = messages[index + 1]
        results = {
            block["toolResult"]["toolUseId"] for block in following["content"] if "toolResult" in block
        }
        if following["role"] != "user" or results != uses:
            raise ConverseShapeError("every toolUse needs its toolResult in the next user message")


@dataclass
class Recorder:
    session: boto3.Session
    exchanges: list[dict[str, Any]] = field(default_factory=list)
    _clients: dict[int, "BedrockRuntimeClient"] = field(default_factory=dict)

    def client(self, remaining: float) -> "BedrockRuntimeClient":
        seconds = max(1, int(remaining))
        if seconds not in self._clients:
            config = Config(connect_timeout=1, read_timeout=seconds, retries={"total_max_attempts": 1})
            client = self.session.client("bedrock-runtime", config=config)
            real = client.converse

            def converse(**request: Any) -> Response:
                answer = dict(real(**request))
                answer.pop("ResponseMetadata", None)
                self.exchanges.append({"request": copy.deepcopy(request), "response": copy.deepcopy(answer)})
                return answer

            client.converse = converse  # type: ignore[method-assign,assignment]
            self._clients[seconds] = client
        return self._clients[seconds]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"exchanges": self.exchanges}, ensure_ascii=False, indent=1, default=str) + "\n"
        )
