import uuid

import pytest

from core.ids import InvalidId, parse_uuid7, successor, uuid7_time
from harness import uuid7


def test_successor_is_a_uuid7_of_the_same_millisecond_that_sorts_right_after() -> None:
    source = uuid7(1_790_000_000_123)
    following = successor(uuid.UUID(source))

    assert following.version == 7
    assert uuid7_time(following) == uuid7_time(uuid.UUID(source))
    assert str(following) > source
    assert successor(uuid.UUID(source)) == following


def test_successor_carries_across_the_variant_bits() -> None:
    source = uuid.UUID(int=(1 << 80) | (0x7 << 76) | (0x123 << 64) | (0b10 << 62) | ((1 << 62) - 1))

    following = successor(source)

    assert following.version == 7
    assert following.variant == uuid.RFC_4122
    assert str(following) > str(source)


def test_no_id_sorts_between_a_message_and_its_successor() -> None:
    milliseconds = 1_790_000_000_123
    source = uuid7(milliseconds)
    following = str(successor(uuid.UUID(source)))
    others = [uuid7(milliseconds) for _ in range(500)]

    assert not any(source < other < following for other in others)


@pytest.mark.parametrize(
    "value",
    [str(uuid.uuid4()), uuid7().upper(), uuid7().replace("-", ""), "", "room-1", None, 7],
)
def test_parse_uuid7_rejects_anything_but_a_canonical_uuid7(value: object) -> None:
    with pytest.raises(InvalidId):
        parse_uuid7(value)


def test_uuid7_time_reads_the_millisecond_timestamp() -> None:
    assert uuid7_time(uuid.UUID(uuid7(1_790_000_000_123))).timestamp() == 1_790_000_000.123
