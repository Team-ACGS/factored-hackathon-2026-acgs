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
        "case_es": (
            "composed",
            (
                "Tu aclaración CLR-2026-182061 sobre el cargo de S/\xa0127.80 en Primax con tu "
                "tarjeta terminada en 4141 está actualmente en revisión desde hoy.",
                "Según el proceso del banco, la revisión toma hasta 10 días hábiles. No "
                "puedo decirte el resultado ni comprometer una fecha concreta, pero el banco "
                "está trabajando en tu caso.",
            ),
        ),
        "case_pt": (
            "composed",
            (
                "Seu caso CLR-2026-862021, referente a uma cobrança de R$\xa0197,26 em Pão de "
                "Açúcar no seu cartão final 6400, está em análise desde hoje.",
                "O processo de revisão pode levar até 8 dias úteis a partir do início da "
                "análise. Não consigo informar um valor de retorno nem uma data exata de "
                "conclusão, pois isso depende do andamento da revisão pelo banco.",
            ),
        ),
        "spend_es": (
            "composed",
            (
                "Este mes has gastado S/\xa02,091.60 en Primax, considerando compras aprobadas "
                "y pendientes. El mes pasado el total fue S/\xa0949.50.",
                "Eso representa S/\xa01,142.10 más que el mes pasado.",
            ),
        ),
        "spend_pt": (
            "composed",
            (
                "Este mês você gastou R$\xa01.456,06 no Ipiranga, enquanto no mês passado o "
                "total foi R$\xa01.601,37. Ou seja, você gastou R$\xa0145,31 menos em comparação "
                "com o mês anterior.",
            ),
        ),
    },
    "haiku-4-5": {
        "case_es": (
            "composed",
            (
                "Tu caso CLR-2026-182061 está en revisión desde hoy. El banco te responde "
                "sobre tu aclaración dentro 10 días hábiles.",
                "No puedo decirte cuándo llegará el dinero; eso depende de cómo el banco "
                "resuelva tu revisión. Lo que sí sé es el plazo para que te respondan.",
            ),
        ),
        "case_pt": (
            "composed",
            (
                "Seu caso CLR-2026-862021 está em análise agora. O banco analisa a sua "
                "contestação dentro 8 dias úteis. Após a análise ser concluída, você saberá "
                "o resultado, mas não posso antecipar prazos para o dinheiro além do período "
                "de revisão.",
            ),
        ),
        "spend_es": (
            "repaired",
            (
                "Este mes gastaste S/\xa02,091.60 en Primax, mientras que el mes pasado fueron "
                "S/\xa0949.50. Así que este mes gastaste S/\xa01,142.10 más que en el período "
                "anterior.",
            ),
        ),
        "spend_pt": (
            "composed",
            (
                "Este mês você gastou R$\xa01.456,06 no Ipiranga, menos do que mês passado. A "
                "diferença é R$\xa0145,31.",
            ),
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

    source, says = EXPECTED[profile.key][name]
    assert tuple(part["text"] for part in result.reply.parts) == says
    assert result.reply.source == source
    recorded = [exchange["request"] for exchange in recording["exchanges"]]
    assert normalized(model.requests) == normalized(recorded)


def normalized(requests: list[dict[str, Any]]) -> Any:
    return json.loads(json.dumps(requests, ensure_ascii=False, default=str))
