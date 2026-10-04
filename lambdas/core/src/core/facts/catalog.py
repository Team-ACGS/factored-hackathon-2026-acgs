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

DATE_ARTICLE = {"es": "el ", "pt-BR": "em ", "en": ""}

ARTICLE_DROPPED_AFTER = {
    "es": frozenset({"el", "del", "al"}),
    "pt-BR": frozenset({"desde", "até", "de", "em", "no", "na", "para", "após", "antes", "depois"}),
    "en": frozenset(),
}

DATE_PREPOSITIONS = {
    "es": frozenset({"en", "el"}),
    "pt-BR": frozenset({"em", "no", "na"}),
    "en": frozenset(),
}

RELATIVE_DAY_LEADS = {
    "es": {"al": "", "el": "", "del": "de"},
    "pt-BR": {"ao": "", "no": "", "do": "de"},
    "en": {"on": ""},
}

PERIOD_PREPOSITIONS = {
    "es": frozenset({"en", "de", "desde", "durante", "entre"}),
    "pt-BR": frozenset({"em", "no", "de", "desde", "durante", "entre"}),
    "en": frozenset({"in", "during", "between"}),
}

UNSEEN_CLAIMS = (
    r"tod[oa]s (ell[oa]s|el[ae]s|hech[oa]s|feit[oa]s|realizad[oa]s|fueron|foram|son|sao|estan|estao"
    r"|en|em|na|no|con|com|por|pela|pelo)",
    r"all (of them|were|are|in|at|made|from|on)",
)

CLOCK_AT = {"es": ("a la", "a las"), "pt-BR": ("à", "às"), "en": ("at", "at")}

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
    "credit_card": {
        "es": ("tarjeta de crédito", "tarjetas de crédito"),
        "pt-BR": ("cartão de crédito", "cartões de crédito"),
        "en": ("credit card", "credit cards"),
    },
    "debit_card": {
        "es": ("tarjeta de débito", "tarjetas de débito"),
        "pt-BR": ("cartão de débito", "cartões de débito"),
        "en": ("debit card", "debit cards"),
    },
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

FEMININE_NOUNS = {
    "es": frozenset({"purchase", "card", "credit_card", "debit_card", "memory"}),
    "pt-BR": frozenset({"purchase", "movement", "memory", "subscription"}),
}

MASCULINE_CHARGE_NOUNS = {
    "es": frozenset({"cargo", "cargos", "movimiento", "movimientos", "pago", "pagos", "cobro", "cobros"}),
    "pt-BR": frozenset({"pagamento", "pagamentos", "movimento", "movimentos", "lancamento", "lancamentos"}),
}
FEMININE_CHARGE_NOUNS = {
    "es": frozenset({"compra", "compras", "transaccion", "transacciones"}),
    "pt-BR": frozenset(
        {"compra", "compras", "cobranca", "cobrancas", "transacao", "transacoes", "movimentacao"}
    ),
}

COUNT_SYNONYMS = {
    "es": "transacción transacciones cargo cargos pago pagos suscripción suscripciones",
    "pt-BR": (
        "transação transações cobrança cobranças pagamento pagamentos assinatura assinaturas "
        "movimento movimentos"
    ),
    "en": "charge charges payment payments subscription subscriptions",
}

