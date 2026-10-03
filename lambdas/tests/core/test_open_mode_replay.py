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
            ("Você tem 3 cartões, sendo 2 cartões de crédito e 1 cartão de débito. Todos estão ativos.",),
            ("cards",),
        ),
        "case_es": (
            "composed",
            (
                (
                    "Tu aclaración CLR-2026-182061 sobre un cargo de S/\xa0127.80 en Primax con tu tarjeta "
                    "terminada en 4141 está actualmente en revisión desde hoy."
                ),
                "El banco revisa la aclaración y responde dentro de 10 días hábiles.",
            ),
            ("case",),
        ),
        "case_pt": (
            "composed",
            (
                (
                    "Sua contestação CLR-2026-862021, referente à cobrança de R$\xa0197,26 em Pão de Açúcar "
                    "no seu cartão final 6400, está com o estágio em análise desde hoje."
                ),
                "O banco analisa a contestação em até 8 dias úteis.",
            ),
            ("case",),
        ),
        "charge_pt": (
            "repaired",
            (
                (
                    "Encontrei 13 movimentações de Ipiranga de 22 de agosto a 20 de setembro. A mais recente "
                    "foi em 18 de setembro às 20:23 no valor de R$\xa0144,77 com status pendente, feita na "
                    "loja em Curitiba. Você quer saber mais sobre alguma em específico? Me informe a data ou "
                    "o valor."
                ),
            ),
            ("movements",),
        ),
        "movements_es": (
            "composed",
            (
                (
                    "Encontré 216 movimientos en ese período. Los más recientes incluyen un cargo en "
                    "Cineplanet con tu tarjeta terminada en 9739, uno en Tambo+ con tu tarjeta terminada en "
                    "9739, y compras en Starbucks con tu tarjeta terminada en 6720 y tu tarjeta terminada en "
                    "5073."
                ),
            ),
            ("movements",),
        ),
        "spend_es": (
            "composed",
            (
                (
                    "Este mes llevas S/\xa02,091.60 en Primax, S/\xa01,142.10 más que el mes pasado cuando "
                    "gastaste S/\xa0949.50."
                ),
                "En total hay 18 movimientos en el período del 1 de agosto al 20 de septiembre.",
            ),
            ("movements",),
        ),
        "spend_pt": (
            "composed",
            (
                (
                    "Este mês você gastou R$\xa01.456,06 no Ipiranga, um valor menos em R$\xa0145,31 "
                    "comparado com o mês passado, quando o total foi R$\xa01.601,37."
                ),
                "Ao todo foram 14 movimentações no período de 1 de agosto a 20 de setembro.",
            ),
            ("movements",),
        ),
        "visa_es": (
            "composed",
            (
                (
                    'Tienes 61 movimientos este mes en tus tarjetas, pero noto que mencionas tu "Visa": '
                    "cuéntame, ¿te refieres a tu tarjeta de crédito terminada en 9454 o a tu tarjeta de "
                    "crédito terminada en 3229? También tienes una tarjeta de débito terminada en 1898 si "
                    "fuera esa."
                ),
            ),
            ("which_one",),
        ),
    },
    "haiku-4-5": {
        "cards_pt": (
            "composed",
            ("Você tem 3 cartões: 2 cartões de crédito e 1 cartão de débito. Todos estão ativos.",),
            ("cards",),
        ),
        "case_es": (
            "composed",
            (
                (
                    "Tu caso CLR-2026-182061 sobre el cargo de S/\xa0127.80 en Primax está en revisión. El "
                    "banco revisa tu aclaración y te responde dentro de 10 días hábiles."
                ),
            ),
            ("case",),
        ),
        "case_pt": (
            "composed",
            (
                (
                    "Sua contestação do débito de R$\xa0197,26 em Pão de Açúcar no seu cartão final 6400 "
                    "está em análise. O banco analisa a contestação e responde dentro do prazo de 8 dias "
                    "úteis."
                ),
            ),
            ("case",),
        ),
        "charge_pt": (
            "repaired",
            (
                (
                    "São cobranças no Ipiranga, um posto de combustível. Você tem 33 compras dessas compras "
                    "nos últimos meses, com um valor típico de R$\xa0238,46. Qual é a data ou o valor da "
                    "cobrança que você quer entender?"
                ),
            ),
            ("movements",),
        ),
        "movements_es": (
            "repaired",
            (
                (
                    "En ese período tienes 216 movimientos. Aquí están las más recientes: Cineplanet por "
                    "S/\xa055.90, Tambo+ por S/\xa015.60, Starbucks por S/\xa014.10, Starbucks por "
                    "S/\xa027.90 y Cabify por S/\xa041.70."
                ),
            ),
            ("movements",),
        ),
        "spend_es": (
            "composed",
            (
                (
                    "Este mes gastaste S/\xa02,091.60 en Primax, mientras que el mes pasado gastaste "
                    "S/\xa0949.50, es decir S/\xa01,142.10 más."
                ),
                "He encontrado 18 movimientos en Primax durante este período.",
            ),
            ("movements",),
        ),
        "spend_pt": (
            "composed",
            (
                (
                    "Este mês você gastou R$\xa01.456,06 no Ipiranga, enquanto no mês passado gastou "
                    "R$\xa01.601,37. Você gastou R$\xa0145,31 a menos este mês."
                ),
                "Você fez 5 compras neste período.",
            ),
            ("movements",),
        ),
        "visa_es": (
            "repaired",
            (
                (
                    "Tu tarjeta terminada en 9454 tiene 25 movimientos del 1 al 20 de septiembre. Aquí ves "
                    "los más recientes: una compra rechazada el 17 de septiembre a las 20:20 en Plaza Vea, "
                    "un pago pendiente el 17 de septiembre a las 17:49 en Primax, y compras aprobadas en "
                    "Cabify y Rappi."
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
