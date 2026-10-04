import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from clara_testing import FakeBedrockRuntime, FakeS3Vectors, local_embedder, local_index
from core.ids import uuid7_at
from core.messaging import Message, customer_message, reply_to
from core.policies import chunk_id, policy_facts
from core.replies import Reply
from core.retrieval import NON_FILTERABLE, ChunkRecord, PolicySearch, VectorRetriever
from core.vectors import SEARCH_DOCUMENT, Vector
from crud.catalog import COUNTRIES
from crud.generator import Claim, Score, manual_transaction
from harness import Aws, demo_account, uuid7

NOW = datetime(2026, 9, 20, 17, 0, tzinfo=UTC)
RECORDINGS = Path(__file__).parent / "core" / "recordings"
PLANTED_SUFFIX = 2979


@dataclass(frozen=True)
class Document:
    slug: str
    group: str
    topic: str
    doc_type: str
    title: str
    text: str
    figures: tuple[str, ...]
    page: int


DOCUMENTS = {
    "PE": (
        Document(
            "dispute-lifecycle",
            "disputes",
            "dispute_lifecycle",
            "procedure",
            "Ciclo de una aclaración",
            "El banco revisa tu aclaración y te responde dentro del plazo de revisión de "
            "{{policy.claims.review_time}}.",
            ("claims.review_time",),
            4,
        ),
        Document(
            "blocked-card-effects",
            "card_security",
            "blocked_card_effects",
            "guide",
            "Qué deja de funcionar cuando se bloquea una tarjeta",
            "Con el bloqueo confirmado, la tarjeta deja de funcionar para nuevas compras y retiros. Un cobro "
            "recurrente o una suscripción que se intente con la tarjeta bloqueada es rechazado, porque la "
            "tarjeta ya no acepta nuevos cargos. El bloqueo no cancela por sí mismo ninguna suscripción ni "
            "ningún servicio.",
            ("cards.replacement_time",),
            2,
        ),
    ),
    "BR": (
        Document(
            "dispute-lifecycle",
            "disputes",
            "dispute_lifecycle",
            "procedure",
            "Ciclo de uma contestação",
            "O banco analisa a sua contestação e responde dentro do prazo de análise de "
            "{{policy.claims.review_time}}.",
            ("claims.review_time",),
            4,
        ),
        Document(
            "blocked-card-effects",
            "card_security",
            "blocked_card_effects",
            "guide",
            "O que deixa de funcionar quando um cartão é bloqueado",
            "Com o bloqueio confirmado, o cartão deixa de funcionar para novas compras e saques. Uma "
            "cobrança recorrente ou uma assinatura tentada com o cartão bloqueado é recusada, porque o "
            "cartão não aceita mais novas cobranças. O bloqueio não cancela por si só nenhuma assinatura "
            "nem nenhum serviço.",
            ("cards.replacement_time",),
            2,
        ),
    ),
}


@dataclass(frozen=True)
class DemoTurn:
    country: str
    locale: str
    text: str
    history: tuple[tuple[str, str], ...] = ()
    planted: bool = False


SUBSCRIPTIONS_ES = (
    ("customer", "¿tengo suscripciones?"),
    (
        "assistant",
        "Sí, veo 2 cargos recurrentes en tus tarjetas: Movistar, mensual, y Netflix, mensual.",
    ),
)
CANCEL_ES = "¿qué pasa si cancelo mi tarjeta? esas suscripciones quién las paga?"
UNRECOGNIZED_ES = (
    ("customer", "hay una transacción que no reconozco"),
    ("assistant", "¿Me dices la fecha o el monto del cargo que no reconoces?"),
    ("customer", "es una de hoy"),
    ("assistant", "Encontré 1 movimiento, hoy."),
)
NOT_MINE_ES = (
    *UNRECOGNIZED_ES,
    ("customer", "esa es"),
    ("assistant", "Es una compra por internet que el sistema de alertas del banco marcó."),
    ("customer", "no la reconozco"),
    (
        "assistant",
        "Entiendo. Es tu primera compra en este comercio y el sistema de alertas del banco la marcó.",
    ),
)

DEMO = {
    "spend_es": DemoTurn("PE", "es", "¿Cuánto gasté en Primax este mes vs el pasado?"),
    "case_es": DemoTurn("PE", "es", "¿cuándo me devuelven la plata de mi aclaración?"),
    "spend_pt": DemoTurn("BR", "pt-BR", "Quanto gastei no Ipiranga este mês comparado com o mês passado?"),
    "case_pt": DemoTurn("BR", "pt-BR", "quando vou receber o dinheiro da minha contestação?"),
    "movements_es": DemoTurn("PE", "es", "transacciones de los últimos 2 meses"),
    "visa_es": DemoTurn("PE", "es", "movimientos de mi Visa de septiembre"),
    "cards_pt": DemoTurn("BR", "pt-BR", "quais são os meus cartões?"),
    "charge_pt": DemoTurn("BR", "pt-BR", "o que é essa cobrança do Ipiranga?"),
    "unrecognized_es": DemoTurn("PE", "es", "hay una transacción que no reconozco", planted=True),
    "unrecognized_pt": DemoTurn("BR", "pt-BR", "tem uma transação que eu não reconheço", planted=True),
    "cancel_es": DemoTurn("PE", "es", CANCEL_ES, SUBSCRIPTIONS_ES),
    "cancel_again_es": DemoTurn(
        "PE",
        "es",
        CANCEL_ES,
        (
            *SUBSCRIPTIONS_ES,
            ("customer", CANCEL_ES),
            ("assistant", "No tengo información del banco sobre eso."),
        ),
    ),
    "that_one_es": DemoTurn("PE", "es", "esa es", UNRECOGNIZED_ES, planted=True),
    "what_now_es": DemoTurn("PE", "es", "¿y ahora qué pasa?", NOT_MINE_ES, planted=True),
}