COUNT_NOUNS = {
    locale: " ".join(
        [form.split()[0] for forms in NOUNS.values() for form in forms[locale]]
        + COUNT_SYNONYMS[locale].split()
    )
    for locale in LOCALES
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
        "Web": {"es": "por internet", "pt-BR": "pela internet", "en": "online"},
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
        "more": {"es": "más", "pt-BR": "a mais", "en": "more"},
        "less": {"es": "menos", "pt-BR": "a menos", "en": "less"},
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
            "es": "el sistema de alertas del banco emitió una alerta",
            "pt-BR": "o sistema de alertas do banco emitiu um alerta",
            "en": "the bank's alert system raised an alert",
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

NUMBER_VALUES = {
    "es": {word: value for value, word in enumerate(CARDINALS["es"].split(), start=2)},
    "en": {word: value for value, word in enumerate(CARDINALS["en"].split(), start=2)},
    "pt-BR": dict(
        zip(
            CARDINALS["pt-BR"].split(),
            (2, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 14, 15, 16, 17, 18, 19, 20),
            strict=True,
        )
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
        r"desembols\w*",
        r"(llegar|llega|llegue|ocurr|pase|pasar|sucede|suceda|recib)\w* (con )?(el|tu|su) dinero",
        r"(el|tu|su) dinero (va a |vaya a )?(lleg|vuelv|volver|regres)\w*",
        r"(cheg|acontec|receb)\w* (com )?o (seu )?dinheiro",
        r"o (seu )?dinheiro (vai |va )?(cheg|volt|retorn)\w*",
        r"(happens?|arrives?|get) (to |with )?(the|your) money",
        r"(the|your) money (will )?(arriv|return|come)\w*",
        r"devoluci\w*",
        r"devoluc\w*",
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
    "promise_talk": (
        r"promet\w*",
        r"promes\w*",
        r"promis\w*",
        r"no (puedo|podria|sabria) (decir|adelantar|anticipar|asegurar|confirmar|indicar)\w*",
        r"nao (posso|consigo|saberia) (dizer|antecipar|informar|confirmar|assegurar|indicar)\w*",
        r"(cannot|can't|can not) (tell you|say when|confirm when)",
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
    "date_outside_reference": (
        "Write dates only as references like {fN.date}; hoy, ayer, today, weekdays and months are dates "
        "too: reference the fact's date or drop the word."
    ),
    "number_word_outside_reference": "Write counts and ordinals only as references like {fN.count}.",
    "merchant_outside_reference": "Write merchants as references like {fN.merchant} or exactly as stored.",
    "contact_outside_facts": "Remove the phone, URL or email; it is not in the facts.",
    "fraud_word": "Never say fraud; describe what the bank saw instead.",
    "safety_claim": "Never say a charge is safe or legitimate.",
    "money_promise": "Never promise money back; describe the next step of the process instead.",
    "legal_term": "Avoid legal terms; describe the bank's process in plain words.",
    "promise_talk": "Never say what you can or cannot promise; state the bank's process with its citation.",
    "noun_after_count": "A count renders with its noun; remove the noun you wrote after the reference.",
    "view_unknown": "Use one of the view types of the reply tool.",
    "view_fact_unknown": "A view may show only facts a tool returned this turn.",
    "view_fact_unfit": "That fact does not fit this view; see the reply tool for the facts each view takes.",
    "view_empty": "The facts of this view have no rows to show; send the reply without the view.",
    "ask_not_allowed": "That ask is not allowed now; send the reply without the ask.",
    "ask_fact_unknown": "An ask may use only facts a tool returned this turn.",
    "ask_fact_unfit": "That fact cannot be an option of this ask; see the reply tool for each ask.",
    "ask_options_count": (
        "which_one takes two to five candidate facts; show takes exactly one fact. With one candidate, "
        "send no ask and answer about it, with its view."
    ),
    "ask_options_partial": (
        "More charges match than your options; drop the which_one, ask for the date or the amount in say, "
        "and attach the movements view of the search."
    ),
    "unseen_rows_claim": "You saw only some of these rows; say nothing about all of them.",
    "show_with_view": "The view already shows the rows; keep the view and drop the show ask.",
    "movements_beside_spend": (
        "In an answer about a spend, give the spend's own total and count; do not add the count or period of "
        "the movements search, the view shows them."
    ),
    "ask_options_repeated": "Each option of which_one must be a different charge or card.",
    "ask_options_mixed": "The options of which_one must all be charges or all be cards.",
}
