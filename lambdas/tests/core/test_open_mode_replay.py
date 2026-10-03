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
                    "Tu aclaración CLR-2026-182061 sobre el cargo de S/\xa0127.80 en Primax está actualmente "
                    "en revisión, con el proceso iniciado hoy."
                ),
                (
                    "El banco revisa tu caso y responde dentro de 10 días hábiles. El resultado depende del "
                    "proceso de revisión en curso."
                ),
            ),
            ("case",),
        ),
        "case_pt": (
            "composed",
            (
                (
                    "Sua contestação CLR-2026-862021, referente a uma cobrança de R$\xa0197,26 no Pão de "
                    "Açúcar no seu cartão final 6400, está em análise desde hoje. O banco tem 8 dias úteis "
                    "para concluir a análise."
                ),
            ),
            ("case",),
        ),
        "charge_pt": (
            "repaired",
            (
                (
                    "Há 13 movimentações do Ipiranga no período de 22 de agosto a 20 de setembro. Qual delas "
                    "você quer saber mais? Me informe a data ou o valor para eu identificar a certa."
                ),
            ),
            ("movements",),
        ),
        "movements_es": (
            "composed",
            (
                (
                    "Encontré 216 movimientos del 20 de julio al 20 de septiembre, en tus 3 tarjetas. Los "
                    "más recientes incluyen un cargo en Cineplanet con tu tarjeta terminada en 9739, uno en "
                    "Tambo+ y otro en Starbucks."
                ),
            ),
            ("movements",),
        ),
        "spend_es": (
            "composed",
            (
                (
                    "Este mes gastaste S/\xa02,091.60 en Primax, S/\xa01,142.10 más que el mes pasado, "
                    "cuando el total fue S/\xa0949.50."
                ),
                "En total hay 18 movimientos en el período del 1 de agosto al 20 de septiembre.",
            ),
            ("movements",),
        ),
        "spend_pt": (
            "composed",
            (
                (
                    "Este mês você gastou R$\xa01.456,06 no Ipiranga, considerando 5 compras, incluindo uma "
                    "cobrança pendente de R$\xa0301,00. No mês passado, o total foi R$\xa01.601,37, então "
                    "você gastou R$\xa0145,31 a menos este mês."
                ),
            ),
            ("movements",),
        ),
        "visa_es": (
            "composed",
            (
                (
                    "Tienes 2 tarjetas de crédito Visa activas. ¿Cuál te interesa? Tu tarjeta terminada en "
                    "9454 tiene 25 movimientos este mes, y tu tarjeta terminada en 3229 tiene 19 "
                    "movimientos."
                ),
            ),
            ("which_one",),
        ),
    },
    "haiku-4-5": {
        "cards_pt": (
            "composed",
            ("Você tem 2 cartões de crédito e 1 cartão de débito. Aqui estão todos com seu status atual.",),
            ("cards",),
        ),
        "case_es": (
            "composed",
            (
                (
                    "Tu caso CLR-2026-182061 está en revisión. El banco revisa tu aclaración y te responde "
                    "dentro de 10 días hábiles."
                ),
            ),
            ("case",),
        ),
        "case_pt": (
            "composed",
            (
                (
                    "Seu caso CLR-2026-862021 está em análise desde hoje. O banco analisa a contestação e "
                    "responde dentro de 8 dias úteis."
                ),
            ),
            ("case",),
        ),
        "charge_pt": (
            "composed",
            (
                (
                    "A Ipiranga é um lugar de abastecimento onde você faz compras regulares. Você tem 33 "
                    "compras lá em nossos registros, com valor típico de R$\xa0238,46."
                ),
                (
                    "Você tem compras recentes no Ipiranga em nossas bases de dados. Qual delas você "
                    "gostaria de conferir? Ou, se preferir, posso ver detalhes sobre uma compra específica "
                    "com a data e o valor que você mencionar."
                ),
            ),
            ("history",),
        ),
        "movements_es": (
            "repaired",
            (
                (
                    "En los últimos meses tienes 212 movimientos registradas. Las más recientes incluyen una "
                    "compra en Cineplanet en tienda, una en Tambo+ en tienda, una en Starbucks en tienda, "
                    "otra en Starbucks en tienda y un viaje con Cabify en la app."
                ),
            ),
            ("movements",),
        ),
        "spend_es": (
            "composed",
            (
                (
                    "Este mes gastaste S/\xa02,091.60 en Primax, mientras que el mes pasado fueron "
                    "S/\xa0949.50. Esto significa que gastaste S/\xa01,142.10 más que el mes anterior."
                ),
            ),
            ("movements",),
        ),
        "spend_pt": (
            "composed",
            (
                (
                    "Este mês no Ipiranga você gastou R$\xa01.456,06, que é R$\xa0145,31 a menos do que no "
                    "mês passado, quando o total foi R$\xa01.601,37."
                ),
            ),
            (),
        ),
        "visa_es": (
            "repaired",
            (
                (
                    "Tienes 25 movimientos en tu tarjeta terminada en 9454 en el período del 1 al 20 de "
                    "septiembre. Aquí ves los últimos: una compra rechazada en Plaza Vea, un cargo pendiente "
                    "de Primax en Trujillo, y cargos aprobados en transporte y comida."
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
