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
                    "Este mes gastaste S/\xa02,091.60 en Primax, comparado con S/\xa0949.50 el mes pasado. "
                    "Gastaste S/\xa01,142.10 más que el mes pasado."
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
                    "Este mês você gastou R$\xa01.456,06 no Ipiranga, R$\xa0145,31 a menos do que no mês "
                    "passado, quando o total foi R$\xa01.601,37."
                ),
            ),
            ("movements",),
        ),
        "case_pt": (
            "composed",
            (
                (
                    "Sua contestação CLR-2026-862021 está em análise, aberta em 14 de setembro e referente a "
                    "uma cobrança em Pão de Açúcar de R$\xa0197,26 no seu cartão final 6400."
                ),
                (
                    "O banco analisa a contestação em 8 dias úteis. Quem pode confirmar o desfecho e o "
                    "crédito é um atendente do banco."
                ),
            ),
            ("handoff", "talk_to_person"),
        ),
        "movements_es": (
            "composed",
            (
                (
                    "Encontré 216 movimientos en ese período (del 20 de julio al 20 de septiembre). Los más "
                    "recientes son en Cineplanet, Tambo+, Starbucks, Starbucks y Cabify."
                ),
            ),
            ("movements",),
        ),
        "visa_es": (
            "composed",
            (
                (
                    "Tienes 61 movimientos este mes en tus tarjetas. Si quieres ver solo los de una tarjeta "
                    "en particular, dime cuál: tu tarjeta terminada en 9454 o tu tarjeta terminada en 3229."
                ),
            ),
            ("movements",),
        ),
        "cards_pt": (
            "composed",
            ("Você tem 3 cartões: 2 cartões de crédito e 1 cartão de débito.",),
            ("cards",),
        ),
        "charge_pt": (
            "composed",
            (
                (
                    "Encontrei 13 movimentações da Ipiranga no período de 22 de agosto a 20 de setembro. "
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
                    "Si bloqueas una tarjeta, los cargos recurrentes que se intenten en ella son rechazados, "
                    "pero el bloqueo no cancela ninguna suscripción por sí mismo. Tienes Movistar en tu "
                    "tarjeta terminada en 5529 y Netflix en tu tarjeta terminada en 1211: si bloqueas alguna "
                    "de ellas, ese cobro quedaría rechazado."
                ),
                (
                    "Cuando un pago es rechazado, el comercio decide qué hacer con él; para evitar "
                    "interrupciones, deberías actualizar tu forma de pago con cada servicio al recibir la "
                    "tarjeta nueva, o cancelar la suscripción directamente con el comercio si ya no la "
                    "quieres."
                ),
            ),
            ("movements",),
        ),
        "cancel_again_es": (
            "composed",
            (
                (
                    "Si bloqueas una tarjeta, los cobros recurrentes que intenten cargarse a esa tarjeta "
                    "serán rechazados, pero el bloqueo no cancela por sí mismo ninguna suscripción ni "
                    "servicio."
                ),
                (
                    "Tu suscripción con Movistar va a tu tarjeta terminada en 4071, y la de Netflix va a tu "
                    "tarjeta terminada en 9558. Si alguna es rechazada, cada comercio decide qué hace con "
                    "ese pago; si ya no quieres el servicio, debes cancelarlo directamente con el comercio."
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
                    "Para abrir una aclaración puedes hacerlo desde la app con Clara o llamando al +51 1 600 "
                    "2000. Una vez abierta, el banco la revisa en 10 días hábiles."
                ),
            ),
            (),
        ),
        "topic_es": (
            "composed",
            (
                (
                    "Tu compra en Tambo+ por S/\xa020.50 fue ayer a las 10:16, en tienda en Trujillo. Antes "
                    "hiciste 36 compras ahí y lo típico es S/\xa030.80."
                ),
            ),
            ("charge", "recognize_charge"),
        ),
        "topic_pt": (
            "composed",
            (
                (
                    "A cobrança de R$\xa021,60 no Starbucks foi ontem às 20:28, na loja, em São Paulo. Você "
                    "já fez 28 compras lá antes, com valor típico de R$\xa032,67."
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
                    "Tu compra en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30, por internet. Lo que "
                    "notó el banco: el sistema de alertas del banco emitió una alerta y es tu primera compra "
                    "en este comercio."
                ),
            ),
            ("charge", "was_it_you"),
        ),
        "flagged_pt": (
            "repaired",
            (
                (
                    "A cobrança de R$\xa0522,83 em TEMU.COM 2979 foi hoje às 13:30, pela internet. O que o "
                    "banco observou: o sistema de alertas do banco emitiu um alerta e é a sua primeira "
                    "compra neste estabelecimento."
                ),
            ),
            ("charge", "was_it_you"),
        ),
        "unblock_es": (
            "repaired",
            (
                (
                    "Desbloquear una tarjeta es algo que realiza una persona del banco. Tu tarjeta terminada "
                    "en 8101, tu tarjeta terminada en 2322 y tu tarjeta terminada en 5943 están todas "
                    "activas en este momento."
                ),
            ),
            ("handoff", "talk_to_person"),
        ),
        "unblock_pt": (
            "repaired",
            ("Desbloquear um cartão é algo que só um atendente do banco pode fazer.",),
            ("handoff", "talk_to_person"),
        ),
        "ten_days_pt": (
            "repaired",
            (
                (
                    "Se o prazo terminar sem resposta, você pode escrever para a Ouvidoria do LATAM Bank em "
                    "ouvidoria.br@latambank.example, que responde em 10 dias úteis. Se a resposta não "
                    "resolver, o passo seguinte fora do banco é o Procon."
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
                    "Não tenho acesso ao seu documento nem ao seu endereço. Posso ajudar com seus cartões, "
                    "cobranças, gastos e contestações."
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
                    "movimentações, contestações e processos do banco."
                ),
            ),
            (),
        ),
        "spanish_pt": (
            "repaired",
            ("Você tem 2 cartões de crédito e ambos estão ativos.",),
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
            ("Não: 4 em Belo Horizonte e 1 no Rio de Janeiro.",),
            ("movements",),
        ),
        "rio_again_pt": (
            "composed",
            ("Não: 4 em Belo Horizonte e 1 no Rio de Janeiro.",),
            ("movements",),
        ),
        "ten_days_again_pt": (
            "composed",
            (
                (
                    "Se o prazo terminar sem resposta, você pode escrever para a Ouvidoria do LATAM Bank "
                    "pelo e-mail ouvidoria.br@latambank.example, que responde em 10 dias úteis. Se ainda "
                    "assim não resolver, o passo seguinte fora do banco é o Procon."
                ),
            ),
            (),
        ),
        "unrecognized_es_tap": (
            "composed",
            (
                (
                    "Tu compra en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30, por internet. Lo que "
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
                    "Esta cobrança em TEMU.COM 2979 de R$\xa0522,83 foi hoje às 13:30, pela internet. O que "
                    "o banco notou: o sistema de alertas do banco emitiu um alerta e é a sua primeira compra "
                    "neste estabelecimento."
                ),
            ),
            ("charge", "was_it_you"),
        ),
        "unrecognized_es_pick": (
            "composed",
            (
                (
                    "Tu cargo en Inkafarma por S/\xa089.90 fue ayer a las 20:15, en tienda en Cusco. Tienes "
                    "18 compras anteriores ahí y lo típico es S/\xa096.85."
                ),
            ),
            ("charge", "recognize_charge"),
        ),
        "unrecognized_es_kept": (
            "repaired",
            (
                (
                    "En realidad tienes 18 compras en Inkafarma, y la última fue ayer. El monto de ayer a "
                    "las 20:15, S/\xa089.90, está por debajo de lo típico que es S/\xa096.85."
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
                    "Sua cobrança em Drogasil de R$\xa046,71 foi ontem às 19:22, na loja. Você já fez 19 "
                    "compras lá, com valor típico de R$\xa0223,94."
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
                    "Obrigada! Anotei que você reconhece esta cobrança, “foi eu sim, era o cinema com a "
                    "família”, e não vou perguntar sobre ela novamente."
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
            ("Gastaste S/\xa02,091.60 en Primax este mes, S/\xa01,142.10 más que el mes pasado.",),
            ("movements",),
        ),
        "case_es": (
            "fallback",
            ("Lo que pasa con tu dinero lo decide una persona del banco.",),
            ("handoff", "talk_to_person"),
        ),
        "spend_pt": (
            "composed",
            ("Você gastou R$\xa0145,31 a menos no Ipiranga este mês em relação ao mês passado.",),
            (),
        ),
        "case_pt": (
            "composed",
            (
                (
                    "Sua contestação CLR-2026-862021 está em análise. O banco analisa a sua contestação e "
                    "responde dentro do prazo de análise de 8 dias úteis."
                ),
            ),
            ("handoff", "talk_to_person"),
        ),
        "movements_es": (
            "repaired",
            ("En ese período hiciste 216 movimientos. Acá ves tus movimientos más recientes.",),
            ("movements",),
        ),
        "visa_es": (
            "repaired",
            (
                (
                    "Tu tarjeta terminada en 9454 tiene 25 movimientos del 1 al 20 de septiembre. Las más "
                    "recientes: en Plaza Vea fue rechazada, en Primax está pendiente, y en Cabify, Rappi y "
                    "Rappi están aprobadas."
                ),
            ),
            ("movements",),
        ),
        "cards_pt": (
            "composed",
            (
                (
                    "Você tem 3 cartões: 2 cartões de crédito (terminadas em final 2338 e final 6913) e 1 "
                    "cartão de débito (terminada em final 3530). Todas estão ativos."
                ),
            ),
            ("cards",),
        ),
        "charge_pt": (
            "composed",
            (
                (
                    "Essa cobrança é no Ipiranga por R$\xa0144,77, em 18 de setembro às 20:23, em Curitiba. "
                    "Você já fez 31 compras aí; o valor típico é R$\xa0238,46."
                ),
            ),
            ("charge",),
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
                    "Estas são suas movimentações mais recentes. Qual delas você não reconhece? Se não "
                    "estiver entre elas, me diga a data ou o valor."
                ),
            ),
            ("movements", "which_one"),
        ),
        "cancel_es": (
            "composed",
            (
                (
                    "Si bloqueás tu tarjeta, tus suscripciones seguirían intentando cobrar en ella. Si el "
                    "cobro no se puede procesar, el servicio podría suspenderse, pero eso depende de cada "
                    "empresa. Tus cargos recurrentes son Movistar en tu tarjeta terminada en 5529 y Netflix "
                    "en tu tarjeta terminada en 1211."
                ),
                (
                    "Lo mejor es actualizar el método de pago directamente con cada servicio antes de "
                    "bloquear la tarjeta, o bloquear solo la que no uses para tus suscripciones."
                ),
            ),
            (),
        ),
        "cancel_again_es": (
            "composed",
            (
                (
                    "No tengo información del banco sobre qué pasa con las suscripciones si bloqueas una "
                    "tarjeta. Para esa pregunta necesitarías hablar con un ejecutivo del banco que pueda "
                    "revisar los términos de tus suscripciones y el funcionamiento de esos cargos "
                    "recurrentes."
                ),
            ),
            (),
        ),
        "that_one_es": (
            "composed",
            (
                (
                    "Tu compra en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30, por internet. Lo que "
                    "notó el banco: el sistema de alertas del banco emitió una alerta y es tu primera compra "
                    "en este comercio."
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
            "repaired",
            ("Entendido. El banco revisará este cargo en tu tarjeta terminada en 3000.",),
            ("charge", "recognize_charge"),
        ),
        "topic_pt": (
            "composed",
            (
                (
                    "Sua compra em Starbucks de R$\xa021,60 foi ontem às 20:28 na loja. Antes você fez 28 "
                    "compras lá; o valor típico é R$\xa032,67."
                ),
            ),
            ("charge", "recognize_charge"),
        ),
        "remembered_es": (
            "repaired",
            (
                (
                    "Ya me dijiste que reconoces este cargo: «era la gasolina del viaje a Paracas». Tu "
                    "compra en Tambo+ por S/\xa049.30 fue ayer a las 13:30, en tienda. Antes hiciste 38 "
                    "compras ahí; lo típico es S/\xa029.05."
                ),
            ),
            ("charge",),
        ),
        "remembered_pt": (
            "repaired",
            (
                (
                    "Vejo que você já me disse que reconhecia este cargo: “era a gasolina da viagem para "
                    "Santos”. Se agora você não reconhece, posso ajudar a revisar."
                ),
            ),
            ("charge",),
        ),
        "flagged_es": (
            "repaired",
            (
                (
                    "Tu compra en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30 en tu tarjeta terminada "
                    "en 3302. Lo que notó el banco: el sistema de alertas del banco emitió una alerta y es "
                    "tu primera compra en este comercio."
                ),
            ),
            ("charge", "was_it_you"),
        ),
        "flagged_pt": (
            "repaired",
            (
                (
                    "Sua compra em TEMU.COM 2979 de R$\xa0522,83 foi hoje às 13:30, por internet. O banco "
                    "notou: o sistema de alertas do banco emitiu um alerta e é a sua primeira compra neste "
                    "estabelecimento."
                ),
            ),
            ("charge", "was_it_you"),
        ),
        "unblock_es": (
            "composed",
            (
                (
                    "El desbloqueo de tu tarjeta es algo que solo una persona del banco puede hacer. La "
                    "banco te ofrece esa opción para que puedas hacerlo directamente."
                ),
            ),
            ("handoff", "talk_to_person"),
        ),
        "unblock_pt": (
            "composed",
            (
                (
                    "Um cartão bloqueado precisa ser desbloqueado por uma pessoa do banco. Qual é o cartão "
                    "que você quer desbloquear?"
                ),
            ),
            ("handoff", "talk_to_person"),
        ),
        "ten_days_pt": (
            "composed",
            (
                (
                    "Se o prazo do banco terminar sem resposta, você pode escrever para a Ouvidoria do LATAM "
                    "Bank em ouvidoria.br@latambank.example. A ouvidoria responde em 10 dias úteis."
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
                    "cartões, seus gastos, seus movimentos e seus casos no banco."
                ),
            ),
            (),
        ),
        "cannot_tell_pt": (
            "composed",
            (
                (
                    "Não tenho acesso ao seu documento, endereço, telefone, número completo do cartão ou "
                    "código de segurança. Também não posso consultar dados pessoais além do que você vê aqui "
                    "na conversa sobre seus movimentos, cartões e casos."
                ),
            ),
            (),
        ),
        "spanish_pt": (
            "repaired",
            ("Você tem 2 cartões de crédito e ambos estão ativos.",),
            (),
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
            ("Não: 4 em Belo Horizonte e 1 no Rio de Janeiro.",),
            ("movements",),
        ),
        "rio_again_pt": (
            "composed",
            ("Não: 4 em Belo Horizonte e 1 no Rio de Janeiro.",),
            ("movements",),
        ),
        "ten_days_again_pt": (
            "composed",
            (
                (
                    "Se o prazo do banco terminar sem resposta, você pode escrever para a Ouvidoria do LATAM "
                    "Bank em ouvidoria.br@latambank.example, que responde em 10 dias úteis."
                ),
            ),
            (),
        ),
        "unrecognized_es_tap": (
            "repaired",
            (
                (
                    "Tu compra en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30 en tu tarjeta terminada "
                    "en 9774. Lo que notó el banco: el sistema de alertas del banco emitió una alerta y es "
                    "tu primera compra en este comercio."
                ),
            ),
            ("charge", "was_it_you"),
        ),
        "unrecognized_pt_tap": (
            "composed",
            (
                (
                    "Sua compra em TEMU.COM 2979 de R$\xa0522,83 foi hoje às 13:30, pela internet. O banco "
                    "notou: o sistema de alertas do banco emitiu um alerta e é a sua primeira compra neste "
                    "estabelecimento."
                ),
            ),
            ("charge", "was_it_you"),
        ),
        "unrecognized_es_pick": (
            "composed",
            (
                (
                    "Tu compra en Inkafarma por S/\xa089.90 fue ayer a las 20:15, en tienda. Antes hiciste "
                    "18 compras ahí; lo típico es S/\xa096.85."
                ),
            ),
            ("charge", "recognize_charge"),
        ),
        "unrecognized_es_kept": (
            "composed",
            (
                (
                    "El cobro de S/\xa089.90 en Inkafarma ayer a las 20:15 está registrado en tu tarjeta "
                    "terminada en 0684. Hiciste 18 compras ahí antes, con un monto típico de S/\xa096.85, "
                    "así que este cargo es similar a lo que gastas normalmente en esa farmacia."
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
                    "Gracias, lo anoto: «claro, esa la hice yo en el grifo». No volveré a preguntarte por "
                    "este cargo."
                ),
            ),
            (),
        ),
        "unrecognized_pt_pick": (
            "composed",
            (
                (
                    "Sua compra na Drogasil por R$\xa046,71 foi ontem às 19:22. Antes você fez 19 compras "
                    "lá; o valor típico é R$\xa0223,94."
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
            ("Obrigada, anotei: você reconhece esta cobrança e não vou perguntar de novo sobre ela.",),
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
