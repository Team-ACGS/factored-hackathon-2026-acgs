import json
from typing import Any

import pytest

from clara_testing.converse import FakeConverse
from core.graphs.profiles import ModelProfile, profiles
from core.turn import run_turn
from demo import DEMO, NOW, RECORDINGS, demo_turn_message, policy_index
from harness import Aws

EXPECTED: dict[str, dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]]] = {
    "sonnet-4-6": {
        "cards_pt": (
            "composed",
            (
                (
                    "Você tem 3 cartões: 2 cartões de crédito e 1 cartão de débito. Seu cartão final 2338 e "
                    "seu cartão final 6913 são de crédito, e seu cartão final 3530 é de débito. Todos estão "
                    "ativos."
                ),
            ),
            ("cards",),
        ),
        "case_es": (
            "composed",
            (
                (
                    "Tu aclaración CLR-2026-182061 sobre el cargo de S/\xa0127.80 en Primax está en revisión "
                    "desde hoy."
                ),
                "El banco revisa tu aclaración y responde en un plazo de 10 días hábiles.",
            ),
            ("case",),
        ),
        "case_pt": (
            "composed",
            (
                (
                    "Sua contestação CLR-2026-862021, referente à cobrança de R$\xa0197,26 em Pão de Açúcar, "
                    "está em análise desde hoje."
                ),
                "O banco analisa a contestação em até 8 dias úteis após o início da análise.",
            ),
            ("case",),
        ),
        "charge_pt": (
            "repaired",
            (
                (
                    "Há 13 movimentações de Ipiranga no período de 22 de agosto a 20 de setembro. Sobre qual "
                    "delas você quer saber mais? Me informe a data ou o valor para eu identificar a certa."
                ),
            ),
            ("movements",),
        ),
        "movements_es": (
            "composed",
            (
                (
                    "Encontré 216 movimientos en ese período. Los más recientes incluyen un cargo en "
                    "Cineplanet ayer a las 20:26, uno en Tambo+ ayer a las 15:21 y compras en Starbucks y "
                    "Starbucks ayer a las 10:11."
                ),
            ),
            ("movements",),
        ),
        "spend_es": (
            "composed",
            (
                (
                    "Este mes llevas S/\xa02,091.60 en Primax, S/\xa01,142.10 más que el mes pasado, cuando "
                    "gastaste S/\xa0949.50. En total tienes 18 movimientos en el período del 1 de agosto al "
                    "20 de septiembre."
                ),
            ),
            ("movements",),
        ),
        "spend_pt": (
            "composed",
            (
                (
                    "Este mês você gastou R$\xa01.456,06 no Ipiranga, com 5 compras. No mês passado o total "
                    "foi R$\xa01.601,37."
                ),
                "Você gastou R$\xa0145,31 a menos do que no mês passado.",
            ),
            ("movements",),
        ),
        "visa_es": (
            "composed",
            (
                (
                    "Tienes 61 movimientos este mes en tus tarjetas. Noto que tienes 2 tarjetas de crédito: "
                    "tu tarjeta terminada en 9454 y tu tarjeta terminada en 3229. ¿Sobre cuál quieres ver "
                    "los movimientos?"
                ),
            ),
            ("which_one",),
        ),
    },
    "haiku-4-5": {
        "cards_pt": (
            "composed",
            (
                (
                    "Você tem 3 cartões: 2 cartões de crédito e 1 cartão de débito. Seus cartões de crédito "
                    "são final 2338 e final 6913, e o de débito é final 3530. Todos estão ativo."
                ),
            ),
            ("cards",),
        ),
        "case_es": (
            "composed",
            (
                (
                    "Tu aclaración CLR-2026-182061 está en revisión. El banco te responde dentro de 10 días "
                    "hábiles."
                ),
            ),
            ("case",),
        ),
        "case_pt": (
            "composed",
            (
                (
                    "Sua contestação CLR-2026-862021 está em análise. O banco analisa a sua contestação e "
                    "responde dentro 8 dias úteis."
                ),
            ),
            ("case",),
        ),
        "charge_pt": (
            "composed",
            (
                (
                    "São cobranças de combustível na Ipiranga, um posto de gasolina. Você tem 33 compras "
                    "nesse lugar de 21 de junho a 20 de setembro, com valor típico de R$\xa0238,46."
                ),
                (
                    "As mais recentes foram em 18 de setembro às 20:23, em 16 de setembro às 21:35 e em 16 "
                    "de setembro às 14:43. Quer ver mais detalhes sobre alguma delas?"
                ),
            ),
            ("history",),
        ),
        "movements_es": (
            "repaired",
            (
                (
                    "Tienes 216 movimientos en este período. Las más recientes incluyen compras en "
                    "Cineplanet, Tambo+, Starbucks y Cabify."
                ),
            ),
            ("movements",),
        ),
        "spend_es": (
            "composed",
            (
                (
                    "Este mes gastaste S/\xa02,091.60 en Primax, S/\xa01,142.10 más que el mes pasado cuando "
                    "gastaste S/\xa0949.50."
                ),
            ),
            ("movements",),
        ),
        "spend_pt": (
            "composed",
            (
                (
                    "Você gastou R$\xa0145,31 a menos no Ipiranga este mês em relação ao mês passado. Este "
                    "mês foram 5 compras, totalizando R$\xa01.456,06."
                ),
            ),
            ("movements",),
        ),
        "visa_es": (
            "repaired",
            (
                (
                    "Tu tarjeta terminada en 9454 tuvo 25 movimientos del 1 al 20 de septiembre. Aquí están "
                    "los más recientes: una compra en Plaza Vea que fue rechazada, una en Primax que está "
                    "pendiente, y otras aprobadas en Cabify y Rappi."
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
