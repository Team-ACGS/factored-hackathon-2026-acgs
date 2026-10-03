import math
from collections.abc import Callable
from functools import cache
from typing import TYPE_CHECKING, Any

import boto3
from botocore.config import Config
from langchain_aws import ChatBedrockConverse

from core.graphs.profiles import ModelProfile

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime import BedrockRuntimeClient

CONNECT_SECONDS = 1.0

Clients = Callable[[float], "BedrockRuntimeClient"]


def read_seconds(remaining: float) -> int:
    return max(1, math.floor(remaining - CONNECT_SECONDS))


@cache
def deadline_client(seconds: int) -> "BedrockRuntimeClient":
    config = Config(
        connect_timeout=CONNECT_SECONDS,
        read_timeout=seconds,
        retries={"total_max_attempts": 1, "mode": "standard"},
    )
    return boto3.client("bedrock-runtime", config=config)


def bedrock_clients(remaining: float) -> "BedrockRuntimeClient":
    return deadline_client(read_seconds(remaining))


def chat_model(client: "BedrockRuntimeClient", profile: ModelProfile) -> ChatBedrockConverse:
    options: dict[str, Any] = {
        "model": profile.id,
        "client": client,
        "bedrock_client": client,
        "provider": "anthropic",
        "max_tokens": profile.max_output_tokens,
    }
    if profile.request_fields():
        options["additional_model_request_fields"] = profile.request_fields()
    return ChatBedrockConverse(**options)
