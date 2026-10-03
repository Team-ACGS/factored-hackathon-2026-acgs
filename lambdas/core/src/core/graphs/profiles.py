import tomllib
from collections.abc import Iterable, Mapping
from decimal import Decimal
from functools import cache
from importlib.resources import files
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

MILLION = Decimal(1_000_000)


class UnknownModel(LookupError):
    pass


class _Row(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CacheSupport(_Row):
    min_prefix_tokens: int
    note: str | None = None


class Prices(_Row):
    input: Decimal
    output: Decimal
    cache_read: Decimal
    cache_write: Decimal
    source: str
    date: str


class ModelProfile(_Row):
    id: str
    key: str
    name: str
    prompt: str
    max_output_tokens: int
    effort: Literal["low", "medium", "high", "max"] | None = None
    thinking: Literal["off"]
    cache: CacheSupport
    prices: Prices

    @property
    def system_prompt(self) -> str:
        return (
            files("core.graphs").joinpath("prompts", f"{self.prompt}.md").read_text(encoding="utf-8").strip()
        )

    def request_fields(self) -> dict[str, Any]:
        return {"output_config": {"effort": self.effort}} if self.effort else {}

    def cost(self, steps: Iterable[Mapping[str, Any]]) -> Decimal:
        total = Decimal(0)
        for step in steps:
            read, written = int(step.get("cache_read", 0)), int(step.get("cache_write", 0))
            fresh = int(step.get("input_tokens", 0)) - read - written
            total += (
                fresh * self.prices.input
                + read * self.prices.cache_read
                + written * self.prices.cache_write
                + int(step.get("output_tokens", 0)) * self.prices.output
            )
        return total / MILLION


class _Table(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: int
    profile: tuple[ModelProfile, ...]


@cache
def table() -> _Table:
    return _Table.model_validate(
        tomllib.loads(files("core.graphs").joinpath("profiles.toml").read_text("utf-8"))
    )


def profiles() -> tuple[ModelProfile, ...]:
    return table().profile


def profile_for(model_id: str) -> ModelProfile:
    for row in profiles():
        if row.id == model_id:
            return row
    raise UnknownModel(f"no model profile for {model_id!r} in core/graphs/profiles.toml")