def policy_index(country: str) -> PolicySearch:
    bedrock, vectors = FakeBedrockRuntime(), FakeS3Vectors(NON_FILTERABLE)
    facts = policy_facts()[country]
    records = [
        ChunkRecord(
            chunk_id=chunk_id(f"{country.lower()}-{document.slug}", 2, facts.version, 3, 1),
            country=country,
            language=facts.language,
            group=document.group,
            topic=document.topic,
            doc_type=document.doc_type,
            doc_id=f"{country.lower()}-{document.slug}",
            version=2,
            facts_version=facts.version,
            effective_date=date(2026, 9, 1),
            section=document.title,
            title=document.title,
            text=document.text.replace("{{policy.claims.review_time}}", "…"),
            figures={key: facts.specs[key] for key in document.figures},
            page_start=document.page,
            page_end=document.page + 1,
            url=f"https://docs.factoredai.sdfles.com/{country}/{country.lower()}-{document.slug}-v2-f{facts.version}.pdf",
            content_hash=facts.language,
        )
        for document in DOCUMENTS[country]
    ]
    embeddings = local_embedder(bedrock).embed([record.text for record in records], SEARCH_DOCUMENT)
    local_index(vectors).put(
        Vector(record.chunk_id, embedding, record.metadata())
        for record, embedding in zip(records, embeddings, strict=True)
    )
    return PolicySearch(
        VectorRetriever(local_embedder(bedrock), local_index(vectors)),
        {"es": 0.0, "pt": 0.0, "en": 0.0},
        "docs.factoredai.sdfles.com",
    )


def demo_turn(aws: Aws, name: str) -> tuple[Message, list[Message]]:
    turn = DEMO[name]
    customer_id = f"c0ffee00-0000-4000-8000-{list(DEMO).index(name) + 1:012d}"
    account = demo_account(aws, customer_id, turn.country, turn.locale, NOW - timedelta(hours=1))
    if turn.planted:
        plant_charge(aws, customer_id, turn.country, account.cards[0]["product_id"])
    room = uuid7()
    history: list[Message] = []
    sent = NOW - timedelta(minutes=len(turn.history) + 1)
    for sender, text in turn.history:
        if sender == "customer":
            history.append(
                customer_message(customer_id, room, uuid7(int(sent.timestamp() * 1000)), text, sent)
            )
        else:
            history.append(reply_to(history[-1], "assistant", text, sent))
        sent += timedelta(minutes=1)
    sent = NOW - timedelta(seconds=1)
    return customer_message(customer_id, room, uuid7(int(sent.timestamp() * 1000)), turn.text, sent), history


def plant_charge(aws: Aws, customer_id: str, country: str, product_id: str) -> dict[str, object]:
    at = NOW - timedelta(minutes=30)
    claim = Claim(customer_id, COUNTRIES[country], NOW - timedelta(hours=1))
    item = manual_transaction(
        random.Random(PLANTED_SUFFIX),  # noqa: S311
        claim,
        product_id,
        str(uuid7_at(at, PLANTED_SUFFIX)),
        PLANTED_SUFFIX,
        Score.FLAGGED,
    )
    aws.transactions.put_item(Item=item)
    return item


def tap(
    question: Message, history: list[Message], first: Reply, option: str
) -> tuple[Message, list[Message]]:
    asked = reply_to(question, "assistant", first.text, NOW, first.parts, first.facts, first.draft)
    [ask] = [part for part in first.parts if part["type"] == "ask"]
    [label] = [entry["label"] for entry in ask["options"] if entry["id"] == option]
    tapped_at = NOW - timedelta(milliseconds=500)
    message = customer_message(
        question.customer_id,
        question.room_id,
        uuid7(int(tapped_at.timestamp() * 1000)),
        label,
        tapped_at,
        input={"ask_id": asked.message_id, "option": option},
    )
    return message, [*history, question, asked]


def planted_charge(aws: Aws, customer_id: str) -> dict[str, Any]:
    items = aws.transactions.query(
        KeyConditionExpression="customer_id = :id", ExpressionAttributeValues={":id": customer_id}
    )["Items"]
    [planted] = [item for item in items if str(item["merchant_name"]).endswith(" 2979")]
    return planted
