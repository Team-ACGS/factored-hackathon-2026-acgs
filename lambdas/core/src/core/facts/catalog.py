LOCALES = ("es", "pt-BR", "en")

NBSP = "\xa0"

WHOLE_CURRENCIES = frozenset({"COP"})

MONEY_STYLES: dict[str, dict[str, tuple[str, str, str, str]]] = {
    "es": {
        "MXN": ("$", "", ",", "."),
        "PEN": ("S/", NBSP, ",", "."),
        "COP": ("$", NBSP, ".", ","),
        "ARS": ("$", NBSP, ".", ","),
        "USD": ("$", "", ",", "."),
        "BRL": ("R$", "", ",", "."),
    },
    "pt-BR": {
        "MXN": ("$", NBSP, ".", ","),
        "PEN": ("PEN", NBSP, ".", ","),
        "COP": ("$", NBSP, ".", ","),
        "ARS": ("$", NBSP, ".", ","),
        "USD": ("$", NBSP, ".", ","),
        "BRL": ("R$", NBSP, ".", ","),
    },
    "en": {
        "MXN": ("$", "", ",", "."),
        "PEN": ("PEN", NBSP, ",", "."),
        "COP": ("$", "", ",", "."),
        "ARS": ("$", "", ",", "."),
        "USD": ("$", "", ",", "."),
        "BRL": ("R$", "", ",", "."),
    },
}

MONTHS = {
    "es": (
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    ),
    "pt-BR": (
        "janeiro",
        "fevereiro",
        "março",
        "abril",
        "maio",
        "junho",
        "julho",
        "agosto",
        "setembro",
        "outubro",
        "novembro",
        "dezembro",
    ),
    "en": (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ),
}

RELATIVE_DAYS = {
    "es": ("hoy", "ayer"),
    "pt-BR": ("hoje", "ontem"),
    "en": ("today", "yesterday"),
}

LAST4 = {"es": "terminada en {}", "pt-BR": "final {}", "en": "ending in {}"}

NOUNS: dict[str, dict[str, tuple[str, str]]] = {
    "purchase": {
        "es": ("compra", "compras"),
        "pt-BR": ("compra", "compras"),
        "en": ("purchase", "purchases"),
    },
    "movement": {
        "es": ("movimiento", "movimientos"),
        "pt-BR": ("movimentação", "movimentações"),
        "en": ("transaction", "transactions"),
    },
    "card": {"es": ("tarjeta", "tarjetas"), "pt-BR": ("cartão", "cartões"), "en": ("card", "cards")},
    "case": {"es": ("caso", "casos"), "pt-BR": ("caso", "casos"), "en": ("case", "cases")},
    "memory": {"es": ("nota", "notas"), "pt-BR": ("nota", "notas"), "en": ("note", "notes")},
    "day": {"es": ("día", "días"), "pt-BR": ("dia", "dias"), "en": ("day", "days")},
    "business_day": {
        "es": ("día hábil", "días hábiles"),
        "pt-BR": ("dia útil", "dias úteis"),
        "en": ("business day", "business days"),
    },
    "minute": {"es": ("minuto", "minutos"), "pt-BR": ("minuto", "minutos"), "en": ("minute", "minutes")},
    "excerpt": {
        "es": ("fragmento", "fragmentos"),
        "pt-BR": ("trecho", "trechos"),
        "en": ("excerpt", "excerpts"),
    },
    "subscription": {
        "es": ("cargo recurrente", "cargos recurrentes"),
        "pt-BR": ("cobrança recorrente", "cobranças recorrentes"),
        "en": ("recurring charge", "recurring charges"),
    },
}

STATUS_LABELS: dict[str, dict[str, dict[str, str]]] = {
    "card": {
        "Active": {"es": "activa", "pt-BR": "ativo", "en": "active"},
        "Blocked": {"es": "bloqueada", "pt-BR": "bloqueado", "en": "blocked"},
        "Inactive": {"es": "inactiva", "pt-BR": "inativo", "en": "inactive"},
        "Cancelled": {"es": "cancelada", "pt-BR": "cancelado", "en": "cancelled"},
    },
    "transaction": {
        "Approved": {"es": "aprobada", "pt-BR": "aprovada", "en": "approved"},
        "Pending": {"es": "pendiente", "pt-BR": "pendente", "en": "pending"},
        "Declined": {"es": "rechazada", "pt-BR": "recusada", "en": "declined"},
        "Reversed": {"es": "revertida", "pt-BR": "estornada", "en": "reversed"},
    },
    "stage": {
        "opened": {"es": "abierto", "pt-BR": "aberto", "en": "opened"},
        "assigned": {"es": "asignado", "pt-BR": "atribuído", "en": "assigned"},
        "in_review": {"es": "en revisión", "pt-BR": "em análise", "en": "in review"},
        "resolved": {"es": "resuelto", "pt-BR": "resolvido", "en": "resolved"},
        "closed": {"es": "cerrado", "pt-BR": "encerrado", "en": "closed"},
    },
}

