from typing import Literal

from pydantic import Field

from core.facts.values import (
    POLICY_CHUNK,
    Count,
    Day,
    FactIds,
    Flag,
    Ledger,
    Passage,
    Text,
    Trace,
    Value,
)
from core.policies import figure, pdf_key, pdf_url
from core.retrieval import PolicySearch, RetrievedChunk, policy_search
from core.tools.context import ToolContext
from core.tools.inputs import Input

Group = Literal["disputes", "card_security", "transactions", "service"]
DocType = Literal["policy", "procedure", "guide", "faq", "glossary"]


class SearchPoliciesInput(Input):
    query: str = Field(min_length=1, max_length=200, description="The question, in the customer's own words")
    topic: Group | None = Field(default=None, description="Document group to search in")
    doc_type: DocType | None = None
    k: int = Field(default=4, ge=1, le=8, description="How many excerpts to return")


def search_policies(context: ToolContext, ledger: Ledger, args: SearchPoliciesInput) -> list[str]:
    search = context.policies or policy_search()
    filters = {name: value for name, value in (("group", args.topic), ("doc_type", args.doc_type)) if value}
    chunks = [
        chunk
        for chunk in search.retriever.search(args.query, context.country, args.k, filters)
        if chunk.country == context.country and chunk.similarity >= search.cut(context.country)
    ]
    rows = [ledger.add(POLICY_CHUNK, chunk_fields(chunk, search), prefix="p") for chunk in chunks]
    aggregate = ledger.add(
        "policies",
        {
            "count": Count(len(rows), "excerpt"),
            "ids": FactIds(tuple(row.id for row in rows)),
            "outcome": Trace("match" if rows else "no_match"),
        },
    )
    return [*(row.id for row in rows), aggregate.id]


def chunk_fields(chunk: RetrievedChunk, search: PolicySearch) -> dict[str, Value | None]:
    key = pdf_key(chunk.country, chunk.doc_id, chunk.version, chunk.facts_version)
    fields: dict[str, Value | None] = {
        "chunk_id": Trace(chunk.chunk_id),
        "doc_id": Trace(chunk.doc_id),
        "title": Text(chunk.title),
        "section": Text(chunk.section),
        "text": Passage(chunk.text),
        "doc_type": Trace(chunk.doc_type),
        "country": Trace(chunk.country),
        "version": Trace(str(chunk.version)),
        "effective_date": Day(chunk.effective_date),
        "page": Trace(str(chunk.page)),
        "url": Trace(pdf_url(search.docs_domain, key, chunk.page)),
    }
    for name, spec in sorted(chunk.figures.items()):
        fields[f"figures.{name}"] = figure(spec)
        if spec.get("verified") is False:
            fields[f"figures.{name}.verified"] = Flag(False)
    return fields
