import json
from typing import Any

import pytest

from clara_testing.converse import FakeConverse
from core.graphs.profiles import ModelProfile, profiles
from core.turn import run_turn
from demo import DEMO, NOW, RECORDINGS, demo_turn_message, policy_index
from harness import Aws

EXPECTED = {
    "sonnet-4-6": {
        "cards_pt": (
            "composed",
            (
                (
                    "Você tem 3 cartões: 2 cartões de crédito e 1 cartão de débito. Seu cartão final 2338 e "
                    "seu cartão final 6913 são de crédito, ambos com status ativo. Seu cartão final 3530 é "
                    "de débito, também ativo."
                ),
            ),
            ("cards",),
        ),
        "case_es": (
            "composed",
            (
                (
                    "Tu aclaración CLR-2026-182061 por el cargo en Primax está actualmente en revisión, "
                    "abierta el 14 de septiembre."
                ),
                (
                    "El banco tiene un plazo de 10 días hábiles para responderte desde que la revisión "
                    "comenzó. No puedo prometerte una fecha exacta, pero ese es el plazo máximo del proceso."
                ),
            ),
            ("case",),
        ),
        "case_pt": (
            "composed",
            (
                (
                    "Sua contestação CLR-2026-862021 referente a uma cobrança de R$\xa0197,26 em Pão de "
                    "Açúcar está atualmente em análise, com revisão iniciada hoje. O banco tem até 8 dias "
                    "úteis para concluir a análise."
                ),
            ),
            ("case",),
        ),
        "charge_pt": (
            "composed",
            (
                (
                    "Encontrei 13 movimentações do Ipiranga nos últimos meses, todas feitas na loja em "
                    "Curitiba, na categoria de transporte. A mais recente, em 18 de setembro às 20:23, é de "
                    "R$\xa0144,77 com seu cartão final 4237 e ainda está pendente. Qual delas você gostaria "
                    "de saber mais?"
                ),
            ),
            (
                "movements",
                "which_one",
            ),
        ),
        "movements_es": (
            "composed",
            (
                (
                    "En ese período encontré 216 movimientos en tus tarjetas. Los más recientes incluyen un "
                    "cargo en Cineplanet con tu tarjeta terminada en 9739, otro en Tambo+ con tu tarjeta "
                    "terminada en 9739 y uno en Starbucks con tu tarjeta terminada en 6720."
                ),
            ),
            ("movements",),
        ),
        "spend_es": (
            "composed",
            (
                (
                    "Este mes gastaste S/\xa02,091.60 en Primax, comparado con S/\xa0949.50 el mes pasado. "
                    "Eso es S/\xa01,142.10 más que el mes anterior."
                ),
                "En total hay 18 movimientos en ese período, repartidos entre tus tarjetas.",
            ),
            ("movements",),
        ),
        "spend_pt": (
            "composed",
            (
                (
                    "Este mês você gastou R$\xa01.456,06 no Ipiranga em 5 compras, enquanto no mês passado o "
                    "total foi R$\xa01.601,37. Ou seja, você gastou R$\xa0145,31 menos em comparação ao mês "
                    "anterior."
                ),
                "Há uma cobrança de R$\xa0301,00 com status pendente na movimentação mais recente.",
            ),
            ("movements",),
        ),
        "visa_es": (
            "composed",
            (
                (
                    "Tienes 2 tarjetas de crédito con movimientos este mes. Tu tarjeta terminada en 9454 "
                    "tiene 25 movimientos y tu tarjeta terminada en 3229 tiene 19 movimientos. ¿De cuál "
                    "quieres ver los movimientos?"
                ),
            ),
            ("which_one",),
        ),
    },
    "haiku-4-5": {
        "cards_pt": (
            "composed",
            ("Você tem 2 cartões de crédito de crédito e 1 cartão de débito.",),
            ("cards",),
        ),
        "case_es": (
            "composed",
            (
                (
                    "Tu aclaración CLR-2026-182061 por S/\xa0127.80 está en revisión. El banco te responde "
                    "dentro de 10 días hábiles. Cuando se resuelva, te diremos el resultado del análisis."
                ),
            ),
            ("case",),
        ),
        "case_pt": (
            "repaired",
            (
                (
                    "Sua contestação CLR-2026-862021 está em análise. O banco analisa contestações dentro do "
                    "prazo de 8 dias úteis."
                ),
                (
                    "Não tenho informações sobre o que acontece após a análise. O que posso te mostrar é o "
                    "status atual da sua contestação."
                ),
            ),
            ("case",),
        ),
        "charge_pt": (
            "composed",
            (
                (
                    "Você tem 13 movimentações em Ipiranga nos últimos dias. A mais recente, de R$\xa0144,77 "
                    "na loja, está pendente desde 18 de setembro às 20:23 em Curitiba."
                ),
                (
                    "É um abastecimento comum para você: você faz aproximadamente 31 compras lá, e esta é "
                    "menor que o seu valor típico."
                ),
            ),
            ("movements",),
        ),
        "movements_es": (
            "repaired",
            (
                (
                    "En ese período tienes 216 movimientos. Aquí están los más recientes: compras en "
                    "Cineplanet, Tambo+, Starbucks, Starbucks y Cabify, entre muchas otras."
                ),
            ),
            ("movements",),
        ),
        "spend_es": (
            "composed",
            (
                (
                    "Este mes gastaste S/\xa02,091.60 en Primax, que es S/\xa01,142.10 más que en el mes "
                    "anterior, cuando gastaste S/\xa0949.50."
                ),
                "En el período actual tienes 12 compras registradas en ese comercio.",
            ),
            ("movements",),
        ),
        "spend_pt": (
            "repaired",
            (
                (
                    "Neste mês você gastou R$\xa01.456,06 no Ipiranga com 5 compras, comparado a "
                    "R$\xa01.601,37 no mês passado. Você gastou R$\xa0145,31 a menos."
                ),
            ),
            (),
        ),
        "visa_es": (
            "repaired",
            (
                (
                    "Tu tarjeta terminada en 9454 tuvo 25 movimientos en el período del 1 al 20 de "
                    "septiembre. Entre ellos están compras en Plaza Vea, Primax y Cabify."
                ),
            ),
            ("movements",),
        ),
    },
}


@pytest.mark.parametrize("profile", profiles(), ids=lambda row: row.key)
@pytest.mark.parametrize("name", list(DEMO))
def test_every_declared_model_replays_its_recorded_demo_turn(
    aws: Aws, name: str, profile: ModelProfile
) -> None:
    recording = json.loads((RECORDINGS / profile.key / f"{name}.json").read_text())
    model = FakeConverse([exchange["response"] for exchange in recording["exchanges"]])
    message = demo_turn_message(aws, name)

    result = run_turn(
        message, [], NOW, profile=profile, clients=model.client, policies=policy_index(DEMO[name][0])
    )

    source, says, shown = EXPECTED[profile.key][name]
    assert tuple(part["text"] for part in result.reply.parts if part["type"] == "say") == says
    assert (
        tuple(part.get("view") or part.get("ask") for part in result.reply.parts if part["type"] != "say")
        == shown
    )
    assert result.reply.source == source
    recorded = [exchange["request"] for exchange in recording["exchanges"]]
    assert normalized(model.requests) == normalized(recorded)


def normalized(requests: list[dict[str, Any]]) -> Any:
    return json.loads(json.dumps(requests, ensure_ascii=False, default=str))