LABELS: dict[str, dict[str, dict[str, str]]] = {
    "never_asked": {
        "full_card_number": {
            "es": "el número completo de la tarjeta",
            "pt-BR": "o número completo do seu cartão",
            "en": "your full card number",
        },
        "cvv": {"es": "el código de seguridad", "pt-BR": "o código de segurança", "en": "the security code"},
        "pin": {"es": "el PIN", "pt-BR": "a senha do cartão", "en": "your PIN"},
        "password": {"es": "la contraseña", "pt-BR": "a senha de acesso", "en": "your password"},
        "one_time_code": {
            "es": "los códigos que envía el banco",
            "pt-BR": "os códigos que enviamos para você",
            "en": "the codes we send you",
        },
    },
    "card_type": {
        "credit": {"es": "de crédito", "pt-BR": "de crédito", "en": "credit"},
        "debit": {"es": "de débito", "pt-BR": "de débito", "en": "debit"},
    },
    "channel": {
        "POS": {"es": "en tienda", "pt-BR": "na loja", "en": "in store"},
        "Web": {"es": "en línea", "pt-BR": "online", "en": "online"},
        "App": {"es": "en la app", "pt-BR": "no app", "en": "in the app"},
    },
    "category": {
        "Food": {"es": "comida", "pt-BR": "alimentação", "en": "food"},
        "Health": {"es": "salud", "pt-BR": "saúde", "en": "health"},
        "Transport": {"es": "transporte", "pt-BR": "transporte", "en": "transport"},
        "Entertainment": {"es": "entretenimiento", "pt-BR": "entretenimento", "en": "entertainment"},
        "Services": {"es": "servicios", "pt-BR": "serviços", "en": "services"},
        "Shopping": {"es": "compras", "pt-BR": "compras", "en": "shopping"},
        "Travel": {"es": "viajes", "pt-BR": "viagens", "en": "travel"},
    },
    "cadence": {
        "monthly": {"es": "mensual", "pt-BR": "mensal", "en": "monthly"},
        "weekly": {"es": "semanal", "pt-BR": "semanal", "en": "weekly"},
    },
    "direction": {
        "more": {"es": "más", "pt-BR": "mais", "en": "more"},
        "less": {"es": "menos", "pt-BR": "menos", "en": "less"},
        "same": {"es": "lo mismo", "pt-BR": "o mesmo", "en": "the same"},
    },
    "counted": {
        "approved_and_pending": {
            "es": "compras aprobadas y pendientes",
            "pt-BR": "compras aprovadas e pendentes",
            "en": "approved and pending purchases",
        },
    },
    "next_step": {
        "fraud_team_contacts_you": {
            "es": "el equipo de seguridad del banco te contactará",
            "pt-BR": "a equipe de segurança do banco vai entrar em contato com você",
            "en": "the bank's security team will contact you",
        },
        "review_in_progress": {
            "es": "el banco está revisando tu caso",
            "pt-BR": "o banco está analisando o seu caso",
            "en": "the bank is reviewing your case",
        },
        "resolution_sent": {
            "es": "el banco ya te envió su respuesta",
            "pt-BR": "o banco já enviou a resposta",
            "en": "the bank has sent you its answer",
        },
    },
    "case_type": {
        "fraud": {"es": "caso de seguridad", "pt-BR": "caso de segurança", "en": "security case"},
        "claim": {"es": "aclaración", "pt-BR": "contestação", "en": "dispute"},
        "service": {
            "es": "solicitud de atención",
            "pt-BR": "solicitação de atendimento",
            "en": "service request",
        },
    },
    "memory_type": {
        "recognized_charge": {
            "es": "un cargo que reconociste",
            "pt-BR": "uma cobrança que você reconheceu",
            "en": "a charge you recognized",
        },
        "recognized_merchant": {
            "es": "un comercio que reconociste",
            "pt-BR": "um estabelecimento que você reconheceu",
            "en": "a merchant you recognized",
        },
    },
    "explanation": {
        "reversed": {"es": "fue revertida", "pt-BR": "foi estornada", "en": "it was reversed"},
        "declined_attempted": {
            "es": "fue un intento rechazado",
            "pt-BR": "foi uma tentativa recusada",
            "en": "it was a declined attempt",
        },
        "fresh_hold": {
            "es": "es una retención reciente que todavía puede cambiar",
            "pt-BR": "é uma retenção recente que ainda pode mudar",
            "en": "it is a recent hold that can still change",
        },
        "stale_pending": {
            "es": "sigue pendiente desde hace tiempo",
            "pt-BR": "continua pendente há algum tempo",
            "en": "it has been pending for a while",
        },
        "prior_purchases": {
            "es": "ya habías comprado antes en este comercio",
            "pt-BR": "você já tinha comprado antes neste estabelecimento",
            "en": "you had bought from this merchant before",
        },
        "none": {
            "es": "no encuentro una explicación en tu historial",
            "pt-BR": "não encontro uma explicação no seu histórico",
            "en": "I find no explanation in your history",
        },
    },
    "score_band": {
        "high": {"es": "alta", "pt-BR": "alta", "en": "high"},
        "low": {"es": "baja", "pt-BR": "baixa", "en": "low"},
        "none": {"es": "sin alerta", "pt-BR": "sem alerta", "en": "no alert"},
    },
    "reason": {
        "score_high": {
            "es": "el sistema de alertas del banco la marcó",
            "pt-BR": "o sistema de alertas do banco a sinalizou",
            "en": "the bank's alert system flagged it",
        },
        "foreign_country": {
            "es": "es en otro país",
            "pt-BR": "é em outro país",
            "en": "it is in another country",
        },
        "unusual_channel": {
            "es": "es por un canal que no sueles usar",
            "pt-BR": "é por um canal que você não costuma usar",
            "en": "it is through a channel you do not usually use",
        },
        "new_merchant": {
            "es": "es tu primera compra en este comercio",
            "pt-BR": "é a sua primeira compra neste estabelecimento",
            "en": "it is your first purchase at this merchant",
        },
        "several_unrecognized": {
            "es": "hay varios cargos que no reconoces",
            "pt-BR": "há várias cobranças que você não reconhece",
            "en": "there are several charges you do not recognize",
        },
    },
}

