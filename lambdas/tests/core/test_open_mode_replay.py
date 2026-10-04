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
    KEPT,
    NOW,
    RECORDINGS,
    base,
    demo_id,
    demo_turn,
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
                    "Este mes llevas S/\xa02,091.60 en Primax, versus S/\xa0949.50 el mes pasado. Gastaste "
                    "S/\xa01,142.10 más que el mes pasado."
                ),
            ),
            ("movements",),
        ),
        "case_es": (
            "composed",
            (
                (
                    "Tu aclaración CLR-2026-182061 sobre el cargo en Primax por S/\xa0127.80 está en "
                    "revisión desde hoy. El banco revisa la aclaración en un plazo de 10 días hábiles."
                ),
            ),
            (
                "case",
                "talk_to_person",
            ),
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
                    "Sua contestação CLR-2026-862021, referente à cobrança de R$\xa0197,26 em Pão de "
                    "Açúcar no seu cartão final 6400, está em análise desde hoje. O banco analisa a "
                    "contestação em até 8 dias úteis."
                ),
            ),
            (
                "case",
                "talk_to_person",
            ),
        ),
        "movements_es": (
            "composed",
            ("Encontré 216 movimientos en ese período. Aquí ves los más recientes, de tus 3 tarjetas.",),
            ("movements",),
        ),
        "visa_es": (
            "composed",
            (
                (
                    "Tienes 61 movimientos este mes entre todas tus tarjetas. Como tienes 2 tarjetas de "
                    "crédito, dime si quieres ver los movimientos de tu tarjeta terminada en 9454 o de "
                    "tu tarjeta terminada en 3229."
                ),
            ),
            ("which_one",),
        ),
        "cards_pt": (
            "composed",
            (
                (
                    "Você tem 3 cartões: 2 cartões de crédito e 1 cartão de débito. Seu cartão final "
                    "2338 e seu cartão final 6913 são de crédito, ambos ativos. Seu cartão final 3530 é "
                    "de débito, também ativo."
                ),
            ),
            ("cards",),
        ),
        "charge_pt": (
            "repaired",
            (
                (
                    "Encontrei 13 movimentações de Ipiranga no período de 22 de agosto a 20 de "
                    "setembro. Para eu te mostrar a certa, você pode me dizer a data ou o valor da "
                    "cobrança que quer entender?"
                ),
            ),
            ("movements",),
        ),
        "unrecognized_es": (
            "composed",
            (
                (
                    "Estos son tus movimientos más recientes. ¿Cuál es el que no reconoces? Si no está "
                    "entre ellos, dime su fecha o su monto."
                ),
            ),
            (
                "movements",
                "which_one",
            ),
        ),
        "unrecognized_pt": (
            "composed",
            (
                (
                    "Estas são suas movimentações mais recentes. Qual é a que você não reconhece? Se "
                    "não estiver entre elas, me diga a data ou o valor."
                ),
            ),
            (
                "movements",
                "which_one",
            ),
        ),
        "cancel_es": (
            "repaired",
            (
                (
                    "Si bloqueas una tarjeta, los cobros recurrentes que se intenten con ella son "
                    "rechazados, pero el bloqueo no cancela ninguna suscripción ni ningún servicio por "
                    "sí mismo. Tus suscripciones están en tarjetas distintas: Movistar se cobra a tu "
                    "tarjeta terminada en 5529 y Netflix a tu tarjeta terminada en 1211, así que "
                    "bloquear una no afecta a la otra."
                ),
                (
                    "Cuando un pago es rechazado, cada comercio decide qué hace con eso; para evitar "
                    "interrupciones, lo recomendable es actualizar la forma de pago o cancelar la "
                    "suscripción directamente con el comercio."
                ),
            ),
            ("movements",),
        ),
        "cancel_again_es": (
            "composed",
            (
                (
                    "Al bloquear una tarjeta, los cargos recurrentes que intenten cobrarse en esa "
                    "tarjeta serán rechazados, ya que no acepta nuevos cargos. El bloqueo en sí no "
                    "cancela ninguna suscripción ni servicio."
                ),
                (
                    "Tus suscripciones están en tarjetas distintas: Movistar se cobra en tu tarjeta "
                    "terminada en 4071 y Netflix en tu tarjeta terminada en 9558. Si bloqueas solo una "
                    "de ellas, solo los cargos de esa tarjeta serían rechazados."
                ),
                (
                    "Cuando una suscripción es rechazada, cada comercio decide qué hace: puedes "
                    "actualizar tu forma de pago cuando recibas la tarjeta nueva, o cancelar "
                    "directamente con el comercio si ya no la quieres."
                ),
            ),
            ("movements",),
        ),
        "that_one_es": (
            "composed",
            (
                (
                    "El cargo de TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30, por internet. Lo que "
                    "notó el banco: el sistema de alertas del banco emitió una alerta y es tu primera "
                    "compra en este comercio."
                ),
            ),
            ("charge",),
        ),
        "what_now_es": (
            "composed",
            (
                (
                    "La aclaración puede presentarse aquí con Clara o por teléfono, y quedará "
                    "registrada con un número de caso. Una vez abierta, el banco revisa tu caso en un "
                    "plazo de 10 días hábiles."
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
            (
                "charge",
                "recognize_charge",
            ),
        ),
        "topic_pt": (
            "composed",
            (
                (
                    "Essa cobrança de Starbucks por R$\xa021,60 foi ontem às 20:28, na loja em São Paulo. "
                    "Você já fez 28 compras lá antes, com valor típico de R$\xa032,67."
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
            "repaired",
            ("Você já me disse antes que reconhece essa cobrança: “era a gasolina da viagem para Santos”.",),
            ("charge",),
        ),
        "flagged_es": (
            "composed",
            (
                (
                    "Tu cargo en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30, por internet. Lo que "
                    "notó el banco: el sistema de alertas del banco emitió una alerta y es tu primera "
                    "compra en este comercio."
                ),
            ),
            (
                "charge",
                "was_it_you",
            ),
        ),
        "flagged_pt": (
            "composed",
            (
                (
                    "Essa cobrança de R$\xa0522,83 em TEMU.COM 2979 foi hoje às 13:30, pela internet. O "
                    "que o banco notou: o sistema de alertas do banco emitiu um alerta e é a sua "
                    "primeira compra neste estabelecimento."
                ),
            ),
            (
                "charge",
                "was_it_you",
            ),
        ),
        "unblock_es": (
            "composed",
            (
                (
                    "Desbloquear una tarjeta es algo que realiza una persona del banco directamente. Lo "
                    "que sí puedo confirmarte es que tus tarjetas están activas en este momento."
                ),
            ),
            ("talk_to_person",),
        ),
        "unblock_pt": (
            "composed",
            ("Desbloquear um cartão é algo que um atendente do banco pode fazer por você.",),
            ("talk_to_person",),
        ),
        "unrecognized_es_tap": (
            "composed",
            (
                (
                    "Tu cargo en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30, por internet. Lo que "
                    "notó el banco: el sistema de alertas del banco emitió una alerta y es tu primera "
                    "compra en este comercio."
                ),
            ),
            (
                "charge",
                "was_it_you",
            ),
        ),
        "unrecognized_pt_tap": (
            "composed",
            (
                (
                    "Essa cobrança de R$\xa0522,83 em TEMU.COM 2979 foi hoje às 13:30, pela internet. O "
                    "que o banco observou: o sistema de alertas do banco emitiu um alerta e é a sua "
                    "primeira compra neste estabelecimento."
                ),
            ),
            (
                "charge",
                "was_it_you",
            ),
        ),
        "unrecognized_es_pick": (
            "composed",
            (
                (
                    "Tu cargo en Inkafarma por S/\xa089.90 fue ayer a las 20:15, en tienda, en Cusco. "
                    "Antes hiciste 18 compras ahí y lo típico es S/\xa096.85."
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
                    "Antes de este cargo tienes 18 compras en Inkafarma, y la más reciente fue ayer. Lo "
                    "típico que gastas ahí es S/\xa096.85, y este cargo de S/\xa089.90 está dentro de ese "
                    "rango."
                ),
            ),
            (
                "charge",
                "recognize_charge",
            ),
        ),
        "unrecognized_es_pick_yes": (
            "story",
            ("Gracias, lo anoto: reconoces este cargo y no volveré a preguntarte por él.",),
            (),
        ),
        "unrecognized_pt_pick": (
            "composed",
            (
                (
                    "Essa cobrança em Drogasil de R$\xa046,71 foi ontem às 19:22, na loja. Você já fez 19 "
                    "compras lá, com valor típico de R$\xa0223,94."
                ),
            ),
            (
                "charge",
                "recognize_charge",
            ),
        ),
        "unrecognized_pt_pick_yes": (
            "story",
            ("Obrigada! Anotei que você reconhece esta cobrança e não vou perguntar sobre ela novamente.",),
            (),
        ),
        "flagged_es_why": (
            "story",
            (
                (
                    "Te pregunto por tu compra en TEMU.COM 2979 porque el banco notó esto: el sistema "
                    "de alertas del banco emitió una alerta y es tu primera compra en este comercio."
                ),
            ),
            (
                "charge",
                "was_it_you",
            ),
        ),
        "flagged_es_block": (
            "story",
            (
                "Listo: tu tarjeta terminada en 3302 quedó bloqueada, y lo confirmé en tu cuenta.",
                (
                    "Abrí el caso CLR-2026-385822 con lo que revisamos. Te contactará una persona del "
                    "banco, y esto es lo que ya sabe."
                ),
            ),
            ("case",),
        ),
        "flagged_pt_why": (
            "story",
            (
                (
                    "Estou perguntando sobre sua compra em TEMU.COM 2979 porque o banco observou o "
                    "seguinte nela: o sistema de alertas do banco emitiu um alerta e é a sua primeira "
                    "compra neste estabelecimento."
                ),
            ),
            (
                "charge",
                "was_it_you",
            ),
        ),
        "flagged_pt_block": (
            "story",
            (
                "Pronto: seu cartão final 8602 foi bloqueado, e eu confirmei isso na sua conta.",
                (
                    "Abri o caso CLR-2026-385822 com o que verificamos. Uma pessoa do banco vai entrar "
                    "em contato, e isto é o que ela já sabe."
                ),
            ),
            ("case",),
        ),
        "unblock_es_yes": (
            "story",
            (
                (
                    "Abrí el caso CLR-2026-738532 con lo que revisamos. Te contactará una persona del "
                    "banco, y esto es lo que ya sabe."
                ),
            ),
            ("case",),
        ),
        "unblock_pt_yes": (
            "story",
            (
                (
                    "Abri o caso CLR-2026-738532 com o que verificamos. Uma pessoa do banco vai entrar "
                    "em contato, e isto é o que ela já sabe."
                ),
            ),
            ("case",),
        ),
        "case_es_yes": (
            "story",
            (
                (
                    "Abrí el caso CLR-2026-738532 con lo que revisamos. Te contactará una persona del "
                    "banco, y esto es lo que ya sabe."
                ),
            ),
            ("case",),
        ),
        "case_pt_yes": (
            "story",
            (
                (
                    "Abri o caso CLR-2026-738532 com o que verificamos. Uma pessoa do banco vai entrar "
                    "em contato, e isto é o que ela já sabe."
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
                    "Abrí el caso CLR-2026-385822 con lo que revisamos. Te contactará una persona del "
                    "banco, y esto es lo que ya sabe."
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
                    "Abri o caso CLR-2026-385822 com o que verificamos. Uma pessoa do banco vai entrar "
                    "em contato, e isto é o que ela já sabe."
                ),
            ),
            ("case",),
        ),
    },
    "haiku-4-5": {
        "spend_es": (
            "repaired",
            (
                (
                    "Este mes gastaste S/\xa01,142.10 más que el mes pasado en Primax. Este mes son "
                    "S/\xa02,091.60, comparado con S/\xa0949.50 el mes pasado."
                ),
            ),
            ("movements",),
        ),
        "case_es": (
            "repaired",
            (
                (
                    "Tu aclaración CLR-2026-182061 está en revisión. El banco revisa tu aclaración "
                    "dentro del plazo de revisión de 10 días hábiles."
                ),
            ),
            ("talk_to_person",),
        ),
        "spend_pt": (
            "composed",
            ("Você gastou R$\xa0145,31 a menos no Ipiranga este mês do que no mês passado.",),
            (),
        ),
        "case_pt": (
            "composed",
            (
                (
                    "Sua contestação CLR-2026-862021 está em análise. O banco analisa e responde dentro "
                    "do prazo de 8 dias úteis."
                ),
            ),
            (
                "case",
                "talk_to_person",
            ),
        ),
        "movements_es": (
            "repaired",
            (
                (
                    "En los últimos meses tuviste 216 movimientos. Los más recientes son en Cineplanet, "
                    "Tambo+, Starbucks, Cabify y otras tiendas."
                ),
            ),
            ("movements",),
        ),
        "visa_es": (
            "repaired",
            (
                (
                    "En tu tarjeta terminada en 9454 tienes 25 movimientos del 1 al 20 de septiembre. "
                    "Los más recientes son compras en Plaza Vea, Primax, Cabify, Rappi y Rappi."
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
            "repaired",
            (
                (
                    "Você tem 13 movimentações no Ipiranga de 22 de agosto a 20 de setembro. São "
                    "compras em posto de gasolina, feitas na loja em Curitiba. Qual é a que você quer "
                    "saber mais? Se não estiver entre estas, diga a data ou o valor."
                ),
            ),
            ("movements",),
        ),
        "unrecognized_es": (
            "composed",
            (
                (
                    "Estos son tus movimientos más recientes. ¿Cuál es el que no reconoces? Si no está "
                    "entre ellos, dime su fecha o su monto."
                ),
            ),
            (
                "movements",
                "which_one",
            ),
        ),
        "unrecognized_pt": (
            "composed",
            (
                (
                    "Estas são suas movimentações mais recentes. Qual é a que você não reconhece? Se "
                    "não estiver entre elas, me diga a data ou o valor."
                ),
            ),
            (
                "movements",
                "which_one",
            ),
        ),
        "cancel_es": (
            "repaired",
            (
                (
                    "Si bloqueas tu tarjeta terminada en 5529 o terminada en 1211, los cargos "
                    "recurrentes de tus suscripciones serán rechazados porque la tarjeta ya no acepta "
                    "nuevos cargos. El bloqueo no cancela por sí mismo ninguna suscripción."
                ),
                (
                    "Actualiza la forma de pago en Movistar y Netflix cuando recibas una tarjeta nueva, "
                    "o cancela con ellos directamente si ya no los quieres."
                ),
            ),
            (),
        ),
        "cancel_again_es": (
            "repaired",
            (
                (
                    "No tengo información del banco sobre qué sucede con las suscripciones cuando "
                    "bloqueas una tarjeta. Eso depende de cómo estén configuradas con cada comercio "
                    "(Movistar en tu tarjeta terminada en 4071 y Netflix en tu tarjeta terminada en "
                    "9558) y de cómo esos servicios manejen los pagos rechazados. Lo mejor es que "
                    "contactes directamente con ellos si tienes dudas."
                ),
            ),
            (),
        ),
        "that_one_es": (
            "composed",
            (
                (
                    "Tu compra en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30 por internet. Lo que "
                    "notó el banco: el sistema de alertas del banco emitió una alerta y es tu primera "
                    "compra en este comercio."
                ),
            ),
            ("charge",),
        ),
        "what_now_es": (
            "repaired",
            (
                (
                    "Tu compra en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30 por internet. Lo que "
                    "notó el banco: el sistema de alertas del banco emitió una alerta y es tu primera "
                    "compra en este comercio."
                ),
                "Recibirás un número de caso y el banco revisa dentro de 10 días hábiles.",
            ),
            ("charge",),
        ),
        "topic_es": (
            "composed",
            (
                (
                    "Tu compra en Tambo+ por S/\xa020.50 fue ayer a las 10:16 en tienda. Antes hiciste 36 "
                    "compras ahí; lo típico es S/\xa030.80. Esta compra es más baja que el promedio."
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
                    "Sua compra em Starbucks por R$\xa021,60 foi ontem às 20:28 em São Paulo, na loja. "
                    "Antes você fez 28 compras lá; o valor típico é R$\xa032,67."
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
                    "Hace poco me dijiste que reconocías este cargo: «era la gasolina del viaje a "
                    "Paracas». Ahora dices que no lo reconoces. ¿Hay algo diferente en lo que me "
                    "cuentas ahora, o quieres que abra una aclaración por este cargo?"
                ),
            ),
            (),
        ),
        "remembered_pt": (
            "composed",
            (
                (
                    "Você já me tinha dito que reconhecia esta cobrança: “era a gasolina da viagem para "
                    "Santos”. Sua compra em 99 por R$\xa0129,17 foi ontem às 20:08, no app. Você tinha "
                    "feito 40 compras ali antes; o valor típico é R$\xa072,98."
                ),
            ),
            ("charge",),
        ),
        "flagged_es": (
            "composed",
            (
                (
                    "Tu compra en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30 en tu tarjeta "
                    "terminada en 3302, por internet. Es tu primer compra ahí. Lo que notó el banco: el "
                    "sistema de alertas del banco emitió una alerta y es tu primera compra en este "
                    "comercio."
                ),
            ),
            (
                "charge",
                "was_it_you",
            ),
        ),
        "flagged_pt": (
            "composed",
            (
                (
                    "Sua compra em TEMU.COM 2979 por R$\xa0522,83 foi hoje às 13:30, pela internet. É a "
                    "sua primeira compra nessa loja. O que o banco notou: o sistema de alertas do banco "
                    "emitiu um alerta e é a sua primeira compra neste estabelecimento."
                ),
            ),
            (
                "charge",
                "was_it_you",
            ),
        ),
        "unblock_es": (
            "repaired",
            ("El desbloqueo de tarjetas es algo que una persona en el banco puede hacer.",),
            ("talk_to_person",),
        ),
        "unblock_pt": (
            "composed",
            (
                (
                    "Todos os seus cartões estão ativos. Para desbloquear um cartão que está bloqueado, "
                    "você precisa falar com a gente."
                ),
            ),
            ("talk_to_person",),
        ),
        "unrecognized_es_tap": (
            "composed",
            (
                (
                    "Tu compra en TEMU.COM 2979 por S/\xa0363.10 fue hoy a las 11:30, por internet. Lo que "
                    "notó el banco: el sistema de alertas del banco emitió una alerta y es tu primera "
                    "compra en este comercio."
                ),
            ),
            (
                "charge",
                "was_it_you",
            ),
        ),
        "unrecognized_pt_tap": (
            "composed",
            (
                (
                    "Sua compra em TEMU.COM 2979 por R$\xa0522,83 foi hoje às 13:30 pela internet. É a "
                    "primeira vez que você compra nesse lugar. O que o banco notou: o sistema de "
                    "alertas do banco emitiu um alerta e é a sua primeira compra neste estabelecimento."
                ),
            ),
            (
                "charge",
                "was_it_you",
            ),
        ),
        "unrecognized_es_pick": (
            "composed",
            (
                (
                    "Tu compra en Inkafarma por S/\xa089.90 fue ayer a las 20:15 en tienda. Antes hiciste "
                    "18 compras ahí; lo típico es S/\xa096.85."
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
                    "El banco vio que es una compra típica en Inkafarma: hiciste 18 compras ahí antes, "
                    "y los montos son parecidos a los tuyos de siempre. Ayer a las 20:15 compraste "
                    "S/\xa089.90, muy cerca del promedio de S/\xa096.85. ¿Reconoces esta compra?"
                ),
            ),
            (
                "charge",
                "recognize_charge",
            ),
        ),
        "unrecognized_es_pick_yes": (
            "story",
            ("Gracias, lo anoto: reconoces este cargo y no volveré a preguntarte por él.",),
            (),
        ),
        "unrecognized_pt_pick": (
            "composed",
            (
                (
                    "Sua compra em Drogasil por R$\xa046,71 foi ontem às 19:22. Antes você fez 19 compras "
                    "lá; o valor típico é R$\xa0223,94."
                ),
            ),
            (
                "charge",
                "recognize_charge",
            ),
        ),
        "unrecognized_pt_pick_yes": (
            "story",
            ("Obrigada, anotei: você reconhece esta cobrança e não vou perguntar de novo sobre ela.",),
            (),
        ),
        "flagged_es_why": (
            "story",
            (
                (
                    "Te pregunto por tu compra en TEMU.COM 2979 porque el banco notó esto: el sistema "
                    "de alertas del banco emitió una alerta y es tu primera compra en este comercio."
                ),
            ),
            (
                "charge",
                "was_it_you",
            ),
        ),
        "flagged_es_block": (
            "story",
            (
                "Listo: tu tarjeta terminada en 3302 quedó bloqueada, y lo confirmé en tu cuenta.",
                (
                    "Abrí el caso CLR-2026-385822 con lo que revisamos. Te contactará una persona del "
                    "banco, y esto es lo que ya sabe."
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
            (
                "charge",
                "was_it_you",
            ),
        ),
        "flagged_pt_block": (
            "story",
            (
                "Pronto: seu cartão final 8602 foi bloqueado, e eu confirmei isso na sua conta.",
                (
                    "Abri o caso CLR-2026-385822 com o que verificamos. Uma pessoa do banco vai entrar "
                    "em contato, e isto é o que ela já sabe."
                ),
            ),
            ("case",),
        ),
        "unblock_es_yes": (
            "story",
            (
                (
                    "Abrí el caso CLR-2026-738532 con lo que revisamos. Te contactará una persona del "
                    "banco, y esto es lo que ya sabe."
                ),
            ),
            ("case",),
        ),
        "unblock_pt_yes": (
            "story",
            (
                (
                    "Abri o caso CLR-2026-738532 com o que verificamos. Uma pessoa do banco vai entrar "
                    "em contato, e isto é o que ela já sabe."
                ),
            ),
            ("case",),
        ),
        "case_es_yes": (
            "story",
            (
                (
                    "Abrí el caso CLR-2026-738532 con lo que revisamos. Te contactará una persona del "
                    "banco, y esto es lo que ya sabe."
                ),
            ),
            ("case",),
        ),
        "case_pt_yes": (
            "story",
            (
                (
                    "Abri o caso CLR-2026-738532 com o que verificamos. Uma pessoa do banco vai entrar "
                    "em contato, e isto é o que ela já sabe."
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

    chains = 3 * len(TAPPED) + len(KEPT) + 2 * len(FLAGGED) + len(ABSTAINED) + 2 * len(LOST)
    assert len(sources) == len(DEMO) + chains
    assert "fallback" not in sources
    assert sources.count("repaired") / len(sources) < 1 / 5


def normalized(requests: list[dict[str, Any]]) -> Any:
    return json.loads(json.dumps(requests, ensure_ascii=False, default=str))
