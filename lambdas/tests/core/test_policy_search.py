from datetime import UTC, date, datetime

import pytest

from clara_testing import FakeBedrockRuntime, FakeS3Vectors, local_embedder, local_index
from core.facts import Ledger
from core.facts.values import Count, Day, FactIds, Flag, Passage, Text, Trace
from core.policies import chunk_id, policy_facts
from core.retrieval import (
    NEAR_DUPLICATE,
    NON_FILTERABLE,
    POOL,
    ChunkRecord,
    PolicySearch,
    VectorRetriever,
    near_duplicate,
    policy_search,
    thresholds,
)
from core.tools import TOOLS, ToolContext, search_policies
from core.tools.registry import RETRIES
from core.vectors import (
    SEARCH_CALLS,
    SEARCH_DOCUMENT,
    SEARCH_QUERY,
    TURN_ATTEMPTS,
    TURN_SECONDS,
    WORST_SEARCH_SECONDS,
    Embedder,
    Vector,
)

NOW = datetime(2026, 10, 1, 15, 0, tzinfo=UTC)
DOMAIN = "docs.factoredai.sdfles.com"

PASSAGES = [
    (
        "PE",
        "dispute-lifecycle",
        "disputes",
        "procedure",
        4,
        "La revisión de tu aclaración toma hasta 10 días hábiles.",
    ),
    ("PE", "card-replacement", "card_security", "policy", 2, "Tu nueva tarjeta llega en 7 días hábiles."),
    (
        "PE",
        "pending-charges",
        "transactions",
        "guide",
        3,
        "Un cargo pendiente de hotel se libera en 10 días.",
    ),
    (
        "BR",
        "dispute-lifecycle",
        "disputes",
        "procedure",
        4,
        "A análise da sua contestação leva até 10 dias úteis.",
    ),
    ("BR", "card-replacement", "card_security", "policy", 2, "Seu novo cartão chega em 7 dias úteis."),
]
FIGURES = {
    "disputes": ("claims.review_time", "legal.claim_response"),
    "card_security": ("cards.replacement_time",),
    "transactions": ("holds.preauth_hotel",),
}


def record(country: str, slug: str, group: str, doc_type: str, page: int, text: str) -> ChunkRecord:
    facts = policy_facts()[country]
    document = f"{country.lower()}-{slug}"
    return ChunkRecord(
        chunk_id=chunk_id(document, 2, facts.version, 3, 1),
        country=country,
        language=facts.language,
        group=group,
        topic=slug.replace("-", "_"),
        doc_type=doc_type,
        doc_id=document,
        version=2,
        facts_version=facts.version,
        effective_date=date(2026, 9, 1),
        section="Plazos",
        title=f"Documento {slug}",
        text=text,
        figures={key: facts.specs[key] for key in FIGURES[group]},
        page_start=page,
        page_end=page + 1,
        url=f"https://{DOMAIN}/{country}/{document}-v2-f{facts.version}.pdf",
        content_hash="hash",
    )


def put(
    clients: tuple[FakeBedrockRuntime, FakeS3Vectors], passages: list[tuple[str, str, str, str, int, str]]
) -> None:
    bedrock, vectors = clients
    records = [record(*passage) for passage in passages]
    embeddings = local_embedder(bedrock).embed([item.text for item in records], SEARCH_DOCUMENT)
    local_index(vectors).put(
        Vector(item.chunk_id, embedding, item.metadata())
        for item, embedding in zip(records, embeddings, strict=True)
    )
    bedrock.calls.clear()


@pytest.fixture
def clients() -> tuple[FakeBedrockRuntime, FakeS3Vectors]:
    pair = (FakeBedrockRuntime(), FakeS3Vectors(NON_FILTERABLE))
    put(pair, PASSAGES)
    return pair


def cuts(es: float = 0.1, pt: float = 0.1, en: float = 0.1) -> dict[str, float]:
    return {"es": es, "pt": pt, "en": en}


def context(
    clients: tuple[FakeBedrockRuntime, FakeS3Vectors],
    country: str = "PE",
    minimum: dict[str, float] | None = None,
) -> ToolContext:
    bedrock, vectors = clients
    retriever = VectorRetriever(local_embedder(bedrock), local_index(vectors))
    search = PolicySearch(retriever, minimum or cuts(), DOMAIN)
    return ToolContext("customer-1", country, "es", NOW, policies=search)


def test_the_model_never_chooses_the_customer_or_the_country() -> None:
    schema = TOOLS["search_policies"].input_schema()

    assert set(schema["properties"]) == {"query", "topic", "doc_type", "k"}
    assert schema["required"] == ["query"]


