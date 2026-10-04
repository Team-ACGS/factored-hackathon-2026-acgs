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
                    "Tu aclaración CLR-2026-182061 está en revisión desde hoy y corresponde al cargo de "
                    "S/\xa0127.80 en Primax con tu tarjeta terminada en 4141."
                ),
                "El banco revisa la aclaración en un plazo de 10 días hábiles desde que inicia la revisión.",
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
                    "Sua contestação CLR-2026-862021 está em análise e se refere a uma cobrança de "
                    "R$\xa0197,26 no Pão de Açúcar no seu cartão final 6400. A análise foi iniciada hoje. O "
                    "banco analisa a contestação em até 8 dias úteis."
                ),
            ),
            ("case",),
        ),
        "movements_es": (
            "composed",
            (
                (
                    "Tienes 216 movimientos en el período del 20 de julio al 20 de septiembre en todas tus "
                    "tarjetas. Los más recientes aparecen a continuación."
                ),
            ),
            ("movements",),
        ),
        "visa_es": (
            "composed",
            (
                (
                    "Tienes 61 movimientos en este período. Ten en cuenta que tienes 2 tarjetas de crédito, "
                    "¿quieres ver los movimientos de tu tarjeta terminada en 9454 o de tu tarjeta terminada "
                    "en 3229?"
                ),
            ),
            ("which_one",),
        ),
        "cards_pt": (
            "composed",
            (
                (
                    "Você tem 2 cartões de crédito e 1 cartão de débito. Seu cartão final 2338 e seu cartão "
                    "final 6913 são de crédito, ambos ativos, e seu cartão final 3530 é de débito, também "
                    "ativo."
                ),
            ),
            ("cards",),
        ),
        "charge_pt": (
            "repaired",
            (
                (
                    "Encontrei 13 movimentações em Ipiranga no período de 22 de agosto a 20 de setembro. "
                    "Para te ajudar, pode me informar a data ou o valor da cobrança que você quer saber?"
                ),
            ),
            ("movements",),
        ),
        "unrecognized_es": (
            "composed",
            (
                (
                    "Estos son tus movimientos más recientes. ¿Cuál es el que no reconoces? Si no está aquí, "
                    "dime su fecha o monto y lo busco."
                ),
            ),
            ("which_one",),
        ),
        "unrecognized_pt": (
            "composed",
            (
                (
                    "Estas são suas movimentações mais recentes. Qual é a que você não reconhece? Se não "
                    "estiver aqui, me diga a data ou o valor."
                ),
            ),
            ("which_one",),
        ),
        "cancel_es": (
            "repaired",
            (
                (
                    "Si bloqueas tu tarjeta terminada en 0355 o tu tarjeta terminada en 1211, los cargos "
                    "recurrentes que intenten cobrarse en la tarjeta bloqueada serán rechazados, pero el "
                    "bloqueo no cancela por sí mismo ninguna suscripción ni ningún servicio."
                ),
                (
                    "Tienes Movistar en tu tarjeta terminada en 5529 y Netflix en tu tarjeta terminada en "
                    "1211. Si bloqueas la tarjeta correspondiente, el siguiente cobro sería rechazado, pero "
                    "el servicio seguiría activo hasta que lo canceles directamente con cada proveedor."
                ),
            ),
            ("movements",),
        ),
        "cancel_again_es": (
            "composed",
            (
                (
                    "Si bloqueas una tarjeta, los cargos recurrentes que se intenten cobrar en ella serán "
                    "rechazados, porque la tarjeta ya no acepta nuevos cargos. Sin embargo, el bloqueo no "
                    "cancela por sí mismo ninguna suscripción ni ningún servicio. Para dejar de pagar esas "
                    "suscripciones, necesitas cancelarlas directamente con cada proveedor."
                ),
            ),
            (),
        ),
        "that_one_es": (
            "composed",
            (
                (
                    "El cargo es de S/\xa0363.10 en TEMU.COM 2979, hecho hoy a las 11:30 por internet y está "
                    "aprobado. El banco nota que es un comercio nuevo para ti y le asignó una puntuación de "
                    "riesgo alta."
                ),
                "Si no lo reconoces, puedes llamar al banco para abrir una aclaración.",
            ),
            ("charge",),
        ),
        "what_now_es": (
            "composed",
            (
                (
                    "Si no reconoces el cargo en TEMU.COM 2979 por S/\xa0363.10 hoy a las 11:30, puedes "
                    "abrir una aclaración con el banco. Para hacerlo, comunícate directamente con el banco "
                    "desde el número al reverso de tu tarjeta terminada en 1977."
                ),
                "Una vez abierta la aclaración, el banco la revisará y te responderá en 10 días hábiles.",
            ),
            ("movement",),
        ),
        "unrecognized_es_tap": (
            "composed",
            (
                (
                    "El cargo en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30, realizado por internet "
                    "desde Cusco y está aprobado. El banco notó que es un comercio nuevo para ti y que la "
                    "operación tiene un perfil de riesgo elevado."
                ),
            ),
            ("charge",),
        ),
        "unrecognized_pt_tap": (
            "composed",
            (
                (
                    "A cobrança de R$\xa0522,83 em TEMU.COM 2979 foi hoje às 13:30, feita pela internet, e "
                    "está aprovada. É a primeira vez que vemos uma compra nesse estabelecimento no seu "
                    "cartão final 9315."
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
                    "Gastaste S/\xa02,091.60 en Primax este mes, S/\xa01,142.10 más que el mes pasado cuando "
                    "gastaste S/\xa0949.50."
                ),
            ),
            ("movements",),
        ),
        "case_es": (
            "composed",
            (
                (
                    "Tu aclaración CLR-2026-182061 está en revisión. El banco revisa tu aclaración y te "
                    "responde dentro del plazo de revisión de 10 días hábiles."
                ),
            ),
            ("case",),
        ),
        "spend_pt": (
            "composed",
            (
                (
                    "Este mês você gastou R$\xa01.456,06 no Ipiranga, ou seja, R$\xa0145,31 a menos que no "
                    "mês passado."
                ),
            ),
            ("movements",),
        ),
        "case_pt": (
            "composed",
            (
                (
                    "Sua contestação CLR-2026-862021 está em análise. O banco analisa sua contestação e "
                    "responde dentro de 8 dias úteis."
                ),
            ),
            ("case",),
        ),
        "movements_es": (
            "repaired",
            (
                (
                    "Tienes 212 movimientos en los últimos meses. Estos son tus movimientos más recientes: "
                    "una compra en Cineplanet, otra en Tambo+, compras en Starbucks y una en Cabify."
                ),
            ),
            ("movements",),
        ),
        "visa_es": (
            "repaired",
            (
                (
                    "Tu tarjeta terminada en 9454 tiene 25 movimientos del 1 al 20 de septiembre. Los "
                    "movimientos más recientes son compras en Plaza Vea, Primax, Cabify, Rappi y Rappi."
                ),
            ),
            ("movements",),
        ),
        "cards_pt": (
            "composed",
            (
                (
                    "Você tem 3 cartões. São 2 cartões de crédito (seu cartão final 2338 e seu cartão final "
                    "6913) e 1 cartão de débito (seu cartão final 3530). Todos estão ativos."
                ),
            ),
            ("cards",),
        ),
        "charge_pt": (
            "composed",
            (
                (
                    "Você tem cobranças em Ipiranga, que é um combustível na categoria de transporte. A "
                    "cobrança mais recente é de R$\xa0144,77 em 18 de setembro às 20:23 no seu cartão final "
                    "4237, e está pendente enquanto o banco confirma a transação."
                ),
                (
                    "É um valor um pouco menor do que seus abastecimentos típicos nessa rede, mas você tem "
                    "31 compras em Ipiranga."
                ),
            ),
            ("movement",),
        ),
        "unrecognized_es": (
            "composed",
            (
                (
                    "Estos son tus movimientos más recientes. ¿Cuál es el que no reconoces? Si no está, dime "
                    "su fecha o su monto."
                ),
            ),
            ("which_one",),
        ),
        "unrecognized_pt": (
            "composed",
            (
                (
                    "Estas são suas movimentações mais recentes. Qual delas você não reconhece? Se não "
                    "estiver aqui, me diz a data ou o valor."
                ),
            ),
            ("which_one",),
        ),
        "cancel_es": (
            "repaired",
            (
                (
                    "Si cancelas tu tarjeta, dejará de funcionar para nuevas compras y retiros. Los cargos "
                    "recurrentes se rechazarán porque la tarjeta ya no acepta nuevos cargos. El bloqueo no "
                    "cancela por sí mismo ninguna suscripción ni ningún servicio, así que tendrías que "
                    "cancelarlas directamente con cada proveedor si quieres que dejen de cobrarte."
                ),
            ),
            (),
        ),
        "cancel_again_es": (
            "repaired",
            (
                (
                    "No tengo información del banco sobre qué ocurre con las suscripciones si cancelas una "
                    "tarjeta. Eso depende de cada proveedor de servicio. Tienes 2 cargos recurrentes "
                    "suscritas: Movistar en tu tarjeta terminada en 4071 y Netflix en tu tarjeta terminada "
                    "en 9558. Te recomendamos que contactes directamente con ellos para saber cómo proceder "
                    "antes de hacer cambios en tu tarjeta."
                ),
            ),
            (),
        ),
        "that_one_es": (
            "composed",
            (
                (
                    "Tu compra en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30 por internet y está "
                    "aprobada. Es la primera vez que compras en ese comerciante."
                ),
            ),
            ("charge",),
        ),
        "what_now_es": (
            "composed",
            (
                (
                    "La compra en TEMU.COM 2979 por S/\xa0363.10 está aprobada, así que el dinero ya se "
                    "procesó. Es tu primera compra en este comercio, lo que disparó las alertas del banco, "
                    "pero no hay una aclaración abierta todavía. Si quieres reportarla, puedes abrir un "
                    "caso."
                ),
            ),
            ("charge",),
        ),
        "unrecognized_es_tap": (
            "composed",
            (
                (
                    "Tu compra en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30 en tu tarjeta terminada "
                    "en 9774 y está aprobada. El banco notó que es tu primera compra en este comercio y que "
                    "tiene características que merecen atención."
                ),
            ),
            ("charge",),
        ),
        "unrecognized_pt_tap": (
            "composed",
            (
                (
                    "Sua compra em TEMU.COM 2979 por R$\xa0522,83 foi hoje às 13:30 e está aprovada. O que o "
                    "banco notou: você não tinha feito compras nessa loja antes e o padrão de risco da "
                    "transação foi alto."
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
