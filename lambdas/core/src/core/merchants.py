import re
import unicodedata

_NOT_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")


def merchant_key(name: str) -> str:
    stripped = "".join(char for char in unicodedata.normalize("NFD", name) if not unicodedata.combining(char))
    return _NOT_ALPHANUMERIC.sub(" ", stripped.lower()).strip()


def matches_merchant(query: str, name: str) -> bool:
    wanted = merchant_key(query).split()
    tokens = set(merchant_key(name).split())
    return bool(wanted) and all(token in tokens for token in wanted)
