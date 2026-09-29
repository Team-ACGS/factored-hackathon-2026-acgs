import base64
import binascii

from core.accounts import transaction_key
from core.ids import InvalidId


class InvalidCursor(ValueError):
    pass


def encode_cursor(key: str) -> str:
    return base64.urlsafe_b64encode(key.encode()).decode().rstrip("=")


def decode_cursor(cursor: str, product_id: str) -> str:
    try:
        key = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
    except (binascii.Error, UnicodeDecodeError) as error:
        raise InvalidCursor("cursor is not readable") from error
    transaction_id = key.rpartition("#")[2]
    try:
        expected = transaction_key(product_id, transaction_id)
    except InvalidId as error:
        raise InvalidCursor("cursor does not name a transaction") from error
    if key != expected:
        raise InvalidCursor("cursor belongs to another card")
    return key
