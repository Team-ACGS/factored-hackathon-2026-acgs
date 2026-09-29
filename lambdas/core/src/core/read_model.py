from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any


def projection(attributes: Sequence[str]) -> dict[str, Any]:
    names = {f"#a{index}": name for index, name in enumerate(attributes)}
    return {"ProjectionExpression": ", ".join(names), "ExpressionAttributeNames": names}


def public(item: Mapping[str, Any], attributes: Sequence[str]) -> dict[str, Any]:
    return {name: _plain(item.get(name)) for name in attributes}


def _plain(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
    return value
