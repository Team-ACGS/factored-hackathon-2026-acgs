import json
from typing import Any

import pytest

from clara_testing.converse import FakeConverse
from core.graphs.profiles import ModelProfile, profiles
from core.messaging import Message
from core.turn import Turn, run_turn
from demo import DEMO, NOW, RECORDINGS, demo_turn, planted_charge, policy_index, tap
from harness import Aws

EXPECTED: dict[str, dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]]] = {
    "sonnet-4-6": {
        "spend_es": (
            "composed",
            (
                (
                    "Este mes llevas S/\xa02,091.60 en Primax, comparado con S/\xa0949.50 el mes pasado. "
                    "Gastaste S/\xa01,142.10 más que el mes pasado."
                ),
            ),
            ("movements",),
        ),
        "case_es": (
            "composed",
            (
                (
                    "Tu aclaración CLR-2026-182061 por S/\xa0127.80 en Primax está en revisión desde hoy, "
                    "usando tu tarjeta terminada en 4141."
                ),
                "El banco tiene hasta 10 días hábiles para revisar tu caso.",
            ),
            ("case",),
        ),
        "spend_pt": (
            "composed",
            (
                (
                    "Este mês você gastou R$\xa01.456,06 no Ipiranga, contra R$\xa01.601,37 no mês passado. "
                    "Você gastou R$\xa0145,31 a menos do que no mês passado."
                ),
            ),
            ("movements",),
        ),
        "case_pt": (
            "composed",
            (
                (
                    "Sua contestação CLR-2026-862021, referente à cobrança de R$\xa0197,26 em Pão de Açúcar "
                    "no seu cartão final 6400, está em análise desde hoje."
                ),
                "O banco analisa a contestação em até 8 dias úteis.",
            ),
            ("case",),
        ),
        "movements_es": (
            "composed",
            ("Encontré 216 movimientos en ese período.",),
            ("movements",),
        ),
        "visa_es": (
            "composed",
            (
                (
                    "Tienes 61 movimientos este mes en tus tarjetas. Como tienes más de una tarjeta de "
                    "crédito activa, ¿cuál quieres ver: tu tarjeta terminada en 9454 o tu tarjeta terminada "
                    "en 3229?"
                ),
            ),
            ("which_one",),
        ),
        "cards_pt": (
            "composed",
            (
                (
                    "Você tem 3 cartões: 2 cartões de crédito e 1 cartão de débito. Seu cartão final 2338 e "
                    "seu cartão final 6913 são de crédito, ambos ativos. Seu cartão final 3530 é de débito e "
                    "também está ativo."
                ),
            ),
            ("cards",),
        ),
        "charge_pt": (
            "repaired",
            (
                (
                    "Encontrei 13 movimentações de Ipiranga. Sobre qual delas você quer saber mais? Me diga "
                    "a data ou o valor para eu identificar a certa."
                ),
            ),
            ("movements",),
        ),
        "unrecognized_es": (
            "composed",
            (
                (
                    "Estos son tus movimientos más recientes. ¿Cuál es el que no reconoces? Si no está entre "
                    "ellos, dime su fecha o su monto."
                ),
            ),
            ("which_one",),
        ),
        "unrecognized_pt": (
            "composed",
            (
                (
                    "Estas são suas movimentações mais recentes. Qual é a que você não reconhece? Se não "
                    "estiver entre elas, me diga a data ou o valor."
                ),
            ),
            ("which_one",),
        ),
        "cancel_es": (
            "composed",
            (
                (
                    "Si bloqueas una tarjeta, los cargos recurrentes que se intenten con ella serán "
                    "rechazados, pero el bloqueo no cancela por sí mismo ninguna suscripción ni ningún "
                    "servicio. En tu caso, Movistar cobra mensualmente a tu tarjeta terminada en 5529 y "
                    "Netflix cobra mensualmente a tu tarjeta terminada en 1211, por lo que solo se vería "
                    "afectada la suscripción de la tarjeta que bloquees."
                ),
                (
                    "Cuando un pago es rechazado, es el comercio quien decide qué hacer: puedes actualizar "
                    "tu forma de pago cuando recibas una tarjeta nueva, o cancelar la suscripción "
                    "directamente con cada comercio si ya no la necesitas."
                ),
            ),
            ("movements",),
        ),
        "cancel_again_es": (
            "composed",
            (
                (
                    "Si bloqueas una tarjeta, los cargos recurrentes que intenten cobrarse en ella serán "
                    "rechazados: la tarjeta bloqueada no acepta nuevos cargos, pero el bloqueo no cancela "
                    "las suscripciones por sí mismo."
                ),
                (
                    "Tu cargo de Movistar está en tu tarjeta terminada en 4071 y el de Netflix está en tu "
                    "tarjeta terminada en 9558. Si bloqueas alguna de esas tarjetas, el comercio "
                    "correspondiente recibirá el pago rechazado y decidirá qué hacer: puedes actualizar tu "
                    "forma de pago con una tarjeta nueva o cancelar la suscripción directamente con el "
                    "comercio."
                ),
            ),
            (),
        ),
        "that_one_es": (
            "composed",
            (
                (
                    "El cargo es de S/\xa0363.10 en TEMU.COM 2979, realizado hoy a las 11:30 por internet "
                    "con tu tarjeta terminada en 9899 y está aprobado."
                ),
                "El banco notó que es un comercio nuevo para ti: no tienes compras previas en TEMU.COM 2979.",
            ),
            ("charge",),
        ),
        "what_now_es": (
            "composed",
            (
                (
                    "Si no reconoces el cargo en TEMU.COM 2979 por S/\xa0363.10, puedes abrir una aclaración "
                    "llamando al banco para que quede registrada y recibas un número de caso."
                ),
                "Una vez abierta, el banco revisa tu aclaración en un plazo de 10 días hábiles.",
            ),
            ("movement",),
        ),
        "unrecognized_es_tap": (
            "composed",
            (
                (
                    "Tu cargo en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30 y está aprobado. Lo "
                    "hiciste por internet con tu tarjeta terminada en 9774."
                ),
                (
                    "El banco notó que es tu primera compra en este comercio y le asignó un nivel de riesgo "
                    "elevado."
                ),
            ),
            ("charge",),
        ),
        "unrecognized_pt_tap": (
            "composed",
            (
                (
                    "A cobrança de R$\xa0522,83 em TEMU.COM 2979 foi realizada hoje às 13:30 pela internet e "
                    "está aprovada. O banco identificou que é a sua primeira compra nesse estabelecimento e "
                    "o nível de risco detectado foi alto."
                ),
            ),
            ("charge",),
        ),
    },
    "haiku-4-5": {
        "spend_es": (
            "repaired",
            (
                (
                    "Gastaste S/\xa01,142.10 más en Primax este mes que el mes pasado. En este mes llevas "
                    "S/\xa02,091.60, mientras que del 1 al 31 de agosto gastaste S/\xa0949.50."
                ),
                "Esos 12 compras están entre en Arequipa.",
            ),
            ("movements",),
        ),
        "case_es": (
            "repaired",
            (
                (
                    "Tu aclaración CLR-2026-182061 está en revisión. El banco revisa tu aclaración dentro de "
                    "10 días hábiles."
                ),
            ),
            (),
        ),
        "spend_pt": (
            "composed",
            (
                (
                    "Você gastou R$\xa0145,31 a menos no Ipiranga este mês comparado com o mês passado. Este "
                    "mês foram 5 compras no total."
                ),
            ),
            ("movements",),
        ),
        "case_pt": (
            "composed",
            (
                (
                    "Sua contestação CLR-2026-862021 está em análise. O banco está analisando e responde "
                    "dentro 8 dias úteis."
                ),
            ),
            ("case",),
        ),
        "movements_es": (
            "repaired",
            ("En ese período tuviste 216 movimientos.",),
            ("movements",),
        ),
        "visa_es": (
            "repaired",
            (
                (
                    "Tienes 25 movimientos en tu tarjeta terminada en 9454 del 1 al 20 de septiembre. Los "
                    "más recientes incluyen compras en Plaza Vea, Primax, Cabify y Rappi, con estados "
                    "aprobados, pendientes y rechazados."
                ),
            ),
            ("movements",),
        ),
        "cards_pt": (
            "composed",
            (
                (
                    "Você tem 2 cartões de crédito e 1 cartão de débito. Sua tarjeta final 2338 está ativo, "
                    "sua tarjeta final 6913 está ativo e sua tarjeta final 3530 está ativo."
                ),
            ),
            ("cards",),
        ),
        "charge_pt": (
            "composed",
            (
                (
                    "Ipiranga é um posto de combustível onde você faz compras com frequência. Você tem 33 "
                    "compras lá nos últimos meses, com um valor típico de R$\xa0238,46."
                ),
            ),
            ("history",),
        ),
        "unrecognized_es": (
            "composed",
            (
                (
                    "Estos son tus movimientos más recientes. ¿Cuál es el que no reconoces? Si no está entre "
                    "ellos, dime su fecha o su monto."
                ),
            ),
            ("which_one",),
        ),
        "unrecognized_pt": (
            "composed",
            (
                (
                    "Essas são suas movimentações mais recentes. Qual delas você não reconhece? Se não "
                    "estiver entre elas, me diga a data ou o valor."
                ),
            ),
            ("which_one",),
        ),
        "cancel_es": (
            "composed",
            (
                (
                    "Si bloqueas una tarjeta, los cargos recurrentes que uses esa tarjeta serán rechazados. "
                    "El bloqueo no cancela por sí mismo ninguna suscripción: el comercio decide qué hacer "
                    "con el pago rechazado. Cuando recibas una tarjeta nueva, puedes actualizar tu forma de "
                    "pago con cada comercio o cancelar directamente con ellos si ya no quieres la "
                    "suscripción."
                ),
                (
                    "Tú tienes 2 cargos recurrentes en tus tarjetas: Movistar en tu tarjeta terminada en "
                    "5529, y Netflix en tu tarjeta terminada en 1211."
                ),
            ),
            (),
        ),
        "cancel_again_es": (
            "composed",
            (
                (
                    "No tengo información del banco sobre qué ocurre con las suscripciones si cancelas una "
                    "tarjeta. Lo que sí sé es que tienes 2 cargos recurrentes en tus tarjetas: Movistar en "
                    "tu tarjeta terminada en 4071 y Netflix en tu tarjeta terminada en 9558."
                ),
                (
                    "Te recomendaría que contactes al banco o directamente a esos servicios para saber cómo "
                    "manejan los cambios de tarjeta."
                ),
            ),
            (),
        ),
        "that_one_es": (
            "composed",
            (
                (
                    "Tu compra en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30 en tu tarjeta terminada "
                    "en 9899 y está aprobada. Lo que notó el banco: es la primera vez que compras ahí y la "
                    "puntuación de riesgo fue alta."
                ),
            ),
            ("charge",),
        ),
        "what_now_es": (
            "fallback",
            ("No pude revisar eso ahora. Intenta de nuevo en un momento.",),
            (),
        ),
        "unrecognized_es_tap": (
            "composed",
            (
                (
                    "Tu compra en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30 y está aprobada. Lo que "
                    "notó el banco: es tu primera compra en este comerciante y el monto fue evaluado como de "
                    "riesgo potencial, pero la transacción fue autorizada."
                ),
            ),
            ("charge",),
        ),
        "unrecognized_pt_tap": (
            "composed",
            (
                (
                    "Sua compra em TEMU.COM 2979 por R$\xa0522,83 foi hoje às 13:30 pela internet. Está "
                    "aprovada. O que o banco notou: você nunca havia comprado nessa loja, e o padrão da "
                    "transação trouxe uma pontuação alta de atenção."
                ),
            ),
            ("charge",),
        ),
    },
}


