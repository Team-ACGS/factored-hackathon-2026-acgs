from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from core.facts import Part, Say, render
from core.facts.values import Json, Ledger, Text, Trace

Source = Literal["composed", "repaired", "fallback", "safety", "say_key"]


@dataclass(frozen=True)
class Reply:
    parts: tuple[Json, ...]
    text: str
    facts: tuple[Json, ...]
    draft: tuple[Json, ...]
    source: Source


def compose(parts: Sequence[Part], ledger: Ledger, locale: str, source: Source) -> Reply:
    says = [part for part in parts if isinstance(part, Say)]
    rendered = render(says, ledger, locale)
    chunks = ledger.chunks()
    referenced: list[str] = []
    for part in rendered:
        referenced.extend(part["facts"])
        part["citations"] = [citation(chunk_id, ledger) for chunk_id in part["citations"]]
        referenced.extend(chunks[entry["chunk_id"]].id for entry in part["citations"])
    return Reply(
        parts=tuple(rendered),
        text="\n\n".join(part["text"] for part in rendered),
        facts=tuple(ledger.payload(list(dict.fromkeys(referenced)))),
        draft=tuple(part.to_wire() for part in says),
        source=source,
    )


def citation(chunk_id: str, ledger: Ledger) -> Json:
    fields = ledger.chunks()[chunk_id].fields
    title, page, url = fields.get("title"), fields.get("page"), fields.get("url")
    number = page.value if isinstance(page, Trace) else None
    return {
        "chunk_id": chunk_id,
        "title": title.value if isinstance(title, Text) else "",
        "page": int(number) if isinstance(number, str) and number.isdigit() else None,
        "url": url.value if isinstance(url, Trace) else None,
    }
