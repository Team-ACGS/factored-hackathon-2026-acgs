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
                    "Este mes llevas S/\xa02,091.60 en Primax, frente a S/\xa0949.50 el mes pasado. Gastaste "
                    "S/\xa01,142.10 más que el mes pasado."
                ),
            ),
            ("movements",),
        ),
        "case_es": (
            "composed",
            (
                (
                    "Tu aclaración CLR-2026-182061 sobre el cargo en Primax por S/\xa0127.80 está en "
                    "revisión desde hoy."
                ),
                "El banco tiene hasta 10 días hábiles para darte una respuesta desde que inició la revisión.",
            ),
            ("case",),
        ),
        "spend_pt": (
            "composed",
            (
                (
                    "Este mês você gastou R$\xa01.456,06 no Ipiranga, comparado com R$\xa01.601,37 no mês "
                    "passado. Você gastou R$\xa0145,31 a menos do que no mês passado."
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
                "O banco analisa a contestação em até 8 dias úteis a partir do início da revisão.",
            ),
            ("case",),
        ),
        "movements_es": (
            "composed",
            (
                (
                    "Encontré 216 movimientos en ese período. Los más recientes incluyen un cargo en "
                    "Cineplanet ayer a las 20:26, uno en Tambo+ ayer a las 15:21 y otro en Starbucks ayer a "
                    "las 10:11, entre otros."
                ),
            ),
            ("movements",),
        ),
        "visa_es": (
            "composed",
            (
                (
                    "Tienes 61 movimientos este mes en todas tus tarjetas. Como tienes tarjetas de crédito y "
                    "una de débito, dime si quieres ver los movimientos de tu tarjeta terminada en 9454 o de "
                    "tu tarjeta terminada en 3229, y te muestro los de esa en particular."
                ),
            ),
            ("which_one",),
        ),
        "cards_pt": (
            "composed",
            (
                (
                    "Você tem 3 cartões no total: 2 cartões de crédito e 1 cartão de débito. Seu cartão "
                    "final 2338 e seu cartão final 6913 são de crédito, ambos ativos. Seu cartão final 3530 "
                    "é de débito e também está ativo."
                ),
            ),
            ("cards",),
        ),
        "charge_pt": (
            "repaired",
            (
                (
                    "Encontrei 13 movimentações do Ipiranga no período de 22 de agosto a 20 de setembro. Me "
                    "diga a data ou o valor da que você quer saber mais para eu identificar a certa."
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
                    "Si bloqueas una tarjeta, los cargos recurrentes que se intenten cobrar en ella serán "
                    "rechazados, porque la tarjeta ya no acepta nuevos cargos. Esto aplica a Movistar en tu "
                    "tarjeta terminada en 5529 y a Netflix en tu tarjeta terminada en 1211. El bloqueo no "
                    "cancela por sí mismo ninguna suscripción ni ningún servicio."
                ),
                (
                    "Cuando un cobro es rechazado, cada comercio decide qué hacer: puede suspender el "
                    "servicio, reintentarlo o notificarte."
                ),
            ),
            ("movements",),
        ),
        "cancel_again_es": (
            "composed",
            (
                (
                    "Si bloqueas una tarjeta, los cargos recurrentes que se intenten cobrar en esa tarjeta "
                    "serán rechazados, pero el bloqueo no cancela ninguna suscripción ni servicio por sí "
                    "solo. Tus suscripciones están en tarjetas distintas: Movistar se cobra en tu tarjeta "
                    "terminada en 4071 y Netflix en tu tarjeta terminada en 9558, así que bloquear una "
                    "tarjeta solo afecta la suscripción que está en esa misma tarjeta."
                ),
                (
                    "Cuando un cobro es rechazado, cada comercio decide qué hace con ese pago; si quieres "
                    "dejar de recibir el servicio, deberás cancelarlo directamente con el comercio."
                ),
            ),
            ("movements",),
        ),
        "that_one_es": (
            "composed",
            (
                (
                    "El cargo es de S/\xa0363.10 en TEMU.COM 2979, realizado hoy a las 11:30 con tu tarjeta "
                    "terminada en 9899 y está aprobado. Lo que notó el banco: el sistema de alertas del "
                    "banco emitió una alerta y es tu primera compra en este comercio."
                ),
            ),
            ("charge",),
        ),
        "what_now_es": (
            "repaired",
            (
                (
                    "Si no reconoces el cargo en TEMU.COM 2979 por S/\xa0363.10, puedes abrir una aclaración "
                    "llamando al banco; tu caso quedará abierto y recibirás un número de caso."
                ),
                "Una vez abierta, el banco revisa tu aclaración en un plazo de 10 días hábiles.",
            ),
            ("movement",),
        ),
        "unrecognized_es_tap": (
            "composed",
            (
                (
                    "El cargo en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30 con tu tarjeta terminada "
                    "en 9774 y está aprobado. Lo que notó el banco: el sistema de alertas del banco emitió "
                    "una alerta y es tu primera compra en este comercio."
                ),
            ),
            ("charge",),
        ),
        "unrecognized_pt_tap": (
            "composed",
            (
                (
                    "A cobrança de R$\xa0522,83 em TEMU.COM 2979 foi hoje às 13:30 e está aprovada. Ela foi "
                    "feita pela internet, em São Paulo. O que o banco observou nessa transação: o sistema de "
                    "alertas do banco emitiu um alerta e é a sua primeira compra neste estabelecimento."
                ),
            ),
            ("charge",),
        ),
    },
    "haiku-4-5": {
        "spend_es": (
            "composed",
            ("Este mes gastaste S/\xa02,091.60 en Primax, S/\xa01,142.10 más que el mes pasado.",),
            ("movements",),
        ),
        "case_es": (
            "fallback",
            ("No pude revisar eso ahora. Intenta de nuevo en un momento.",),
            (),
        ),
        "spend_pt": (
            "composed",
            (
                (
                    "Este mês você gastou R$\xa01.456,06 no Ipiranga. Gastou R$\xa0145,31 a menos que no mês "
                    "passado, quando o total foi R$\xa01.601,37."
                ),
            ),
            ("movements",),
        ),
        "case_pt": (
            "composed",
            (
                (
                    "Sua contestação CLR-2026-862021 está em análise. O banco analisa a sua contestação e "
                    "responde dentro do prazo de análise de 8 dias úteis."
                ),
            ),
            ("case",),
        ),
        "movements_es": (
            "repaired",
            (
                (
                    "Tuviste 216 movimientos en los últimos meses. Aquí ves las más recientes: compras en "
                    "Cineplanet, Tambo+, Starbucks (varias), Cabify y muchas más."
                ),
            ),
            ("movements",),
        ),
        "visa_es": (
            "repaired",
            (
                (
                    "Tu tarjeta terminada en 9454 tiene 25 movimientos en este período. Te muestro los "
                    "movimientos más recientes: una compra en Plaza Vea rechazada, una en Primax pendiente, "
                    "y compras aprobadas en Cabify y Rappi."
                ),
            ),
            ("movements",),
        ),
        "cards_pt": (
            "composed",
            (
                (
                    "Você tem 3 cartões: 2 cartões de crédito (seu cartão final 2338 e seu cartão final "
                    "6913) e 1 cartão de débito (seu cartão final 3530). Todos estão ativos."
                ),
            ),
            ("cards",),
        ),
        "charge_pt": (
            "fallback",
            ("Não consegui verificar isso agora. Tente de novo em um momento.",),
            (),
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
            "repaired",
            (
                (
                    "Tienes 2 cargos recurrentes: Movistar en tu tarjeta terminada en 5529 y Netflix en tu "
                    "tarjeta terminada en 1211. Si bloqueas una tarjeta, los cargos recurrentes que intenten "
                    "cobrar a esa tarjeta serán rechazados. El bloqueo no cancela automáticamente tus "
                    "suscripciones, así que debes contactar con los comercios para cancelarlas si ya no las "
                    "quieres, o actualizar tus datos de pago cuando recibas una tarjeta nueva."
                ),
            ),
            (),
        ),
        "cancel_again_es": (
            "composed",
            (
                (
                    "El bloqueo de la tarjeta no cancela por sí mismo ninguna suscripción. Cuando intentan "
                    "cobrar en una tarjeta bloqueada, el cargo es rechazado. Tú decides qué hacer con cada "
                    "suscripción: si quieres continuar, actualiza la forma de pago con una tarjeta nueva "
                    "cuando la recibas, o cancélala directamente con cada comercio si ya no la quieres."
                ),
            ),
            (),
        ),
        "that_one_es": (
            "composed",
            (
                (
                    "Tu compra en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30 por internet y está "
                    "aprobada. Lo que notó el banco: el sistema de alertas del banco emitió una alerta y es "
                    "tu primera compra en este comercio."
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
                    "notó el banco: el sistema de alertas del banco emitió una alerta y es tu primera compra "
                    "en este comercio."
                ),
            ),
            ("charge",),
        ),
        "unrecognized_pt_tap": (
            "composed",
            (
                (
                    "Sua compra em TEMU.COM 2979 por R$\xa0522,83 foi hoje às 13:30 pela internet e está "
                    "aprovada. O banco viu: o sistema de alertas do banco emitiu um alerta e é a sua "
                    "primeira compra neste estabelecimento."
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