COUNTRY_NAMES = {
    "PE": {"es": "Perú", "pt-BR": "Peru", "en": "Peru"},
    "MX": {"es": "México", "pt-BR": "México", "en": "Mexico"},
    "CO": {"es": "Colombia", "pt-BR": "Colômbia", "en": "Colombia"},
    "AR": {"es": "Argentina", "pt-BR": "Argentina", "en": "Argentina"},
    "US": {"es": "Estados Unidos", "pt-BR": "Estados Unidos", "en": "the United States"},
    "BR": {"es": "Brasil", "pt-BR": "Brasil", "en": "Brazil"},
}

DECIMAL_COMMA_COUNTRIES = frozenset({"AR", "CO", "BR"})

RATIO = {
    "es": {
        "far_below": "mucho menos de lo habitual",
        "below": "menos de lo habitual",
        "usual": "lo habitual",
        "above": "algo más de lo habitual",
        "times": "unas {} veces lo habitual",
        "far_above": "más de {} veces lo habitual",
    },
    "pt-BR": {
        "far_below": "muito menos do que o habitual",
        "below": "menos do que o habitual",
        "usual": "o habitual",
        "above": "um pouco mais do que o habitual",
        "times": "cerca de {} vezes o habitual",
        "far_above": "mais de {} vezes o habitual",
    },
    "en": {
        "far_below": "much less than usual",
        "below": "less than usual",
        "usual": "about the usual",
        "above": "a bit more than usual",
        "times": "about {} times the usual",
        "far_above": "more than {} times the usual",
    },
}

LIST_JOIN = {"es": " y ", "pt-BR": " e ", "en": " and "}

QUOTES = {"es": ("«", "»"), "pt-BR": ("“", "”"), "en": ("“", "”")}

CARDINALS = {
    "es": (
        "dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince dieciseis "
        "diecisiete dieciocho diecinueve veinte"
    ),
    "pt-BR": (
        "dois duas tres quatro cinco seis sete oito nove dez onze doze treze catorze quatorze quinze "
        "dezesseis dezessete dezoito dezenove vinte"
    ),
    "en": (
        "two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
        "seventeen eighteen nineteen twenty"
    ),
}

