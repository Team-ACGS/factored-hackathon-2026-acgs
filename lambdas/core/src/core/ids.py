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


def successor(value: uuid.UUID) -> uuid.UUID:
    """The next UUIDv7 after `value` within the same millisecond: no other id can sort between them."""
    random = (((value.int >> 64) & _RANDOM_A_MASK) << _RANDOM_B_BITS) | (value.int & _RANDOM_B_MASK)
    following = random + 1
    if following >> _RANDOM_BITS:
        raise InvalidId("no successor within the same millisecond")
    timestamp = value.int >> 80
    return uuid.UUID(
        int=(timestamp << 80)
        | (0x7 << 76)
        | ((following >> _RANDOM_B_BITS) << 64)
        | (0b10 << 62)
        | (following & _RANDOM_B_MASK)
    )


def format_instant(instant: datetime) -> str:
    return instant.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
