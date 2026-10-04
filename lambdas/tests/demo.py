import random
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from clara_testing import FakeBedrockRuntime, FakeS3Vectors, local_embedder, local_index
from core.countries import zone
from core.facts.catalog import MONTHS
from core.facts.render import format_money
from core.ids import uuid7_at
from core.messaging import Message, customer_message, reply_to
from core.policies import chunk_id, policy_facts
from core.replies import Reply
from core.retrieval import NON_FILTERABLE, ChunkRecord, PolicySearch, VectorRetriever
from core.vectors import SEARCH_DOCUMENT, Vector
from crud.catalog import COUNTRIES
from crud.generator import Claim, Score, manual_transaction
from harness import Aws, demo_account

NOW = datetime(2026, 9, 20, 17, 0, tzinfo=UTC)
RECORDINGS = Path(__file__).parent / "core" / "recordings"
PLANTED_SUFFIX = 2979
ROOM_SEED = 1
MESSAGE_SEED = 1_000
PLACEHOLDER = re.compile(r"\{\{policy\.[a-z_.]+\}\}")


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
    section: int = 3


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
        Document(
            "dispute-lifecycle",
            "disputes",
            "dispute_lifecycle",
            "procedure",
            "Ciclo de una aclaración",
            "Apertura. Usted presenta la aclaración en la app con Clara o por teléfono en el "
            "{{policy.channels.phone}}. Su caso queda abierto y usted recibe un número de caso.",
            ("channels.phone",),
            3,
            2,
        ),
        Document(
            "blocked-card-effects",
            "card_security",
            "blocked_card_effects",
            "guide",
            "Qué deja de funcionar cuando se bloquea una tarjeta",
            "Mi suscripción fue rechazada: el comercio decide qué hace con un pago rechazado. Actualice la "
            "forma de pago cuando reciba la tarjeta nueva, o cancélela con el comercio si ya no la quiere.",
            ("cards.replacement_time",),
            3,
            7,
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
        Document(
            "dispute-lifecycle",
            "disputes",
            "dispute_lifecycle",
            "procedure",
            "Ciclo de uma contestação",
            "Abertura. Você apresenta a contestação no app com a Clara ou por telefone no "
            "{{policy.channels.phone}}. Seu caso fica aberto e você recebe um número de caso.",
            ("channels.phone",),
            3,
            2,
        ),
        Document(
            "blocked-card-effects",
            "card_security",
            "blocked_card_effects",
            "guide",
            "O que deixa de funcionar quando um cartão é bloqueado",
            "Minha assinatura foi recusada: o estabelecimento decide o que faz com um pagamento recusado. "
            "Atualize a forma de pagamento quando receber o cartão novo, ou cancele a assinatura com o "
            "estabelecimento se você não a quer mais.",
            ("cards.replacement_time",),
            3,
            7,
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
    topic: Literal["", "charge", "remembered", "flagged"] = ""


TOPIC_TEXT = {
    "es": "No reconozco el cargo de {merchant} por {amount} del {date}.",
    "pt-BR": "Não reconheço a cobrança de {merchant} de {amount} em {date}.",
}
NOTES = {"es": "era la gasolina del viaje a Paracas", "pt-BR": "era a gasolina da viagem para Santos"}


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
    "topic_es": DemoTurn("PE", "es", TOPIC_TEXT["es"], topic="charge"),
    "topic_pt": DemoTurn("BR", "pt-BR", TOPIC_TEXT["pt-BR"], topic="charge"),
    "remembered_es": DemoTurn("PE", "es", TOPIC_TEXT["es"], topic="remembered"),
    "remembered_pt": DemoTurn("BR", "pt-BR", TOPIC_TEXT["pt-BR"], topic="remembered"),
    "flagged_es": DemoTurn("PE", "es", TOPIC_TEXT["es"], planted=True, topic="flagged"),
    "flagged_pt": DemoTurn("BR", "pt-BR", TOPIC_TEXT["pt-BR"], planted=True, topic="flagged"),
    "unblock_es": DemoTurn("PE", "es", "Desbloquea mi tarjeta, por favor"),
    "unblock_pt": DemoTurn("BR", "pt-BR", "desbloqueia meu cartão, por favor"),
}
KEPT = {"unrecognized_es": "¿y por qué me cobraron eso si casi no voy?"}


FLAGGED = ("flagged_es", "flagged_pt")


def base(name: str) -> str:
    for suffix in ("_why", "_no", "_block", "_yes", "_card", "_open", "_tap", "_pick", "_kept"):
        name = name.removesuffix(suffix)
    return name


def policy_index(country: str) -> PolicySearch:
    bedrock, vectors = FakeBedrockRuntime(), FakeS3Vectors(NON_FILTERABLE)
    facts = policy_facts()[country]
    records = [
        ChunkRecord(
            chunk_id=chunk_id(f"{country.lower()}-{document.slug}", 2, facts.version, document.section, 1),
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
            text=document.text.replace("{{policy.claims.review_time}}", "…").replace(
                "{{policy.channels.phone}}", "…"
            ),
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
    planted = (
        plant_charge(aws, customer_id, turn.country, account.cards[0]["product_id"]) if turn.planted else None
    )
    room = str(uuid7_at(NOW - timedelta(hours=1), ROOM_SEED))
    history: list[Message] = []
    sent = NOW - timedelta(minutes=len(turn.history) + 1)
    for sender, text in turn.history:
        if sender == "customer":
            history.append(customer_message(customer_id, room, demo_id(sent, len(history)), text, sent))
        else:
            history.append(reply_to(history[-1], "assistant", text, sent))
        sent += timedelta(minutes=1)
    sent = NOW - timedelta(seconds=1)
    text, input = turn.text, None
    if turn.topic:
        row = dict(planted) if turn.topic == "flagged" and planted else habitual_charge(account.transactions)
        if turn.topic == "remembered":
            remember(aws, customer_id, row, NOTES[turn.locale])
        text = turn.text.format(
            merchant=row["merchant_name"],
            amount=format_money(Decimal(str(row["amount"])), str(row["currency"]), turn.locale),
            date=long_date(datetime.fromisoformat(str(row["transaction_date"])), turn.country, turn.locale),
        )
        input = {
            "topic": {
                "type": "charge",
                "product_id": row["product_id"],
                "transaction_id": row["transaction_id"],
            }
        }
    return customer_message(customer_id, room, demo_id(sent, len(history)), text, sent, input=input), history


def demo_id(at: datetime, index: int) -> str:
    return str(uuid7_at(at, MESSAGE_SEED + index))


def habitual_charge(rows: list[dict[str, Any]]) -> dict[str, Any]:
    approved = sorted(
        (row for row in rows if row["transaction_status"] == "Approved"),
        key=lambda row: (row["transaction_date"], row["transaction_id"]),
        reverse=True,
    )
    for row in approved:
        prior = [
            other for other in approved if other["merchant_name"] == row["merchant_name"] and other is not row
        ]
        if Decimal(str(row.get("fraud_score", 0))) <= 30 and len(prior) >= 2:
            return row
    raise LookupError("no habitual charge in the demo account")


def quiet_choice(question: Message, aws: Aws, options: list[str]) -> str:
    rows = {
        str(item["transaction_id"]): item
        for item in aws.transactions.query(
            KeyConditionExpression="customer_id = :id",
            ExpressionAttributeValues={":id": question.customer_id},
        )["Items"]
    }
    return next(option for option in options if Decimal(str(rows[option].get("fraud_score", 0))) <= 30)


def remember(aws: Aws, customer_id: str, row: dict[str, Any], note: str) -> None:
    aws.memory.put_item(
        Item={
            "customer_id": customer_id,
            "memory_key": f"recognized_charge#{row['transaction_id']}",
            "type": "recognized_charge",
            "subject": row["transaction_id"],
            "note": note,
            "source_room_id": str(uuid7_at(NOW - timedelta(days=2), 1)),
            "created_at": "2026-09-18T15:00:00.000Z",
            "ask_id": str(uuid7_at(NOW - timedelta(days=2), 2)),
            "merchant": row["merchant_name"],
            "product_id": row["product_id"],
            "amount": Decimal(str(row["amount"])),
            "currency": row["currency"],
            "charged_at": row["transaction_date"],
        }
    )


def long_date(at: datetime, country: str, locale: str) -> str:
    day = at.astimezone(zone(country)).date()
    month = MONTHS[locale][day.month - 1]
    return f"{day.day} de {month} de {day.year}"


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


def kept(question: Message, history: list[Message], first: Reply, text: str) -> tuple[Message, list[Message]]:
    asked = reply_to(question, "assistant", first.text, NOW, first.parts, first.facts, first.draft)
    sent = NOW - timedelta(milliseconds=200)
    message = customer_message(
        question.customer_id, question.room_id, demo_id(sent, len(history) + 1), text, sent
    )
    return message, [*history, question, asked]


def tap(
    question: Message, history: list[Message], first: Reply, option: str, step: int = 0
) -> tuple[Message, list[Message]]:
    asked = reply_to(question, "assistant", first.text, NOW, first.parts, first.facts, first.draft)
    [ask] = [part for part in first.parts if part["type"] == "ask"]
    [label] = [entry["label"] for entry in ask["options"] if entry["id"] == option]
    tapped_at = NOW - timedelta(milliseconds=500 - 100 * step)
    message = customer_message(
        question.customer_id,
        question.room_id,
        demo_id(tapped_at, len(history) + 1),
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
