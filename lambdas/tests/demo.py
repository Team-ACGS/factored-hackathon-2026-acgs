from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from clara_testing import FakeBedrockRuntime, FakeS3Vectors, local_embedder, local_index
from core.messaging import Message, customer_message
from core.policies import chunk_id, policy_facts
from core.retrieval import NON_FILTERABLE, ChunkRecord, PolicySearch, VectorRetriever
from core.vectors import SEARCH_DOCUMENT, Vector
from harness import Aws, demo_account, uuid7

NOW = datetime(2026, 9, 20, 17, 0, tzinfo=UTC)
RECORDINGS = Path(__file__).parent / "core" / "recordings"
PROCESS = {
    "PE": (
        "es",
        "Ciclo de una aclaración",
        "El banco revisa tu aclaración y te responde dentro del plazo de revisión de "
        "{{policy.claims.review_time}}.",
    ),
    "BR": (
        "pt",
        "Ciclo de uma contestação",
        "O banco analisa a sua contestação e responde dentro do prazo de análise de "
        "{{policy.claims.review_time}}.",
    ),
}
DEMO = {
    "spend_es": ("PE", "es", "¿Cuánto gasté en Primax este mes vs el pasado?"),
    "case_es": ("PE", "es", "¿cuándo me devuelven la plata de mi aclaración?"),
    "spend_pt": ("BR", "pt-BR", "Quanto gastei no Ipiranga este mês comparado com o mês passado?"),
    "case_pt": ("BR", "pt-BR", "quando vou receber o dinheiro da minha contestação?"),
    "movements_es": ("PE", "es", "transacciones de los últimos 2 meses"),
    "visa_es": ("PE", "es", "movimientos de mi Visa de septiembre"),
    "cards_pt": ("BR", "pt-BR", "quais são os meus cartões?"),
    "charge_pt": ("BR", "pt-BR", "o que é essa cobrança do Ipiranga?"),
}


def policy_index(country: str) -> PolicySearch:
    bedrock, vectors = FakeBedrockRuntime(), FakeS3Vectors(NON_FILTERABLE)
    facts = policy_facts()[country]
    language, title, template = PROCESS[country]
    document = f"{country.lower()}-dispute-lifecycle"
    record = ChunkRecord(
        chunk_id=chunk_id(document, 2, facts.version, 3, 1),
        country=country,
        language=facts.language,
        group="disputes",
        topic="dispute_lifecycle",
        doc_type="procedure",
        doc_id=document,
        version=2,
        facts_version=facts.version,
        effective_date=date(2026, 9, 1),
        section=title,
        title=title,
        text=template.replace("{{policy.claims.review_time}}", "…"),
        figures={"claims.review_time": facts.specs["claims.review_time"]},
        page_start=4,
        page_end=5,
        url=f"https://docs.factoredai.sdfles.com/{country}/{document}-v2-f{facts.version}.pdf",
        content_hash=language,
    )
    [embedding] = local_embedder(bedrock).embed([record.text], SEARCH_DOCUMENT)
    local_index(vectors).put([Vector(record.chunk_id, embedding, record.metadata())])
    return PolicySearch(
        VectorRetriever(local_embedder(bedrock), local_index(vectors)),
        {"es": 0.0, "pt": 0.0, "en": 0.0},
        "docs.factoredai.sdfles.com",
    )


def demo_turn_message(aws: Aws, name: str) -> Message:
    country, language, text = DEMO[name]
    customer_id = f"c0ffee00-0000-4000-8000-{list(DEMO).index(name) + 1:012d}"
    demo_account(aws, customer_id, country, language, NOW - timedelta(hours=1))
    sent = NOW - timedelta(seconds=1)
    return customer_message(customer_id, uuid7(), uuid7(int(sent.timestamp() * 1000)), text, sent)
