import json
from typing import Any

import pytest

from clara_testing.converse import FakeConverse
from core.turn import run_turn
from demo import DEMO, NOW, RECORDINGS, demo_turn_message, policy_index
from harness import Aws

EXPECTED = {
    "case_es": (
        "Tu aclaración CLR-2026-182061 sobre el cobro de Primax por S/\xa0127.80 está "
        "actualmente en revisión desde hoy.",
        "El banco tiene hasta 10 días hábiles para completar la revisión y darte una "
        "respuesta. No puedo prometerte una fecha exacta de devolución, ya que eso "
        "depende del resultado de ese proceso.",
    ),
    "case_pt": (
        "Seu caso CLR-2026-862021, referente a uma cobrança de R$\xa0197,26 em Pão de "
        "Açúcar no seu cartão final 6400, está em análise desde hoje.",
        "O banco tem até 8 dias úteis para concluir a análise da contestação. Não é "
        "possível adiantar uma data de resolução, pois depende do resultado da revisão "
        "em andamento.",
    ),
    "spend_es": (
        "Este mes en Primax llevas S/\xa02,091.60, comparado con S/\xa0949.50 el mes pasado. "
        "Eso es S/\xa01,142.10 más que el mes anterior.",
    ),
    "spend_pt": (
        "Este mês você gastou R$\xa01.456,06 no Ipiranga, contra R$\xa01.601,37 no mês "
        "passado, ou seja, menos R$\xa0145,31.",
        "Vale lembrar que este mês ainda não terminou, então o valor pode aumentar até o final do período.",
    ),
}


@pytest.mark.parametrize("name", list(DEMO))
def test_a_recorded_demo_turn_replays_to_the_same_answer_and_the_same_requests(aws: Aws, name: str) -> None:
    recording = json.loads((RECORDINGS / f"{name}.json").read_text())
    model = FakeConverse([exchange["response"] for exchange in recording["exchanges"]])

    result = run_turn(
        demo_turn_message(aws, name), [], NOW, clients=model.client, policies=policy_index(DEMO[name][0])
    )

    assert tuple(part["text"] for part in result.reply.parts) == EXPECTED[name]
    assert result.reply.source == "composed"
    assert normalized(model.requests) == normalized(
        [exchange["request"] for exchange in recording["exchanges"]]
    )


def normalized(requests: list[dict[str, Any]]) -> Any:
    return json.loads(json.dumps(requests, ensure_ascii=False, default=str))
