import json
from typing import Any

import pytest

from clara_testing.converse import FakeConverse
from core.graphs.profiles import ModelProfile, profiles
from core.messaging import Message
from core.turn import Turn, run_turn
from demo import (
    DEMO,
    KEPT,
    NOW,
    RECORDINGS,
    base,
    demo_turn,
    kept,
    planted_charge,
    policy_index,
    quiet_choice,
    tap,
)
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
                    "Tu aclaración CLR-2026-182061 sobre el cargo en Primax por S/\xa0127.80 está en "
                    "revisión desde hoy."
                ),
                (
                    "El banco tiene hasta 10 días hábiles para resolver la aclaración desde que "
                    "inicia la revisión."
                ),
            ),
            ("case",),
        ),
        "spend_pt": (
            "repaired",
            (
                (
                    "Este mês você gastou R$\xa01.456,06 no Ipiranga, contra R$\xa01.601,37 no mês passado."
                    " Você gastou R$\xa0145,31 a menos do que no mês passado."
                ),
            ),
            ("movements",),
        ),
        "case_pt": (
            "composed",
            (
                (
                    "Sua contestação CLR-2026-862021, referente à cobrança de R$\xa0197,26 em Pão de "
                    "Açúcar no seu cartão final 6400, está em análise desde hoje. O banco analisa a "
                    "contestação em até 8 dias úteis."
                ),
            ),
            ("case",),
        ),
        "movements_es": (
            "composed",
            ("Encontré 216 movimientos en ese período. Aquí ves los más recientes en tus 3 tarjetas.",),
            ("movements",),
        ),
        "visa_es": (
            "composed",
            (
                (
                    "Tienes 61 movimientos este mes en todas tus tarjetas. Noto que tienes tarjetas "
                    "de crédito y una de débito, pero el banco no nos indica la red de cada una, así "
                    'que no puedo filtrar solo las "Visa". ¿Me puedes indicar si te refieres a tu '
                    "tarjeta terminada en 9454, tu tarjeta terminada en 3229 o tu tarjeta terminada "
                    "en 1898?"
                ),
            ),
            ("which_one",),
        ),
        "cards_pt": (
            "composed",
            (
                (
                    "Você tem 3 cartões: 2 cartões de crédito e 1 cartão de débito. Seu cartão final "
                    "2338 e seu cartão final 6913 são de crédito, ambos ativos. Seu cartão final 3530"
                    " é de débito e também está ativo."
                ),
            ),
            ("cards",),
        ),
        "charge_pt": (
            "composed",
            (
                (
                    "Encontrei 13 movimentações de Ipiranga no período de 22 de agosto a 20 de "
                    "setembro. Sobre qual delas você quer saber mais? Me diga a data ou o valor para "
                    "eu identificar a certa."
                ),
            ),
            ("movements",),
        ),
        "unrecognized_es": (
            "composed",
            (
                (
                    "Estos son tus movimientos más recientes. ¿Cuál es el que no reconoces? Si no "
                    "está entre ellos, dime su fecha o su monto."
                ),
            ),
            (
                "movements",
                "which_one",
            ),
        ),
        "unrecognized_es_tap": (
            "composed",
            (
                (
                    "Tu cargo en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30 y está aprobado. Lo "
                    "que notó el banco: el sistema de alertas del banco emitió una alerta y es tu "
                    "primera compra en este comercio."
                ),
            ),
            ("charge",),
        ),
        "unrecognized_es_pick": (
            "composed",
            (
                (
                    "Tu cargo en Inkafarma por S/\xa089.90 fue ayer a las 20:15, realizado en tienda en "
                    "Cusco y está aprobado. Ya tienes 18 compras en ese lugar, y el monto típico es "
                    "S/\xa096.85."
                ),
            ),
            (
                "charge",
                "recognize_charge",
            ),
        ),
        "unrecognized_es_kept": (
            "composed",
            (
                (
                    "Según los registros del banco, ya tienes 18 compras en Inkafarma, y la última "
                    "fue ayer. El monto típico es S/\xa096.85, y este cargo fue por S/\xa089.90, lo que "
                    "está dentro de lo habitual."
                ),
            ),
            (
                "charge",
                "recognize_charge",
            ),
        ),
        "unrecognized_pt": (
            "composed",
            (
                (
                    "Estas são suas movimentações mais recentes. Qual é a cobrança que você não "
                    "reconhece? Se não estiver entre elas, me diga a data ou o valor."
                ),
            ),
            (
                "movements",
                "which_one",
            ),
        ),
        "unrecognized_pt_tap": (
            "composed",
            (
                (
                    "Sua cobrança em TEMU.COM 2979 de R$\xa0522,83 foi hoje às 13:30 e está aprovada. O "
                    "que o banco observou: o sistema de alertas do banco emitiu um alerta e é a sua "
                    "primeira compra neste estabelecimento. Não há compras anteriores nesse "
                    "estabelecimento no seu histórico."
                ),
            ),
            ("charge",),
        ),
        "unrecognized_pt_pick": (
            "composed",
            (
                (
                    "Essa cobrança em Drogasil por R$\xa046,71 foi ontem às 19:22, na loja, e está "
                    "aprovada. Você já fez 19 compras nessa farmácia, com valor típico de R$\xa0223,94."
                ),
            ),
            (
                "charge",
                "recognize_charge",
            ),
        ),
        "cancel_es": (
            "composed",
            (
                (
                    "Si bloqueas tu tarjeta, los cobros recurrentes que se intenten con ella serán "
                    "rechazados, pero el bloqueo no cancela por sí mismo ninguna suscripción ni "
                    "ningún servicio. Tienes Movistar en tu tarjeta terminada en 5529 y Netflix en tu"
                    " tarjeta terminada en 1211: si bloqueas alguna de ellas, esos cobros quedarían "
                    "rechazados."
                ),
                (
                    "Cuando eso ocurre, cada comercio decide qué hacer con el pago rechazado. Si "
                    "luego recibes una tarjeta nueva, actualiza la forma de pago con el comercio; si "
                    "ya no quieres el servicio, cancélalo directamente con él."
                ),
            ),
            ("movements",),
        ),
        "cancel_again_es": (
            "composed",
            (
                (
                    "Si bloqueas tu tarjeta terminada en 4071, el cargo de Movistar sería rechazado "
                    "porque la tarjeta bloqueada ya no acepta nuevos cargos. Lo mismo pasaría con "
                    "Netflix en tu tarjeta terminada en 9558. El bloqueo no cancela por sí mismo "
                    "ninguna suscripción ni ningún servicio."
                ),
                (
                    "Cuando un pago es rechazado, es el comercio quien decide qué hacer con él. Si "
                    "quieres cancelar una suscripción, debes hacerlo directamente con el comercio."
                ),
            ),
            ("movements",),
        ),
        "that_one_es": (
            "composed",
            (
                (
                    "El cargo en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30, hecho por internet "
                    "y está aprobado. Lo que notó el banco: el sistema de alertas del banco emitió "
                    "una alerta y es tu primera compra en este comercio. No tienes compras previas en"
                    " ese comercio."
                ),
            ),
            ("charge",),
        ),
        "what_now_es": (
            "composed",
            (
                (
                    "Si no reconoces este cargo, puedes abrir una aclaración con Clara o llamando al "
                    "banco. Una vez abierta, el banco revisa tu caso en un plazo de 10 días hábiles."
                ),
            ),
            ("charge",),
        ),
        "topic_es": (
            "composed",
            (
                (
                    "Tu cargo en Tambo+ por S/\xa020.50 fue ayer a las 10:16, hecho en tienda en "
                    "Trujillo. Antes hiciste 36 compras ahí; lo típico es S/\xa030.80."
                ),
            ),
            (
                "charge",
                "recognize_charge",
            ),
        ),
        "topic_pt": (
            "composed",
            (
                (
                    "A cobrança no Starbucks de R$\xa021,60 foi ontem às 20:28, na loja, em São Paulo. "
                    "Você já fez 28 compras lá, com valor típico de R$\xa032,67."
                ),
            ),
            (
                "charge",
                "recognize_charge",
            ),
        ),
        "remembered_es": (
            "composed",
            ("Ya me dijiste que reconoces este cargo: «era la gasolina del viaje a Paracas».",),
            ("charge",),
        ),
        "remembered_pt": (
            "composed",
            ("Você já me disse que reconhece essa cobrança: “era a gasolina da viagem para Santos”.",),
            ("charge",),
        ),
    },
    "haiku-4-5": {
        "spend_es": (
            "composed",
            (
                (
                    "Este mes en Primax gastaste S/\xa02,091.60. El mes pasado fue S/\xa0949.50, así que "
                    "gastaste S/\xa01,142.10 más."
                ),
            ),
            ("movements",),
        ),
        "case_es": (
            "repaired",
            (
                (
                    "Tu aclaración CLR-2026-182061 está en revisión. El banco revisa la aclaración "
                    "dentro del plazo de 10 días hábiles."
                ),
            ),
            ("case",),
        ),
        "spend_pt": (
            "composed",
            ("Você gastou R$\xa0145,31 a menos no Ipiranga este mês comparado com o mês passado.",),
            ("movements",),
        ),
        "case_pt": (
            "composed",
            (
                (
                    "Sua contestação CLR-2026-862021 está em análise. O banco analisa a sua "
                    "contestação e responde dentro do prazo de análise de 8 dias úteis."
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
                    "Tienes 25 movimientos en tu tarjeta terminada en 9454 del 1 al 20 de septiembre."
                    " Entre los movimientos más recientes hay uno rechazado en Plaza Vea, uno "
                    "pendiente en Primax, y aprobados con Cabify y Rappi, además de otro rechazado "
                    "con Rappi."
                ),
            ),
            ("movements",),
        ),
        "cards_pt": (
            "composed",
            ("Você tem 2 cartões de crédito e 1 cartão de débito.",),
            ("cards",),
        ),
        "charge_pt": (
            "composed",
            (
                (
                    "Sua compra no Ipiranga por R$\xa0144,77 foi em 18 de setembro às 20:23 na loja, em "
                    "Curitiba. Você está com pendente e o banco deixou a transação em espera nos "
                    "primeiros dias. Antes você fez 31 compras nesse lugar; o valor típico é "
                    "R$\xa0238,46."
                ),
            ),
            ("charge",),
        ),
        "unrecognized_es": (
            "composed",
            (
                (
                    "Estos son tus movimientos más recientes. ¿Cuál es el que no reconoces? Si no "
                    "está entre ellos, dime su fecha o su monto."
                ),
            ),
            (
                "movements",
                "which_one",
            ),
        ),
        "unrecognized_es_tap": (
            "composed",
            (
                (
                    "Tu compra en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30 por internet. Es tu"
                    " primera compra ahí. Lo que notó el banco: el sistema de alertas del banco "
                    "emitió una alerta y es tu primera compra en este comercio."
                ),
            ),
            ("charge",),
        ),
        "unrecognized_es_pick": (
            "composed",
            (
                (
                    "Tu compra en Inkafarma por S/\xa089.90 fue ayer a las 20:15. Antes hiciste 18 "
                    "compras ahí; lo típico es S/\xa096.85."
                ),
            ),
            (
                "charge",
                "recognize_charge",
            ),
        ),
        "unrecognized_es_kept": (
            "composed",
            (
                (
                    "Lo que registra el banco es que hiciste 18 compras en Inkafarma antes de esta. "
                    "La compra fue ayer a las 20:15 en la tienda, así que fue un cargo en el punto de"
                    " venta. Si no reconoces esta compra o sospechas que no fue tuya, puedo ayudarte "
                    "a abrirla para revisión."
                ),
            ),
            (
                "charge",
                "recognize_charge",
            ),
        ),
        "unrecognized_pt": (
            "composed",
            (
                (
                    "Estas são suas movimentações mais recentes. Qual delas você não reconhece? Se "
                    "não estiver entre elas, me diga a data ou o valor."
                ),
            ),
            (
                "movements",
                "which_one",
            ),
        ),
        "unrecognized_pt_tap": (
            "composed",
            (
                (
                    "Sua compra em TEMU.COM 2979 por R$\xa0522,83 foi hoje às 13:30 e está aprovada. É "
                    "sua primeira compra nesse estabelecimento, e o banco notou: o sistema de alertas"
                    " do banco emitiu um alerta e é a sua primeira compra neste estabelecimento."
                ),
            ),
            ("charge",),
        ),
        "unrecognized_pt_pick": (
            "composed",
            (
                (
                    "Sua compra na Drogasil por R$\xa046,71 foi ontem às 19:22 na loja. Você já fez 19 "
                    "compras lá; o valor típico é R$\xa0223,94."
                ),
            ),
            (
                "charge",
                "recognize_charge",
            ),
        ),
        "cancel_es": (
            "composed",
            (
                (
                    "Si bloqueas tu tarjeta, aquella deja de funcionar para nuevas compras, y los "
                    "cargos recurrentes serán rechazados. Eso significa que tus suscripciones a "
                    "Movistar en tu tarjeta terminada en 5529 y a Netflix en tu tarjeta terminada en "
                    "1211 no podrán cobrarse, porque la tarjeta bloqueada no acepta nuevos cargos."
                ),
                (
                    "El bloqueo no cancela automáticamente las suscripciones; solo rechaza los pagos."
                    " Cuando recibas tu tarjeta nueva, puedes actualizar el método de pago con esos "
                    "servicios, o bien cancelarlas directamente con ellos si ya no las quieres."
                ),
            ),
            (),
        ),
        "cancel_again_es": (
            "repaired",
            (
                (
                    "No tengo información en los documentos del banco sobre lo que ocurre con las "
                    "suscripciones si cancelas una tarjeta. Eso depende de cómo cada comercio tenga "
                    "configurado el cobro y si tienes otra forma de pago registrada con ellos."
                ),
            ),
            (),
        ),
        "that_one_es": (
            "composed",
            (
                (
                    "Tu compra en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30. Es la primera vez "
                    "que compras ahí. Lo que notó el banco: el sistema de alertas del banco emitió "
                    "una alerta y es tu primera compra en este comercio."
                ),
            ),
            ("charge",),
        ),
        "what_now_es": (
            "fallback",
            ("La compra en TEMU.COM 2979 por S/\xa0363.10 está aprobada.",),
            ("charge",),
        ),
        "topic_es": (
            "composed",
            (
                (
                    "Tu compra en Tambo+ por S/\xa020.50 fue ayer a las 10:16 y está aprobada. Antes "
                    "hiciste 36 compras en este comercio; lo típico es S/\xa030.80."
                ),
            ),
            (
                "charge",
                "recognize_charge",
            ),
        ),
        "topic_pt": (
            "composed",
            (
                (
                    "Sua compra no Starbucks por R$\xa021,60 foi na loja em São Paulo, autorizada em seu"
                    " cartão final 3188. Antes você fez 28 compras nessa loja; o valor típico é "
                    "R$\xa032,67."
                ),
            ),
            (
                "charge",
                "recognize_charge",
            ),
        ),
        "remembered_es": (
            "composed",
            (
                (
                    "Ya me dijiste que reconoces este cargo: «era la gasolina del viaje a Paracas». "
                    "Tu compra en Tambo+ por S/\xa049.30 fue ayer a las 13:30 en tienda en Arequipa. "
                    "Antes hiciste 38 compras ahí; lo típico es S/\xa029.05."
                ),
            ),
            ("charge",),
        ),
        "remembered_pt": (
            "composed",
            (
                (
                    "Você tinha me dito que reconhecia este cargo: “era a gasolina da viagem para "
                    "Santos”. Agora que não reconhece mais, eu posso abrir uma contestação para você."
                    " Antes, gostaria de confirmar: tem certeza de que foi ontem às 20:08 na cidade "
                    "de Belo Horizonte?"
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
    country = DEMO[base(name)].country
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


@pytest.mark.parametrize("profile", profiles(), ids=lambda row: row.key)
@pytest.mark.parametrize("name", TAPPED)
def test_every_declared_model_replays_the_pick_of_a_quiet_charge_and_what_follows(
    aws: Aws, name: str, profile: ModelProfile
) -> None:
    question, history = demo_turn(aws, name)
    first, _ = replayed(name, profile, question, history)
    [ask] = [part for part in first.reply.parts if part["type"] == "ask"]
    quiet = quiet_choice(question, aws, [option["id"] for option in ask["options"]])
    picked, before = tap(question, history, first.reply, quiet)

    result, _ = replayed(f"{name}_pick", profile, picked, before)

    assert_expected(result, profile, f"{name}_pick")
    if name in KEPT:
        follow, earlier = kept(picked, before, result.reply, KEPT[name])
        assert_expected(replayed(f"{name}_kept", profile, follow, earlier)[0], profile, f"{name}_kept")


def test_the_default_model_answers_the_recorded_set_with_no_fallback_and_few_repairs() -> None:
    sources = [source for source, _, _ in EXPECTED[DEFAULT.key].values()]

    assert len(sources) == len(DEMO) + 2 * len(TAPPED) + len(KEPT)
    assert "fallback" not in sources
    assert sources.count("repaired") / len(sources) < 1 / 5


def normalized(requests: list[dict[str, Any]]) -> Any:
    return json.loads(json.dumps(requests, ensure_ascii=False, default=str))
