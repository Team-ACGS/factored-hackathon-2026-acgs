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
                    "Este mes gastaste S/\xa02,091.60 en Primax, comparado con S/\xa0949.50 el mes pasado. "
                    "Eso es S/\xa01,142.10 más que el mes pasado."
                ),
            ),
            ("movements",),
        ),
        "case_es": (
            "composed",
            (
                (
                    "Tu aclaración CLR-2026-182061 está en revisión por el cargo de S/\xa0127.80 en Primax "
                    "con tu tarjeta terminada en 4141."
                ),
                "El banco tiene hasta 10 días hábiles para revisar tu caso.",
            ),
            ("case",),
        ),
        "spend_pt": (
            "composed",
            (
                (
                    "Este mês você gastou R$\xa01.456,06 no Ipiranga, de 1 a 20 de setembro. Você gastou "
                    "R$\xa0145,31 a menos do que no mês passado, quando o total foi R$\xa01.601,37."
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
                    "Tienes 61 movimientos este mes en total, entre tus tarjetas de crédito y débito. Como "
                    "no tenemos una red de tarjeta como Visa registrada, te muestro los movimientos de este "
                    "período para todas tus tarjetas. Si me dices cuál tarjeta te interesa, con gusto lo "
                    "filtro para ti."
                ),
            ),
            ("movements",),
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
                    "Encontrei 13 movimentações do Ipiranga no período de 22 de agosto a 20 de setembro. "
                    "Sobre qual delas você quer saber mais? Me diga a data ou o valor para eu identificar a "
                    "certa."
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
                    "Al bloquear una tarjeta, los cargos recurrentes que se intenten cobrar en ella son "
                    "rechazados, pero el bloqueo no cancela por sí mismo ninguna suscripción ni ningún "
                    "servicio. Tienes Movistar en tu tarjeta terminada en 5529 y Netflix en tu tarjeta "
                    "terminada en 1211: si bloquearas alguna de ellas, el cobro de esa suscripción sería "
                    "rechazado."
                ),
                (
                    "Cuando eso pasa, cada comercio decide qué hace con el pago rechazado; si quisieras "
                    "seguir usando el servicio, tendrías que actualizar la forma de pago con ese comercio, o "
                    "cancelar la suscripción directamente con él."
                ),
            ),
            ("movements",),
        ),
        "cancel_again_es": (
            "composed",
            (
                (
                    "Si bloqueas una tarjeta, los cobros recurrentes que se intenten con ella son "
                    "rechazados, porque la tarjeta ya no acepta nuevos cargos. El bloqueo no cancela por sí "
                    "mismo ninguna suscripción ni ningún servicio."
                ),
                (
                    "Tus suscripciones están en tarjetas distintas: Movistar se cobra en tu tarjeta "
                    "terminada en 4071 y Netflix en tu tarjeta terminada en 9558. Si bloqueas solo una de "
                    "ellas, la otra suscripción seguiría cobrándose normalmente."
                ),
                (
                    "Cuando un pago es rechazado, es el comercio quien decide qué hacer; puedes actualizar "
                    "tu forma de pago cuando recibas una tarjeta nueva, o cancelar la suscripción "
                    "directamente con el comercio si ya no la quieres."
                ),
            ),
            ("movements",),
        ),
        "that_one_es": (
            "composed",
            (
                (
                    "El cargo de S/\xa0363.10 en TEMU.COM 2979 fue hoy a las 11:30, hecho por internet, y "
                    "está aprobado. Lo que notó el banco: el sistema de alertas del banco emitió una alerta "
                    "y es tu primera compra en este comercio."
                ),
            ),
            ("charge",),
        ),
        "what_now_es": (
            "composed",
            (
                (
                    "Si no reconoces el cargo en TEMU.COM 2979 por S/\xa0363.10, puedes presentar una "
                    "aclaración en la app con Clara o por teléfono, y tu caso quedará abierto con un número "
                    "de caso."
                ),
                "Una vez abierto, el banco revisa la aclaración en un plazo de 10 días hábiles.",
            ),
            (),
        ),
        "unrecognized_es_tap": (
            "composed",
            (
                (
                    "Tu cargo en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30 en tu tarjeta terminada "
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
                    "feita pela internet, em São Paulo. O que o banco observou nessa cobrança: o sistema de "
                    "alertas do banco emitiu um alerta e é a sua primeira compra neste estabelecimento."
                ),
            ),
            ("charge",),
        ),
    },
    "haiku-4-5": {
        "spend_es": (
            "composed",
            (
                (
                    "Gastaste S/\xa01,142.10 más en Primax que el mes pasado. Este mes llevabas "
                    "S/\xa02,091.60, mientras que en el mes anterior gastaste S/\xa0949.50."
                ),
            ),
            ("movements",),
        ),
        "case_es": (
            "composed",
            (
                (
                    "Tu aclaración CLR-2026-182061 está en revisión. El banco revisa tu caso dentro del "
                    "plazo de revisión de 10 días hábiles."
                ),
            ),
            ("case",),
        ),
        "spend_pt": (
            "composed",
            (
                (
                    "Você gastou R$\xa0145,31 a menos no Ipiranga neste mês em relação ao mês passado. Este "
                    "mês foram 5 compras, totalizando R$\xa01.456,06."
                ),
            ),
            ("movements",),
        ),
        "case_pt": (
            "composed",
            (
                (
                    "Sua contestação CLR-2026-862021 está em análise. O banco analisa a sua contestação "
                    "dentro 8 dias úteis."
                ),
            ),
            ("case",),
        ),
        "movements_es": (
            "repaired",
            (
                (
                    "En los últimos meses registraste 216 movimientos. Los más recientes incluyen Cineplanet "
                    "S/\xa055.90, Tambo+ S/\xa015.60, Starbucks S/\xa014.10 y S/\xa027.90, y Cabify "
                    "S/\xa041.70."
                ),
            ),
            ("movements",),
        ),
        "visa_es": (
            "repaired",
            ("Tu tarjeta terminada en 9454 tiene 25 movimientos del 1 al 20 de septiembre.",),
            ("movements",),
        ),
        "cards_pt": (
            "composed",
            ("Você tem 2 cartões de crédito e 1 cartão de débito.",),
            ("cards",),
        ),
        "charge_pt": (
            "repaired",
            (
                (
                    "Você tem várias cobranças do Ipiranga, que é um posto de gasolina. Se você quer saber "
                    "sobre qual delas, me diga a data ou o valor."
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
                    "Estas são suas transações mais recentes. Qual é a que você não reconhece? Se não "
                    "estiver entre elas, me diga a data ou o valor."
                ),
            ),
            ("which_one",),
        ),
        "cancel_es": (
            "composed",
            (
                (
                    "No encontré en los documentos del banco qué sucede si bloqueas una tarjeta. Lo que sí "
                    "veo es que tienes 2 cargos recurrentes: Movistar en tu tarjeta terminada en 5529 y "
                    "Netflix en tu tarjeta terminada en 1211. Si bloqueás una tarjeta, esos cargos no "
                    "podrían procesarse con esa tarjeta, así que tendrías que actualizarlos en los servicios "
                    "respectivos o los cargos podrían ser rechazados."
                ),
            ),
            (),
        ),
        "cancel_again_es": (
            "fallback",
            (
                (
                    "Movistar: cargo mensual de S/\xa095.60 en tu tarjeta terminada en 4071. Netflix: cargo "
                    "mensual de S/\xa038.00 en tu tarjeta terminada en 9558."
                ),
            ),
            (),
        ),
        "that_one_es": (
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
        "what_now_es": (
            "composed",
            (
                (
                    "Tu compra en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30 y está aprobada. Lo que "
                    "notó el banco: el sistema de alertas del banco emitió una alerta y es tu primera compra "
                    "en este comercio."
                ),
                (
                    "Como no la reconoces, puedes abrir una aclaración. El banco revisa tu aclaración 10 "
                    "días hábiles."
                ),
            ),
            ("charge",),
        ),
        "unrecognized_es_tap": (
            "repaired",
            (
                (
                    "Tu compra en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30 desde Cusco por "
                    "internet y está aprobada. Lo que notó el banco: el sistema de alertas del banco emitió "
                    "una alerta y es tu primera compra en este comercio."
                ),
            ),
            ("charge",),
        ),
        "unrecognized_pt_tap": (
            "composed",
            (
                (
                    "Sua compra em TEMU.COM 2979 por R$\xa0522,83 foi hoje às 13:30 pela internet e está "
                    "aprovada. O banco notou: o sistema de alertas do banco emitiu um alerta e é a sua "
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