TAPPED = ("unrecognized_es", "unrecognized_pt")
DEFAULT = profiles()[0]


def replayed(name: str, profile: ModelProfile, message: Message, history: list[Message]) -> tuple[Turn, Any]:
    recording = json.loads((RECORDINGS / profile.key / f"{name}.json").read_text())
    model = FakeConverse([exchange["response"] for exchange in recording["exchanges"]])
    country = DEMO[name.removesuffix("_tap")].country
    result = run_turn(
        message, history, NOW, profile=profile, clients=model.client, policies=policy_index(country)
    )
    assert normalized(model.requests) == normalized(
        [exchange["request"] for exchange in recording["exchanges"]]
    )
    return result, model


def assert_expected(result: Turn, profile: ModelProfile, name: str) -> None:
    source, says, shown = EXPECTED[profile.key][name]
    assert tuple(part["text"] for part in result.reply.parts if part["type"] == "say") == says
    assert (
        tuple(part.get("view") or part.get("ask") for part in result.reply.parts if part["type"] != "say")
        == shown
    )
    assert result.reply.source == source


@pytest.mark.parametrize("profile", profiles(), ids=lambda row: row.key)
@pytest.mark.parametrize("name", list(DEMO))
def test_every_declared_model_replays_its_recorded_demo_turn(
    aws: Aws, name: str, profile: ModelProfile
) -> None:
    message, history = demo_turn(aws, name)

    result, _ = replayed(name, profile, message, history)

    assert_expected(result, profile, name)


@pytest.mark.parametrize("profile", profiles(), ids=lambda row: row.key)
@pytest.mark.parametrize("name", TAPPED)
def test_every_declared_model_replays_the_tap_on_the_planted_charge(
    aws: Aws, name: str, profile: ModelProfile
) -> None:
    question, history = demo_turn(aws, name)
    first, _ = replayed(name, profile, question, history)
    tapped, earlier = tap(
        question, history, first.reply, planted_charge(aws, question.customer_id)["transaction_id"]
    )

    result, _ = replayed(f"{name}_tap", profile, tapped, earlier)

    assert_expected(result, profile, f"{name}_tap")


def test_the_default_model_answers_the_recorded_set_with_no_fallback_and_few_repairs() -> None:
    sources = [source for source, _, _ in EXPECTED[DEFAULT.key].values()]

    assert len(sources) == len(DEMO) + len(TAPPED)
    assert "fallback" not in sources
    assert sources.count("repaired") / len(sources) < 1 / 5


def normalized(requests: list[dict[str, Any]]) -> Any:
    return json.loads(json.dumps(requests, ensure_ascii=False, default=str))
