from dataclasses import dataclass, field

from core.policies import CountryFacts

from bankdata.policies.chunk import Chunking, oversized
from bankdata.policies.document import SOURCE_KEY, Problem, edition_ids, expand, parse
from bankdata.policies.render import RenderedDocument, render
from bankdata.policies.spec import Limits
from bankdata.policies.store import Store
from bankdata.policies.validate import validate_all


@dataclass(frozen=True)
class Loaded:
    problems: list[Problem] = field(default_factory=list)
    editions: list[RenderedDocument] = field(default_factory=list)
    source_hashes: dict[str, str] = field(default_factory=dict)
    present: set[str] = field(default_factory=set)


def load(
    store: Store,
    facts: dict[str, CountryFacts],
    limits: Limits,
    chunking: Chunking,
    renderable: frozenset[str] = frozenset(),
) -> Loaded:
    loaded = Loaded()
    sources = [
        parse(key, (store.read(key) or b"").decode("utf-8")) for key in store.names() if SOURCE_KEY.match(key)
    ]
    problems = validate_all(sources, facts, limits)
    blocked = {
        _document(problem.file)
        for found in problems.values()
        for problem in found
        if problem.code == "parity" and problem.code not in renderable
    }
    for source in sources:
        found = problems[source.key]
        loaded.problems.extend(found)
        loaded.present.update(edition_ids(source.key))
        if _document(source.key) in blocked or any(problem.code not in renderable for problem in found):
            continue
        loaded.source_hashes[source.key] = source.source_hash
        for edition in expand(source):
            document = render(edition, facts[edition.country])
            too_long = oversized(document, chunking)
            loaded.problems.extend(too_long)
            if not too_long or "chunk_length" in renderable:
                loaded.editions.append(document)
    return loaded


def _document(key: str) -> str:
    return key.split("/", 1)[0]