def test_returns_cited_chunks_of_the_contexts_country_only(
    clients: tuple[FakeBedrockRuntime, FakeS3Vectors],
) -> None:
    ledger = Ledger("PE", NOW)

    result = search_policies(
        context(clients), ledger, query="¿Cuánto tarda la revisión de mi aclaración?", k=8
    )

    chunks = [ledger.facts[fact_id] for fact_id in result.ids if fact_id.startswith("p")]
    assert chunks
    assert {fact.fields["country"] for fact in chunks} == {Trace("PE")}
    assert chunks[0].fields["chunk_id"] == Trace("pe-dispute-lifecycle-v2-f2-s3-c1")
    assert ledger.facts[result.ids[-1]].fields["ids"] == FactIds(tuple(fact.id for fact in chunks))
    assert clients[0].calls[0]["input_type"] == "search_query"


def test_a_chunk_is_facts_with_typed_figures_and_a_url_at_its_page(
    clients: tuple[FakeBedrockRuntime, FakeS3Vectors],
) -> None:
    ledger = Ledger("PE", NOW)

    search_policies(context(clients), ledger, query="revisión de mi aclaración", topic="disputes", k=1)

    fields = ledger.facts["p1"].fields
    assert fields["title"] == Text("Documento dispute-lifecycle")
    assert fields["section"] == Text("Plazos")
    assert fields["text"] == Passage("La revisión de tu aclaración toma hasta 10 días hábiles.")
    assert fields["effective_date"] == Day(date(2026, 9, 1))
    assert fields["url"] == Trace(f"https://{DOMAIN}/PE/pe-dispute-lifecycle-v2-f2.pdf#page=4")
    assert fields["figures.claims.review_time"] == Count(10, "business_day")
    assert fields["figures.legal.claim_response"] == Count(15, "business_day")
    assert fields["figures.legal.claim_response.verified"] == Flag(False)
    assert "figures.claims.review_time.verified" not in fields


def test_filters_by_group_and_doc_type(clients: tuple[FakeBedrockRuntime, FakeS3Vectors]) -> None:
    ledger = Ledger("PE", NOW)

    search_policies(context(clients), ledger, query="días hábiles", topic="card_security", doc_type="policy")

    assert [fact.fields["doc_id"] for fact in ledger.chunks().values()] == [Trace("pe-card-replacement")]


def test_no_match_under_the_minimum_similarity(clients: tuple[FakeBedrockRuntime, FakeS3Vectors]) -> None:
    ledger = Ledger("PE", NOW)

    result = search_policies(
        context(clients, minimum=cuts(es=0.95)), ledger, query="¿Cuánto tarda la revisión?"
    )

    [aggregate] = [ledger.facts[fact_id] for fact_id in result.ids]
    assert aggregate.fields["outcome"] == Trace("no_match")
    assert aggregate.fields["count"] == Count(0, "excerpt")
    assert ledger.chunks() == {}


@pytest.mark.parametrize("failing", ["bedrock", "vectors"])
def test_unavailable_after_two_retries_never_no_match(
    clients: tuple[FakeBedrockRuntime, FakeS3Vectors], failing: str
) -> None:
    bedrock, vectors = clients
    ledger = Ledger("PE", NOW)
    (bedrock if failing == "bedrock" else vectors).failures = 3

    result = search_policies(context(clients), ledger, query="revisión")

    [error] = [ledger.facts[fact_id] for fact_id in result.ids]
    assert (error.kind, error.fields["error"]) == ("error", Trace("unavailable"))


def test_two_failures_are_retried_within_the_turn(clients: tuple[FakeBedrockRuntime, FakeS3Vectors]) -> None:
    clients[1].failures = 2
    ledger = Ledger("PE", NOW)

    search_policies(context(clients), ledger, query="revisión de mi aclaración")

    assert ledger.chunks()


@pytest.mark.parametrize(
    "arguments", [{"query": "x", "k": 9}, {"query": ""}, {"query": "x", "country": "BR"}]
)
def test_invalid_arguments_are_refused(
    clients: tuple[FakeBedrockRuntime, FakeS3Vectors], arguments: dict[str, object]
) -> None:
    ledger = Ledger("PE", NOW)

    result = search_policies(context(clients), ledger, **arguments)

    assert ledger.facts[result.ids[0]].fields["error"] == Trace("invalid_argument")


def test_three_attempts_of_both_calls_fit_in_half_the_turn() -> None:
    assert TURN_ATTEMPTS == RETRIES + 1
    assert SEARCH_CALLS == 2
    assert WORST_SEARCH_SECONDS <= TURN_SECONDS / 2


