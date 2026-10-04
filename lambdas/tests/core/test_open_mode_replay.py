import json
from datetime import timedelta
from typing import Any

import pytest

from clara_testing.converse import FakeConverse
from core.graphs.profiles import ModelProfile, profiles
from core.messaging import Message, customer_message
from core.turn import Turn, run_turn
from demo import (
    DEMO,
    FLAGGED,
    FREE,
    KEPT,
    NOT_ME_FREE,
    NOW,
    RECORDINGS,
    base,
    demo_id,
    demo_turn,
    forget,
    kept,
    planted_charge,
    policy_index,
    quiet_choice,
    tap,
)
from harness import Aws

ABSTAINED = ("unblock_es", "unblock_pt", "case_es", "case_pt")
LOST = {"es": "me robaron la tarjeta", "pt": "roubaram o meu cartão"}

EXPECTED: dict[str, dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]]] = {
    "sonnet-4-6": {
        "spend_es": (
            "composed",
            (
                (
                    "Este mes gastaste S/\xa02,091.60 en Primax, versus S/\xa0949.50 el mes pasado. Eso es "
                    "S/\xa01,142.10 más que el mes pasado."
                ),
            ),
            ("movements",),
        ),
        "case_es": (
            "composed",
            (
                (
                    "Tu aclaración CLR-2026-182061 sobre el cargo en Primax está en revisión desde hoy. El "
                    "banco revisa tu aclaración en 10 días hábiles."
                ),
            ),
            ("handoff", "talk_to_person"),
        ),
        "spend_pt": (
            "composed",
            (
                (
                    "Este mês você gastou R$\xa01.456,06 no Ipiranga, enquanto no mês passado foram "
                    "R$\xa01.601,37. Você gastou R$\xa0145,31 a menos do que no mês passado."
                ),
            ),
            ("movements",),
        ),
        "case_pt": (
            "composed",
            (
                (
                    "Sua contestação CLR-2026-862021 está em análise, referente à cobrança de R$\xa0197,26 "
                    "em Pão de Açúcar no seu cartão final 6400. O banco analisa a contestação em 8 dias "
                    "úteis."
                ),
            ),
            ("handoff", "talk_to_person"),
        ),
        "movements_es": (
            "repaired",
            (
                (
                    "Encontré 216 movimientos del 20 de julio al 20 de septiembre. Los más recientes son en "
                    "Cineplanet por S/\xa055.90 (ayer a las 20:26), en Tambo+ por S/\xa015.60 (ayer a las "
                    "15:21), en Starbucks por S/\xa014.10 (ayer a las 10:11), en Starbucks por S/\xa027.90 "
                    "(ayer a las 08:13), y en Cabify por S/\xa041.70 (el 18 de septiembre a las 20:45)."
                ),
            ),
            ("movements",),
        ),
        "visa_es": (
            "composed",
            (
                (
                    "Tienes 61 movimientos este mes. Nota que el banco no guarda información de red (Visa, "
                    "Mastercard), así que te muestro tus tarjetas de crédito y débito sin distinguir la "
                    "marca."
                ),
            ),
            ("movements",),
        ),
        "cards_pt": (
            "composed",
            (
                (
                    "Você tem 2 cartões de crédito e 1 cartão de débito. Seu cartão final 2338 e seu cartão "
                    "final 6913 são de crédito, ambos ativos. Seu cartão final 3530 é de débito e também "
                    "está ativo."
                ),
            ),
            ("cards",),
        ),
        "charge_pt": (
            "composed",
            (
                (
                    "Encontrei 13 movimentações de Ipiranga no seu histórico. Sobre qual delas você quer "
                    "saber mais? Me diga a data ou o valor para eu identificar a certa."
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
            ("movements", "which_one"),
        ),
        "unrecognized_pt": (
            "composed",
            (
                (
                    "Estas são suas movimentações mais recentes. Qual é a que você não reconhece? Se não "
                    "estiver entre elas, me diga a data ou o valor."
                ),
            ),
            ("movements", "which_one"),
        ),
        "cancel_es": (
            "composed",
            (
                (
                    "Si bloqueas una tarjeta, los cobros recurrentes que se intenten con ella son "
                    "rechazados; el bloqueo no cancela por sí mismo ninguna suscripción ni ningún servicio."
                ),
                (
                    "Tienes Movistar en tu tarjeta terminada en 5529 y Netflix en tu tarjeta terminada en "
                    "1211. Si bloqueas alguna de esas tarjetas, el comercio decide qué hace con el pago "
                    "rechazado; puedes actualizar la forma de pago cuando recibas una tarjeta nueva, o "
                    "cancelar la suscripción directamente con el comercio."
                ),
            ),
            ("movements",),
        ),
        "cancel_again_es": (
            "composed",
            (
                (
                    "Si bloqueas una tarjeta, los cobros recurrentes que intenten hacerse con esa tarjeta "
                    "son rechazados, pero el bloqueo no cancela ninguna suscripción ni ningún servicio por "
                    "sí mismo."
                ),
                (
                    "Tus suscripciones van por tarjetas distintas: Movistar está en tu tarjeta terminada en "
                    "4071 y Netflix en tu tarjeta terminada en 9558. Si bloqueas solo una de ellas, la otra "
                    "sigue cobrando sin cambios."
                ),
                (
                    "Cuando un pago es rechazado, es el comercio quien decide qué hacer con ese cobro; para "
                    "que deje de intentarlo, necesitas cancelar la suscripción directamente con ellos."
                ),
            ),
            ("movements",),
        ),
        "that_one_es": (
            "composed",
            (
                (
                    "El cargo en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30, por internet. Lo que "
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
                    "Para abrir una aclaración sobre el cargo en TEMU.COM 2979 por S/\xa0363.10, puedes "
                    "hacerlo aquí en la app con Clara o llamando al +51 1 600 2000. Una vez abierta, el "
                    "banco revisa tu aclaración en 10 días hábiles."
                ),
            ),
            (),
        ),
        "topic_es": (
            "composed",
            (
                (
                    "Tu cargo en Tambo+ por S/\xa020.50 fue ayer a las 10:16, en tienda en Trujillo. Antes "
                    "hiciste 36 compras ahí y lo típico es S/\xa030.80."
                ),
            ),
            ("charge", "recognize_charge"),
        ),
        "topic_pt": (
            "composed",
            (
                (
                    "Sua cobrança em Starbucks de R$\xa021,60 foi ontem às 20:28, na loja, em São Paulo. "
                    "Você já fez 28 compras lá antes, com valor típico de R$\xa032,67."
                ),
            ),
            ("charge", "recognize_charge"),
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
        "flagged_es": (
            "composed",
            (
                (
                    "Tu cargo en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30, por internet. Lo que "
                    "notó el banco: el sistema de alertas del banco emitió una alerta y es tu primera compra "
                    "en este comercio."
                ),
            ),
            ("charge", "was_it_you"),
        ),
        "flagged_pt": (
            "composed",
            (
                (
                    "A cobrança de R$\xa0522,83 em TEMU.COM 2979 foi hoje às 13:30, pela internet. É a sua "
                    "primeira compra nesse estabelecimento e o que o banco notou: o sistema de alertas do "
                    "banco emitiu um alerta e é a sua primeira compra neste estabelecimento."
                ),
            ),
            ("charge", "was_it_you"),
        ),
        "unblock_es": (
            "composed",
            (
                (
                    "Desbloquear una tarjeta es algo que realiza una persona del banco. Puedo contarte que "
                    "tus tarjetas están activas en este momento, pero para gestionar un desbloqueo "
                    "necesitarás hablar con el equipo de atención."
                ),
            ),
            ("handoff", "talk_to_person"),
        ),
        "unblock_pt": (
            "composed",
            (
                (
                    "Desbloquear um cartão é algo que só um atendente do banco pode fazer. Posso verificar o "
                    "status dos seus cartões enquanto isso."
                ),
            ),
            ("handoff", "talk_to_person"),
        ),
        "ten_days_pt": (
            "composed",
            (
                (
                    "Se o prazo terminar sem resposta, você pode escrever para a Ouvidoria do LATAM Bank em "
                    "ouvidoria.br@latambank.example, que responde em 10 dias úteis. Se ainda assim não ficar "
                    "satisfeita, o passo seguinte fora do banco é o Procon."
                ),
            ),
            (),
        ),
        "about_you_pt": (
            "say_key",
            (
                "Você é Ana, cliente do LATAM Bank (Brasil).",
                (
                    "Você tem 3 cartões: o de crédito final 0470, o de crédito final 9210 e o de débito "
                    "final 6341."
                ),
            ),
            (),
        ),
        "document_pt": (
            "composed",
            (
                (
                    "Não tenho acesso ao seu documento nem ao seu endereço. Posso ajudar você com seus "
                    "cartões, cobranças, movimentações, contestações e processos do banco."
                ),
            ),
            (),
        ),
        "cannot_tell_pt": (
            "composed",
            (
                (
                    "Não tenho acesso ao seu documento, endereço, telefone, número completo do cartão, CVV "
                    "nem a nenhum outro dado pessoal sensível. Posso te ajudar com seus cartões, cobranças, "
                    "movimentações e processos do banco."
                ),
            ),
            (),
        ),
        "spanish_pt": (
            "repaired",
            ("Você tem 2 cartões de crédito e ambas estão ativas.",),
            ("cards",),
        ),
        "largest_pt": (
            "composed",
            (
                (
                    "Sua maior compra de 21 de junho a 20 de setembro foi em LATAM Airlines, de "
                    "R$\xa01.852,15, em 6 de julho às 19:01."
                ),
            ),
            ("movement",),
        ),
        "rio_pt": (
            "composed",
            ("Não: 1 em Belo Horizonte e 1 no Rio de Janeiro.",),
            ("movements",),
        ),
        "rio_again_pt": (
            "composed",
            ("Não: 3 em Curitiba.",),
            ("movements",),
        ),
        "ten_days_again_pt": (
            "composed",
            (
                (
                    "Se o prazo terminar sem resposta, você pode escrever para a Ouvidoria do LATAM Bank "
                    "pelo e-mail ouvidoria.br@latambank.example, que responde em 10 dias úteis. Se ainda "
                    "assim não estiver satisfeita, o passo seguinte fora do banco é o Procon."
                ),
            ),
            (),
        ),
        "unrecognized_es_tap": (
            "composed",
            (
                (
                    "Tu cargo en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30, por internet. Lo que "
                    "notó el banco: el sistema de alertas del banco emitió una alerta y es tu primera compra "
                    "en este comercio."
                ),
            ),
            ("charge", "was_it_you"),
        ),
        "unrecognized_pt_tap": (
            "composed",
            (
                (
                    "A cobrança em TEMU.COM 2979 de R$\xa0522,83 foi hoje às 13:30, pela internet. É sua "
                    "primeira compra nesse estabelecimento e o que o banco notou: o sistema de alertas do "
                    "banco emitiu um alerta e é a sua primeira compra neste estabelecimento."
                ),
            ),
            ("charge", "was_it_you"),
        ),
        "unrecognized_es_pick": (
            "composed",
            (
                (
                    "Tu cargo en Inkafarma por S/\xa089.90 fue ayer a las 20:15, en tienda, en Cusco. Antes "
                    "hiciste 18 compras ahí y lo típico es S/\xa096.85."
                ),
            ),
            ("charge", "recognize_charge"),
        ),
        "unrecognized_es_kept": (
            "composed",
            (
                (
                    "Antes de este cargo, tienes 18 compras en Inkafarma, y la última fue ayer, con un monto "
                    "típico de S/\xa096.85. El banco no marcó ninguna alerta en esta transacción."
                ),
            ),
            ("charge", "recognize_charge"),
        ),
        "unrecognized_es_pick_yes": (
            "story",
            ("Gracias, lo anoto: reconoces este cargo y no volveré a preguntarte por él.",),
            (),
        ),
        "unrecognized_es_free": (
            "story",
            (
                (
                    "Gracias, lo anoto: reconoces este cargo, «claro, esa la hice yo en el grifo», y no "
                    "volveré a preguntarte por él."
                ),
            ),
            (),
        ),
        "unrecognized_pt_pick": (
            "composed",
            (
                (
                    "A cobrança em Drogasil de R$\xa046,71 foi ontem às 19:22, na loja, em São Paulo. Você "
                    "já fez 19 compras nessa loja, com valor típico de R$\xa0223,94."
                ),
            ),
            ("charge", "recognize_charge"),
        ),
        "unrecognized_pt_pick_yes": (
            "story",
            ("Obrigada! Anotei que você reconhece esta cobrança e não vou perguntar sobre ela novamente.",),
            (),
        ),
        "unrecognized_pt_free": (
            "story",
            (
                (
                    "Obrigada! Anotei que você reconhece esta cobrança e registrei sua observação “foi eu "
                    "sim, era o cinema com a família”, então não vou perguntar sobre ela novamente."
                ),
            ),
            (),
        ),
        "flagged_es_why": (
            "story",
            (
                (
                    "Te pregunto por tu compra en TEMU.COM 2979 porque el banco notó esto: el sistema de "
                    "alertas del banco emitió una alerta y es tu primera compra en este comercio."
                ),
            ),
            ("charge", "was_it_you"),
        ),
        "flagged_es_block": (
            "story",
            (
                "Listo: tu tarjeta terminada en 3302 quedó bloqueada, y lo confirmé en tu cuenta.",
                (
                    "Abrí el caso CLR-2026-385822 con lo que revisamos. Te contactará una persona del banco, "
                    "y esto es lo que ya sabe."
                ),
            ),
            ("case",),
        ),
        "flagged_pt_why": (
            "story",
            (
                (
                    "Estou perguntando sobre sua compra em TEMU.COM 2979 porque o banco notou o seguinte: o "
                    "sistema de alertas do banco emitiu um alerta e é a sua primeira compra neste "
                    "estabelecimento."
                ),
            ),
            ("charge", "was_it_you"),
        ),
        "flagged_pt_block": (
            "story",
            (
                "Pronto: seu cartão final 8602 foi bloqueado, e eu confirmei isso na sua conta.",
                (
                    "Abri o caso CLR-2026-385822 com o que verificamos. Uma pessoa do banco vai entrar em "
                    "contato, e isto é o que ela já sabe."
                ),
            ),
            ("case",),
        ),
        "unblock_es_yes": (
            "story",
            (
                (
                    "Abrí el caso CLR-2026-738532 con lo que revisamos. Te contactará una persona del banco, "
                    "y esto es lo que ya sabe."
                ),
            ),
            ("case",),
        ),
        "unblock_pt_yes": (
            "story",
            (
                (
                    "Abri o caso CLR-2026-738532 com o que verificamos. Uma pessoa do banco vai entrar em "
                    "contato, e isto é o que ela já sabe."
                ),
            ),
            ("case",),
        ),
        "case_es_yes": (
            "story",
            (
                (
                    "Abrí el caso CLR-2026-738532 con lo que revisamos. Te contactará una persona del banco, "
                    "y esto es lo que ya sabe."
                ),
            ),
            ("case",),
        ),
        "case_pt_yes": (
            "story",
            (
                (
                    "Abri o caso CLR-2026-738532 com o que verificamos. Uma pessoa do banco vai entrar em "
                    "contato, e isto é o que ela já sabe."
                ),
            ),
            ("case",),
        ),
        "topic_es_open": (
            "story",
            ("Abrí tu aclaración CLR-2026-217737; esto es lo que queda registrado.",),
            ("case",),
        ),
        "lost_es_block": (
            "story",
            (
                "Listo: tu tarjeta terminada en 7132 quedó bloqueada, y lo confirmé en tu cuenta.",
                (
                    "Abrí el caso CLR-2026-385822 con lo que revisamos. Te contactará una persona del banco, "
                    "y esto es lo que ya sabe."
                ),
            ),
            ("case",),
        ),
        "topic_pt_open": (
            "story",
            ("Abri sua contestação CLR-2026-217737; isto é o que fica registrado.",),
            ("case",),
        ),
        "lost_pt_block": (
            "story",
            (
                "Pronto: seu cartão final 9500 foi bloqueado, e eu confirmei isso na sua conta.",
                (
                    "Abri o caso CLR-2026-385822 com o que verificamos. Uma pessoa do banco vai entrar em "
                    "contato, e isto é o que ela já sabe."
                ),
            ),
            ("case",),
        ),
    },
    "haiku-4-5": {
        "spend_es": (
            "composed",
            (
                (
                    "Gastaste S/\xa01,142.10 más en Primax este mes que el pasado. Este mes llevabas "
                    "S/\xa02,091.60; el mes pasado fue S/\xa0949.50."
                ),
            ),
            ("movements",),
        ),
        "case_es": (
            "repaired",
            (
                (
                    "Tu aclaración CLR-2026-182061 está en revisión. El banco revisa tu aclaración en 10 "
                    "días hábiles."
                ),
            ),
            ("handoff", "talk_to_person"),
        ),
        "spend_pt": (
            "composed",
            (
                (
                    "Neste mês você gastou R$\xa01.456,06 no Ipiranga. Comparado com o mês passado, gastou "
                    "R$\xa0145,31 a menos."
                ),
            ),
            (),
        ),
        "case_pt": (
            "composed",
            (
                (
                    "Sua contestação CLR-2026-862021 está em análise. O banco analisa sua contestação dentro "
                    "do prazo de 8 dias úteis. Para saber mais sobre o resultado ou se tiver outras dúvidas, "
                    "você pode falar com uma pessoa no banco."
                ),
            ),
            ("handoff", "talk_to_person"),
        ),
        "movements_es": (
            "repaired",
            (
                (
                    "En los últimos meses hiciste 216 movimientos. Las más recientes fueron en Arequipa con "
                    "Cineplanet, Starbucks y Cabify, también en Trujillo con Tambo+. La mayoría están en "
                    "Arequipa, aunque también tienes movimientos en Trujillo, Cusco y Lima."
                ),
            ),
            ("movements",),
        ),
        "visa_es": (
            "repaired",
            (
                (
                    "Tu tarjeta terminada en 9454 tuvo 25 movimientos del 1 al 20 de septiembre. Los más "
                    "recientes incluyen una compra rechazada en Plaza Vea por S/\xa0334.30, una pendiente en "
                    "Primax por S/\xa0155.60, y compras aprobadas en Cabify y Rappi, más una rechazada en "
                    "Rappi."
                ),
            ),
            ("movements",),
        ),
        "cards_pt": (
            "composed",
            (
                (
                    "Você tem 2 cartões de crédito e 1 cartão de débito. Sua tarjeta final 2338 está ativo, "
                    "sua tarjeta final 6913 está ativo e seu cartão final 3530 está ativo."
                ),
            ),
            ("cards",),
        ),
        "charge_pt": (
            "composed",
            (
                (
                    "Você tem várias compras no Ipiranga. Como é um posto de combustível, essas cobranças "
                    "são por abastecimentos. Você fez 33 compras lá desde 23 de junho, com o valor típico de "
                    "R$\xa0238,46."
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
            ("movements", "which_one"),
        ),
        "unrecognized_pt": (
            "composed",
            (
                (
                    "Estes são seus movimentos mais recentes. Qual é o que você não reconhece? Se não "
                    "estiver entre eles, me diga a data ou o valor."
                ),
            ),
            ("movements", "which_one"),
        ),
        "cancel_es": (
            "composed",
            (
                (
                    "Si bloqueas tu tarjeta, los cargos recurrentes que uses en esa tarjeta serán "
                    "rechazados. El bloqueo no cancela automáticamente las suscripciones; el comercio decide "
                    "qué hace con un pago rechazado."
                ),
                (
                    "Tus suscripciones están en tu tarjeta terminada en 5529 (Movistar) y tu tarjeta "
                    "terminada en 1211 (Netflix). Si bloqueas cualquiera de ellas, necesitas actualizar la "
                    "forma de pago con esos servicios o cancelarlas directamente con ellos si ya no las "
                    "quieres."
                ),
            ),
            (),
        ),
        "cancel_again_es": (
            "repaired",
            (
                (
                    "No tengo información del banco sobre eso. Lo que sí puedo decirte es que tienes 2 "
                    "cargos recurrentes: Movistar en tu tarjeta terminada en 4071 y Netflix en tu tarjeta "
                    "terminada en 9558. Si cancelas una tarjeta, lo mejor es que hables con el banco sobre "
                    "cómo afectaría a esos cargos."
                ),
            ),
            (),
        ),
        "that_one_es": (
            "repaired",
            (
                (
                    "Tu compra en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30 por internet. Es tu "
                    "primera compra ahí. Lo que notó el banco: el sistema de alertas del banco emitió una "
                    "alerta y es tu primera compra en este comercio."
                ),
            ),
            ("charge",),
        ),
        "what_now_es": (
            "composed",
            (
                (
                    "El banco revisará esta compra por ti. Verificará lo que sucedió y, si determina que no "
                    "debería haberse aprobado, se revertirá el cargo de tu cuenta."
                ),
            ),
            ("charge",),
        ),
        "topic_es": (
            "repaired",
            (
                (
                    '["Entendido. Este cargo en Tambo+ por S/\xa020.50 ayer a las 10:16 será '
                    'revisado."],\n<parameter name="answer">no'
                ),
            ),
            ("charge", "recognize_charge"),
        ),
        "topic_pt": (
            "composed",
            (
                (
                    "Sua compra em Starbucks por R$\xa021,60 foi ontem às 20:28, na loja. Antes você fez 28 "
                    "compras lá; o valor típico é R$\xa032,67."
                ),
            ),
            ("charge", "recognize_charge"),
        ),
        "remembered_es": (
            "fallback",
            ("La compra en Tambo+ por S/\xa049.30 está aprobada.",),
            ("charge",),
        ),
        "remembered_pt": (
            "composed",
            (
                (
                    "Vejo que você já me havia dito que reconhecia essa cobrança em 99: “era a gasolina da "
                    "viagem para Santos”. Se agora você não reconhece mais esse gasto, podemos abrir uma "
                    "contestação para revisar o que aconteceu."
                ),
            ),
            ("charge",),
        ),
        "flagged_es": (
            "repaired",
            ("Entendido.",),
            ("charge", "was_it_you"),
        ),
        "flagged_pt": (
            "composed",
            (
                (
                    "Sua compra em TEMU.COM 2979 por R$\xa0522,83 foi hoje às 13:30, pela internet. O banco "
                    "notou um valor alto e que é sua primeira vez comprando lá: o sistema de alertas do "
                    "banco emitiu um alerta e é a sua primeira compra neste estabelecimento."
                ),
            ),
            ("charge", "was_it_you"),
        ),
        "unblock_es": (
            "composed",
            (
                (
                    "El desbloqueo de una tarjeta es algo que solo una persona del banco puede hacer. "
                    "Podemos conectarte con alguien del equipo para que lo resuelva."
                ),
            ),
            ("handoff", "talk_to_person"),
        ),
        "unblock_pt": (
            "composed",
            (
                (
                    "Desbloquear um cartão é algo que um representante do banco precisa fazer. Gostaria de "
                    "falar com alguém lá?"
                ),
            ),
            ("handoff", "talk_to_person"),
        ),
        "ten_days_pt": (
            "composed",
            (
                (
                    "Se o prazo do banco terminar sem resposta, você pode escrever para a Ouvidoria do LATAM "
                    "Bank, em ouvidoria.br@latambank.example, que responde em 10 dias úteis. O Procon é o "
                    "passo seguinte fora do banco."
                ),
            ),
            (),
        ),
        "about_you_pt": (
            "say_key",
            (
                "Você é Ana, cliente do LATAM Bank (Brasil).",
                (
                    "Você tem 3 cartões: o de crédito final 0470, o de crédito final 9210 e o de débito "
                    "final 6341."
                ),
            ),
            (),
        ),
        "document_pt": (
            "composed",
            (
                (
                    "Não tenho acesso ao seu documento nem ao seu endereço. Posso ajudar com informações "
                    "sobre seus cartões, movimentações, gastos e casos abertos com o banco."
                ),
            ),
            (),
        ),
        "cannot_tell_pt": (
            "composed",
            (
                (
                    "Não tenho acesso ao seu documento, endereço, telefone, número completo do cartão, CVV "
                    "ou outros dados pessoais. Só posso ajudar você com informações sobre seus cartões, "
                    "movimentações, gastos e casos de contestação no banco."
                ),
            ),
            (),
        ),
        "spanish_pt": (
            "repaired",
            ("Você tem 2 cartões de crédito e ambas estão ativas.",),
            ("cards",),
        ),
        "largest_pt": (
            "composed",
            (
                (
                    "Sua maior compra de 21 de junho a 20 de setembro foi em LATAM Airlines, de "
                    "R$\xa01.852,15, em 6 de julho às 19:01."
                ),
            ),
            ("movement",),
        ),
        "rio_pt": (
            "composed",
            ("Não: 1 em Belo Horizonte e 1 no Rio de Janeiro.",),
            ("movements",),
        ),
        "rio_again_pt": (
            "composed",
            ("Não: 3 em Curitiba. Todas as compras que encontrei foram em Curitiba.",),
            ("movements",),
        ),
        "ten_days_again_pt": (
            "fallback",
            (
                "O seu caso CLR-2026-801204 (contestação) está em análise.",
                (
                    "É o que diz o banco em “Ciclo de uma contestação”: Você pode pedir para falar com uma "
                    "pessoa pelo chat, que atende todos os dias, das 8h às 22h, ou no +55 11 4000 2000, que "
                    "atende 24 horas, todos os dias. Se não estiver satisfeito com a resposta, ou se o prazo "
                    "do banco terminar sem ela, você pode escrever para a ouvidoria do banco, Ouvidoria do "
                    "LATAM Bank, em ouvidoria.br@latambank.example, que responde em 10 dias úteis. O órgão "
                    "de defesa do consumidor (Procon) é o passo seguinte fora do banco."
                ),
            ),
            ("case",),
        ),
        "unrecognized_es_tap": (
            "composed",
            (
                (
                    "Tu compra en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30, por internet. Es tu "
                    "primera compra ahí. Lo que notó el banco: el sistema de alertas del banco emitió una "
                    "alerta y es tu primera compra en este comercio."
                ),
            ),
            ("charge", "was_it_you"),
        ),
        "unrecognized_pt_tap": (
            "composed",
            (
                (
                    "Sua compra em TEMU.COM 2979 por R$\xa0522,83 foi hoje às 13:30, por internet. É a "
                    "primeira vez que você compra nessa loja. O que o banco notou: o sistema de alertas do "
                    "banco emitiu um alerta e é a sua primeira compra neste estabelecimento."
                ),
            ),
            ("charge", "was_it_you"),
        ),
        "unrecognized_es_pick": (
            "composed",
            (
                (
                    "Tu compra en Inkafarma por S/\xa089.90 fue ayer a las 20:15. Antes hiciste 18 compras "
                    "ahí; lo típico es S/\xa096.85."
                ),
            ),
            ("charge", "recognize_charge"),
        ),
        "unrecognized_es_kept": (
            "composed",
            (
                (
                    "Es una compra en Inkafarma que hiciste ayer a las 20:15, en tienda. Tienes el historial "
                    "de 18 compras ahí; lo que típicamente gastas en esa farmacia es S/\xa096.85, así que "
                    "este monto de S/\xa089.90 está en línea con lo que normalmente compras."
                ),
            ),
            ("charge", "recognize_charge"),
        ),
        "unrecognized_es_pick_yes": (
            "story",
            ("Gracias, lo anoto: reconoces este cargo y no volveré a preguntarte por él.",),
            (),
        ),
        "unrecognized_es_free": (
            "story",
            (
                (
                    "Gracias, lo anoto: reconoces este cargo y «claro, esa la hice yo en el grifo». No "
                    "volveré a preguntarte por él."
                ),
            ),
            (),
        ),
        "unrecognized_pt_pick": (
            "composed",
            (
                (
                    "Sua compra na Drogasil de R$\xa046,71 foi ontem às 19:22, na loja. Você fez 19 compras "
                    "lá antes; o valor típico é R$\xa0223,94."
                ),
            ),
            ("charge", "recognize_charge"),
        ),
        "unrecognized_pt_pick_yes": (
            "story",
            ("Obrigada, anotei: você reconhece esta cobrança e não vou perguntar de novo sobre ela.",),
            (),
        ),
        "unrecognized_pt_free": (
            "story",
            (
                (
                    "Obrigada, anotei: você reconhece esta cobrança e não vou perguntar de novo sobre ela. "
                    "“foi eu sim, era o cinema com a família”"
                ),
            ),
            (),
        ),
        "flagged_es_why": (
            "story",
            (
                (
                    "Te pregunto por tu compra en TEMU.COM 2979 porque el banco notó esto: el sistema de "
                    "alertas del banco emitió una alerta y es tu primera compra en este comercio."
                ),
            ),
            ("charge", "was_it_you"),
        ),
        "flagged_es_block": (
            "story",
            (
                "Listo: tu tarjeta terminada en 3302 quedó bloqueada, y lo confirmé en tu cuenta.",
                (
                    "Abrí el caso CLR-2026-385822 con lo que revisamos. Te contactará una persona del banco, "
                    "y esto es lo que ya sabe."
                ),
            ),
            ("case",),
        ),
        "flagged_pt_why": (
            "story",
            (
                (
                    "Pergunto sobre sua compra em TEMU.COM 2979 porque o banco notou isto: o sistema de "
                    "alertas do banco emitiu um alerta e é a sua primeira compra neste estabelecimento."
                ),
            ),
            ("charge", "was_it_you"),
        ),
        "flagged_pt_block": (
            "story",
            (
                "Pronto: seu cartão final 8602 foi bloqueado, e eu confirmei isso na sua conta.",
                (
                    "Abri o caso CLR-2026-385822 com o que verificamos. Uma pessoa do banco vai entrar em "
                    "contato, e isto é o que ela já sabe."
                ),
            ),
            ("case",),
        ),
        "unblock_es_yes": (
            "story",
            (
                (
                    "Abrí el caso CLR-2026-738532 con lo que revisamos. Te contactará una persona del banco, "
                    "y esto es lo que ya sabe."
                ),
            ),
            ("case",),
        ),
        "unblock_pt_yes": (
            "story",
            (
                (
                    "Abri o caso CLR-2026-738532 com o que verificamos. Uma pessoa do banco vai entrar em "
                    "contato, e isto é o que ela já sabe."
                ),
            ),
            ("case",),
        ),
        "case_es_yes": (
            "story",
            (
                (
                    "Abrí el caso CLR-2026-738532 con lo que revisamos. Te contactará una persona del banco, "
                    "y esto es lo que ya sabe."
                ),
            ),
            ("case",),
        ),
        "case_pt_yes": (
            "story",
            (
                (
                    "Abri o caso CLR-2026-738532 com o que verificamos. Uma pessoa do banco vai entrar em "
                    "contato, e isto é o que ela já sabe."
                ),
            ),
            ("case",),
        ),
    },
}


TAPPED = ("unrecognized_es", "unrecognized_pt")
DEFAULT = profiles()[0]


def replayed(
    name: str, profile: ModelProfile, message: Message, history: list[Message], country: str | None = None
) -> tuple[Turn, Any]:
    recording = json.loads((RECORDINGS / profile.key / f"{name}.json").read_text())
    model = FakeConverse([exchange["response"] for exchange in recording["exchanges"]])
    country = country or DEMO[base(name)].country
    result = run_turn(
        message, history, NOW, profile=profile, clients=model.client, policies=policy_index(country)
    )
    assert normalized(model.requests) == normalized(
        [exchange["request"] for exchange in recording["exchanges"]]
    )
    return result, model


def deterministic(message: Message, history: list[Message]) -> Turn:
    model = FakeConverse([])
    result = run_turn(message, history, NOW, profile=DEFAULT, clients=model.client)
    assert model.requests == []
    return result


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
    said, earlier = tap(picked, before, result.reply, "yes", step=1)
    assert_expected(replayed(f"{name}_pick_yes", profile, said, earlier)[0], profile, f"{name}_pick_yes")
    forget(aws, question.customer_id)
    denied, before_denial = kept(picked, before, result.reply, NOT_ME_FREE[name])
    assert [
        part["ask"] for part in deterministic(denied, before_denial).reply.parts if part["type"] == "ask"
    ] == ["block_card"]
    forget(aws, question.customer_id)
    owned, before_owning = kept(picked, before, result.reply, FREE[name])
    free, _ = replayed(f"{name}_free", profile, owned, before_owning)
    assert_expected(free, profile, f"{name}_free")
    assert free.summary()["writes"] == ["memory:graph"]


@pytest.mark.parametrize("profile", profiles(), ids=lambda row: row.key)
@pytest.mark.parametrize("name", FLAGGED)
def test_every_declared_model_replays_the_flagged_charge_from_the_question_to_the_handoff(
    aws: Aws, name: str, profile: ModelProfile
) -> None:
    question, history = demo_turn(aws, name)
    first, _ = replayed(name, profile, question, history)
    asked_why, earlier = tap(question, history, first.reply, "why")
    why, _ = replayed(f"{name}_why", profile, asked_why, earlier)
    said_no, before = tap(question, history, first.reply, "no")
    confirm = deterministic(said_no, before)
    said_yes, after = tap(said_no, before, confirm.reply, "yes", step=1)

    done, _ = replayed(f"{name}_block", profile, said_yes, after)

    assert_expected(first, profile, name)
    assert_expected(why, profile, f"{name}_why")
    assert [part["ask"] for part in confirm.reply.parts if part["type"] == "ask"] == ["block_card"]
    assert_expected(done, profile, f"{name}_block")
    assert [effect["type"] for effect in done.reply.effects] == ["card_blocked", "case_opened"]


@pytest.mark.parametrize("profile", profiles(), ids=lambda row: row.key)
@pytest.mark.parametrize("name", ABSTAINED)
def test_every_declared_model_replays_the_person_s_yes_after_an_abstention(
    aws: Aws, name: str, profile: ModelProfile
) -> None:
    question, history = demo_turn(aws, name)
    first, _ = replayed(name, profile, question, history)
    said_yes, earlier = tap(question, history, first.reply, "yes")

    handed, _ = replayed(f"{name}_yes", profile, said_yes, earlier)

    assert_expected(handed, profile, f"{name}_yes")
    assert [effect["type"] for effect in handed.reply.effects] == ["case_opened"]


@pytest.mark.parametrize("locale", ["es", "pt"])
def test_the_default_model_replays_the_claim_path_and_the_lost_card(aws: Aws, locale: str) -> None:
    question, history = demo_turn(aws, f"topic_{locale}")
    asked, _ = replayed(f"topic_{locale}", DEFAULT, question, history)
    said_no, before = tap(question, history, asked.reply, "no")
    card_question = deterministic(said_no, before)
    has_it, after = tap(said_no, before, card_question.reply, "yes", step=1)
    consent = deterministic(has_it, after)
    opened_it, last = tap(has_it, after, consent.reply, "yes", step=2)
    opened, _ = replayed(f"topic_{locale}_open", DEFAULT, opened_it, last)

    assert_expected(opened, DEFAULT, f"topic_{locale}_open")
    assert [effect["case_type"] for effect in opened.reply.effects] == ["claim"]

    country = DEMO[f"topic_{locale}"].country
    sent = NOW - timedelta(seconds=2)
    lost = customer_message(question.customer_id, demo_id(sent, 0), demo_id(sent, 1), LOST[locale], sent)
    listed = deterministic(lost, [])
    [ask] = [part for part in listed.reply.parts if part["type"] == "ask"]
    picked, earlier = tap(lost, [], listed.reply, ask["options"][0]["id"])
    confirm = deterministic(picked, earlier)
    said_yes, after_pick = tap(picked, earlier, confirm.reply, "yes", step=1)
    blocked, _ = replayed(f"lost_{locale}_block", DEFAULT, said_yes, after_pick, country)

    assert_expected(blocked, DEFAULT, f"lost_{locale}_block")
    assert [effect["type"] for effect in blocked.reply.effects] == ["card_blocked", "case_opened"]


def test_the_default_model_answers_the_recorded_set_with_no_fallback_and_few_repairs() -> None:
    sources = [source for source, _, _ in EXPECTED[DEFAULT.key].values()]

    chains = 4 * len(TAPPED) + len(KEPT) + 2 * len(FLAGGED) + len(ABSTAINED) + 2 * len(LOST)
    assert len(sources) == len(DEMO) + chains
    assert "fallback" not in sources
    assert sources.count("repaired") / len(sources) < 1 / 5


def normalized(requests: list[dict[str, Any]]) -> Any:
    return json.loads(json.dumps(requests, ensure_ascii=False, default=str))