ORDINALS = {
    "es": (
        "segundo segunda segundos segundas tercer tercero tercera terceros terceras cuarto cuarta cuartos "
        "cuartas quinto quinta quintos quintas sexto sexta sextos sextas septimo septima octavo octava "
        "noveno novena decimo decima undecimo undecima duodecimo duodecima decimotercero decimotercera "
        "decimocuarto decimocuarta decimoquinto decimoquinta decimosexto decimosexta decimoseptimo "
        "decimoseptima decimoctavo decimoctava decimonoveno decimonovena vigesimo vigesima"
    ),
    "pt-BR": (
        "segundo segunda segundos segundas terceiro terceira terceiros terceiras quarto quarta quartos "
        "quartas quinto quinta quintos quintas sexto sexta sextos sextas setimo setima oitavo oitava "
        "nono nona decimo decima vigesimo vigesima"
    ),
    "en": (
        "second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth "
        "fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth twentieth"
    ),
}

NUMBER_HOMONYMS = {
    "es": (),
    "pt-BR": (r"segund[oa]s?\s+(o|a|os|as|seu|sua|seus|suas|ele|ela|eles|elas|este|esta|esse|essa)\b",),
    "en": (),
}

WEEKDAYS = {
    "es": "lunes martes miercoles jueves viernes sabado domingo",
    "pt-BR": "segunda-feira terca-feira quarta-feira quinta-feira sexta-feira terca sabado domingo",
    "en": "monday tuesday wednesday thursday friday saturday sunday",
}

DATE_WORDS = {
    "es": "setiembre hoy ayer anteayer manana",
    "pt-BR": "hoje ontem anteontem amanha",
    "en": "today yesterday tomorrow tonight",
}

DATE_HOMONYMS = {"en": ("may", "march")}

FORBIDDEN = {
    "fraud_word": (r"fraud\w*",),
    "safety_claim": (
        r"es seguro",
        r"es legitim[oa]",
        r"e seguro",
        r"e legitim[oa]",
        r"(is|it's|it is|its) (safe|legit|legitimate)",
    ),
    "money_promise": (
        r"reembols\w*",
        r"reintegr\w*",
        r"devolver(a|an|e|emos)",
        r"devolveremos",
        r"(te|le|lo|la|los) (vamos a |van a |va a )?(devolver|reintegrar|reembolsar|estornar)",
        r"vamos (te )?(devolver|reembolsar|estornar)",
        r"(recuperar|recibir|receber)\w* (o )?(tu|su|seu|teu) dinero",
        r"(recuperar|receber)\w* (o )?(seu|teu) dinheiro",
        r"garanti\w*",
        r"refund\w*",
        r"reimburs\w*",
        r"money back",
        r"(get|receive|recover) your money",
        r"guarante\w*",
    ),
    "legal_term": (
        r"abogad\w*",
        r"advogad\w*",
        r"demanda\w*",
        r"tribuna\w*",
        r"juzgado\w*",
        r"juicio\w*",
        r"judicia\w*",
        r"juiz\w*",
        r"ley|leyes|lei|leis|law|laws",
        r"legal\w*",
        r"indemniz\w*",
        r"indeniz\w*",
        r"lawyer\w*",
        r"attorney\w*",
        r"lawsuit\w*",
        r"sue|sued|suing",
        r"court\w*",
        r"liabilit\w*",
    ),
}

INSTRUCTIONS = {
    "unresolved_reference": "Use only references to facts and fields returned this turn.",
    "trace_only_reference": "This field is for tracing only; do not reference it in prose.",
    "unknown_citation": "Cite only policy chunks retrieved this turn.",
    "uncited_policy_reference": "Cite the chunk as [p:<chunk_id>] in each sentence that uses it.",
    "policy_figure_outside_reference": "State a policy figure only as {pN.figures.<group>.<key>}.",
    "digit_outside_reference": "Replace the number with a reference like {fN.field}.",
    "currency_outside_reference": "Write amounts only as references like {fN.amount}.",
    "date_outside_reference": "Write dates only as references like {fN.date}.",
    "number_word_outside_reference": "Write counts and ordinals only as references like {fN.count}.",
    "merchant_outside_reference": "Write merchants as references like {fN.merchant} or exactly as stored.",
    "contact_outside_facts": "Remove the phone, URL or email; it is not in the facts.",
    "fraud_word": "Never say fraud; describe what the bank saw instead.",
    "safety_claim": "Never say a charge is safe or legitimate.",
    "money_promise": "Never promise money back; describe the next step of the process instead.",
    "legal_term": "Avoid legal terms; describe the bank's process in plain words.",
    "view_id_unknown": "A view may show only ids a tool returned this turn.",
    "ask_target_unknown": "An ask may target only an id a tool returned this turn.",
}