@pytest.mark.parametrize("broken", ["short_embeddings", "metadata", "figures"])
def test_an_unreadable_answer_is_unavailable_never_a_crash(
    clients: tuple[FakeBedrockRuntime, FakeS3Vectors], broken: str
) -> None:
    bedrock, vectors = clients
    key = "pe-dispute-lifecycle-v2-f2-s3-c1"
    data, metadata = vectors.vectors[key]
    if broken == "short_embeddings":
        bedrock.short = True
    elif broken == "metadata":
        vectors.vectors[key] = (data, {**metadata, "page_start": "first"})
    else:
        vectors.vectors[key] = (data, {**metadata, "figures": '{"claims.review_time": {"type": "unknown"}}'})
    ledger = Ledger("PE", NOW)

    result = search_policies(context(clients), ledger, query="revisión de mi aclaración", k=8)

    [error] = [ledger.facts[fact_id] for fact_id in result.ids]
    assert error.fields["error"] == Trace("unavailable")


def test_the_cut_is_the_one_of_the_countrys_document_language(
    clients: tuple[FakeBedrockRuntime, FakeS3Vectors],
) -> None:
    strict_spanish = cuts(es=0.95)
    peru, brazil = Ledger("PE", NOW), Ledger("BR", NOW)

    search_policies(context(clients, "PE", strict_spanish), peru, query="revisión de mi aclaración")
    search_policies(context(clients, "BR", strict_spanish), brazil, query="análise da minha contestação")

    assert peru.chunks() == {}
    assert brazil.chunks()


def test_thresholds_need_exactly_one_cut_per_document_language() -> None:
    assert thresholds('{"es": 0.36, "pt": 0.35, "en": 0.38}') == {"es": 0.36, "pt": 0.35, "en": 0.38}
    for encoded in ['{"es": 0.36, "pt": 0.35}', '{"es": 0.3, "pt": 0.3, "en": 0.3, "fr": 0.3}', "0.5744"]:
        with pytest.raises(ValueError, match="one cut for each"):
            thresholds(encoded)


def test_policy_search_fails_on_a_missing_language(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLICY_EMBEDDING_MODEL_ID", "cohere.embed-v4:0")
    monkeypatch.setenv("POLICY_INDEX_ARN", "arn:aws:s3vectors:us-east-1:000000000000:bucket/b/index/i")
    monkeypatch.setenv("POLICY_DOCS_DOMAIN", DOMAIN)
    monkeypatch.setenv("POLICY_MIN_SIMILARITY", '{"es": 0.36, "pt": 0.35}')
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    policy_search.cache_clear()

    with pytest.raises(ValueError, match="one cut for each"):
        policy_search()
    policy_search.cache_clear()


def test_no_two_excerpts_returned_are_near_duplicates(
    clients: tuple[FakeBedrockRuntime, FakeS3Vectors],
) -> None:
    bedrock, vectors = clients
    copies = [
        (
            "PE",
            f"copy-{n}",
            "disputes",
            "policy",
            5,
            f"La revisión de tu aclaración toma hasta 10 días hábiles, copia {n}.",
        )
        for n in range(10)
    ]
    put(clients, copies)
    retriever = VectorRetriever(local_embedder(bedrock), local_index(vectors))

    chunks = retriever.search("revisión de mi aclaración", "PE", 4, {})

    texts = [chunk.text for chunk in chunks]
    assert len(texts) == 3
    assert not any(near_duplicate(left, right) for n, left in enumerate(texts) for right in texts[n + 1 :])
    assert POOL > 4


def test_a_near_duplicate_is_half_the_smaller_excerpts_shingles() -> None:
    base = "uno dos tres cuatro cinco seis siete ocho nueve diez"
    assert near_duplicate(base, base + " once doce trece catorce quince dieciseis diecisiete dieciocho")
    assert not near_duplicate(base, "uno dos tres cuatro cinco otra cosa distinta por completo aqui")
    assert NEAR_DUPLICATE == 0.5


def test_the_first_excerpts_do_not_depend_on_k(clients: tuple[FakeBedrockRuntime, FakeS3Vectors]) -> None:
    bedrock, vectors = clients
    retriever = VectorRetriever(local_embedder(bedrock), local_index(vectors))

    three = retriever.search("revisión de mi aclaración", "PE", 3, {})
    four = retriever.search("revisión de mi aclaración", "PE", 4, {})

    assert [chunk.chunk_id for chunk in three] == [chunk.chunk_id for chunk in four][:3]


@pytest.mark.parametrize(
    ("model", "sized"), [("cohere.embed-v4:0", True), ("cohere.embed-multilingual-v3", False)]
)
def test_the_embedder_asks_each_model_for_1024_floats(model: str, sized: bool) -> None:
    bedrock = FakeBedrockRuntime()

    [vector] = Embedder(local_embedder(bedrock).client, model).embed(["hola"], SEARCH_QUERY)

    assert len(vector) == 1024
    assert ("output_dimension" in bedrock.calls[0]) is sized
