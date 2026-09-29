import uuid
from datetime import UTC, datetime

_RANDOM_BITS = 74
_RANDOM_B_BITS = 62
_RANDOM_B_MASK = (1 << _RANDOM_B_BITS) - 1
_RANDOM_A_MASK = (1 << 12) - 1


class InvalidId(ValueError):
    pass


def parse_uuid7(value: object) -> uuid.UUID:
    if not isinstance(value, str):
        raise InvalidId("expected a UUIDv7 string")
    try:
        parsed = uuid.UUID(value)
    except ValueError as error:
        raise InvalidId("expected a UUIDv7 string") from error
    if parsed.version != 7 or str(parsed) != value:
        raise InvalidId("expected a lowercase canonical UUIDv7")
    return parsed


def uuid7_time(value: uuid.UUID) -> datetime:
    return datetime.fromtimestamp((value.int >> 80) / 1000, tz=UTC)


def uuid7_at(instant: datetime, random: int) -> uuid.UUID:
    return _compose(int(instant.timestamp() * 1000), random & ((1 << _RANDOM_BITS) - 1))


def successor(value: uuid.UUID) -> uuid.UUID:
    """The next UUIDv7 after `value` within the same millisecond: no other id can sort between them."""
    random = (((value.int >> 64) & _RANDOM_A_MASK) << _RANDOM_B_BITS) | (value.int & _RANDOM_B_MASK)
    following = random + 1
    if following >> _RANDOM_BITS:
        raise InvalidId("no successor within the same millisecond")
    return _compose(value.int >> 80, following)


def _compose(milliseconds: int, random: int) -> uuid.UUID:
    return uuid.UUID(
        int=(milliseconds << 80)
        | (0x7 << 76)
        | ((random >> _RANDOM_B_BITS) << 64)
        | (0b10 << 62)
        | (random & _RANDOM_B_MASK)
    )


def format_instant(instant: datetime) -> str:
    return instant.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
