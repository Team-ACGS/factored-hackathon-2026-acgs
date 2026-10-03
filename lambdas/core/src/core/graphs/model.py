import math
import os
from collections.abc import Callable
from functools import cache
from typing import TYPE_CHECKING, Any

import boto3
from botocore.config import Config
from langchain_aws import ChatBedrockConverse

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime import BedrockRuntimeClient

MAX_OUTPUT_TOKENS = 1024
EFFORT = "low"
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


def chat_model(client: "BedrockRuntimeClient", model_id: str | None = None) -> ChatBedrockConverse:
    options: dict[str, Any] = {
        "model": model_id or os.environ["BEDROCK_MODEL_ID"],
        "client": client,
        "bedrock_client": client,
        "provider": "anthropic",
        "max_tokens": MAX_OUTPUT_TOKENS,
        "additional_model_request_fields": {"output_config": {"effort": EFFORT}},
    }
    return ChatBedrockConverse(**options)
