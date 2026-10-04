from core.facts.parts import Say
from core.facts.values import Fact

FIXED: dict[str, dict[str, str]] = {
    "consent_block": {
        "es": "Puedo bloquear tu tarjeta {k.last4} ahora, para que nadie más pueda comprar con ella. "
        "Desbloquearla después lo hace una persona del banco.",
        "pt-BR": "Posso bloquear seu cartão {k.last4} agora, para que ninguém mais compre com ele. "
        "Desbloqueá-lo depois é com uma pessoa do banco.",
        "en": "I can block your card {k.last4} now, so no one else can buy with it. "
        "Unblocking it later is done by a person at the bank.",
    },
    "consent_claim": {
        "es": "Puedo abrir una aclaración por tu cargo en {c.charge.merchant} por {c.charge.amount}. "
        "Una persona del banco la revisará.",
        "pt-BR": "Posso abrir uma contestação da cobrança em {c.charge.merchant} de {c.charge.amount}. "
        "Uma pessoa do banco vai analisá-la.",
        "en": "I can open a dispute for your charge at {c.charge.merchant} for {c.charge.amount}. "
        "A person at the bank will review it.",
    },
    "have_card": {
        "es": "Gracias por contarme. Antes de seguir, necesito saber algo de tu tarjeta.",
        "pt-BR": "Obrigada por me contar. Antes de seguir, preciso saber algo sobre o seu cartão.",
        "en": "Thank you for telling me. Before we go on, I need to know something about your card.",
    },
    "blocked": {
        "es": "Listo: tu tarjeta {k.last4} quedó bloqueada, y lo confirmé en tu cuenta.",
        "pt-BR": "Pronto: seu cartão {k.last4} foi bloqueado, e eu confirmei isso na sua conta.",
        "en": "Done: your card {k.last4} is blocked, and I confirmed it in your account.",
    },
    "blocked_before": {
        "es": "Tu tarjeta {k.last4} ya estaba bloqueada, así que no hice nada más en ella.",
        "pt-BR": "Seu cartão {k.last4} já estava bloqueado, então não fiz mais nada nele.",
        "en": "Your card {k.last4} was already blocked, so I did nothing else to it.",
    },
    "block_unconfirmed": {
        "es": "No pude confirmar el bloqueo de tu tarjeta {k.last4}, así que no lo doy por hecho.",
        "pt-BR": "Não consegui confirmar o bloqueio do seu cartão {k.last4}, então não o dou como feito.",
        "en": "I could not confirm the block of your card {k.last4}, so I do not count it as done.",
    },
    "case_opened": {
        "es": "Abrí el caso {s.case_id} con lo que revisamos. Te contactará una persona del banco, "
        "y esto es lo que ya sabe.",
        "pt-BR": "Abri o caso {s.case_id} com o que verificamos. Uma pessoa do banco vai entrar em contato, "
        "e isto é o que ela já sabe.",
        "en": "I opened case {s.case_id} with what we checked. A person at the bank will contact you, "
        "and this is what they already know.",
    },
    "claim_opened": {
        "es": "Abrí tu aclaración {s.case_id}; esto es lo que queda registrado.",
        "pt-BR": "Abri sua contestação {s.case_id}; isto é o que fica registrado.",
        "en": "I opened your dispute {s.case_id}; this is what is on record.",
    },
    "case_unconfirmed": {
        "es": "No pude confirmar que el caso quedó abierto. Llama al banco al {p.phone} ({p.phone_schedule}) "
        "y cuéntales lo que pasó.",
        "pt-BR": "Não consegui confirmar que o caso foi aberto. Ligue para o banco no {p.phone} "
        "({p.phone_schedule}) e conte o que aconteceu.",
        "en": "I could not confirm that the case is open. Call the bank at {p.phone} ({p.phone_schedule}) "
        "and tell them what happened.",
    },
    "card_blocked_offer": {
        "es": "Tu tarjeta {k.last4} ya está bloqueada, así que no hace falta bloquearla otra vez. "
        "Puedo pasarte con una persona del banco para que revise lo que pasó.",
        "pt-BR": "Seu cartão {k.last4} já está bloqueado, então não é preciso bloqueá-lo de novo. "
        "Posso passar você para uma pessoa do banco revisar o que aconteceu.",
        "en": "Your card {k.last4} is already blocked, so there is no need to block it again. "
        "I can hand you to a person at the bank to review what happened.",
    },
    "lost": {
        "es": "Vamos a proteger tu tarjeta. Elige cuál perdiste o te robaron.",
        "pt-BR": "Vamos proteger seu cartão. Escolha qual você perdeu ou foi roubado.",
        "en": "Let's protect your card. Pick the one you lost or that was stolen.",
    },
    "lost_none": {
        "es": "Todas tus tarjetas ya están bloqueadas. Puedo pasarte con una persona del banco para que "
        "revise lo que pasó.",
        "pt-BR": "Todos os seus cartões já estão bloqueados. Posso passar você para uma pessoa do banco "
        "revisar o que aconteceu.",
        "en": "All your cards are already blocked. I can hand you to a person at the bank to review "
        "what happened.",
    },
    "already": {
        "es": "Ya me habías respondido sobre este cargo, así que lo dejo como me dijiste.",
        "pt-BR": "Você já tinha me respondido sobre esta cobrança, então deixo como você me disse.",
        "en": "You had already answered me about this charge, so I keep it as you told me.",
    },
    "not_me": {
        "es": "Vamos a proteger tu tarjeta. Elige el movimiento que no hiciste; si no está, dime su fecha "
        "o su monto.",
        "pt-BR": "Vamos proteger seu cartão. Escolha a movimentação que você não fez; se não estiver aqui, "
        "me diga a data ou o valor.",
        "en": "Let's protect your card. Pick the transaction you did not make; if it is not here, tell me "
        "its date or amount.",
    },
}

COMPOSED: dict[str, dict[str, str]] = {
    "recognized": {
        "es": "Gracias, lo anoto: reconoces este cargo y no volveré a preguntarte por él.",
        "pt-BR": "Obrigada, anotei: você reconhece esta cobrança e não vou perguntar de novo sobre ela.",
        "en": "Thank you, noted: you recognize this charge and I will not ask you about it again.",
    },
    "why_asked": {
        "es": "Te pregunto por tu compra en {c.charge.merchant} porque el banco notó esto: "
        "{c.verdict.reasons}.",
        "pt-BR": "Pergunto sobre sua compra em {c.charge.merchant} porque o banco notou isto: "
        "{c.verdict.reasons}.",
        "en": "I am asking about your purchase at {c.charge.merchant} because the bank noticed this: "
        "{c.verdict.reasons}.",
    },
    "declined_block": {
        "es": "Está bien, no la bloqueo. Si cambias de opinión, escríbeme.",
        "pt-BR": "Tudo bem, não vou bloqueá-lo. Se mudar de ideia, me escreva.",
        "en": "All right, I will not block it. If you change your mind, write to me.",
    },
    "declined_claim": {
        "es": "Está bien, no abro la aclaración. Si cambias de opinión, escríbeme.",
        "pt-BR": "Tudo bem, não vou abrir a contestação. Se mudar de ideia, me escreva.",
        "en": "All right, I will not open the dispute. If you change your mind, write to me.",
    },
    "declined_person": {
        "es": "Está bien. Si lo necesitas, escríbeme y te paso con una persona del banco.",
        "pt-BR": "Tudo bem. Se precisar, me escreva e eu passo você para uma pessoa do banco.",
        "en": "All right. If you need it, write to me and I will hand you to a person at the bank.",
    },
    "abstain_unblock": {
        "es": "Desbloquear una tarjeta lo hace una persona del banco.",
        "pt-BR": "Desbloquear um cartão é com uma pessoa do banco.",
        "en": "Unblocking a card is done by a person at the bank.",
    },
    "abstain_refund": {
        "es": "Lo que pasa con tu dinero lo decide una persona del banco.",
        "pt-BR": "O que acontece com o seu dinheiro é decidido por uma pessoa do banco.",
        "en": "What happens with your money is decided by a person at the bank.",
    },
    "abstain_human": {
        "es": "Claro, una persona del banco puede ayudarte con esto.",
        "pt-BR": "Claro, uma pessoa do banco pode ajudar você com isso.",
        "en": "Of course, a person at the bank can help you with this.",
    },
}


def fixed(key: str, locale: str, **bound: Fact) -> Say:
    return Say(bind(FIXED[key][locale], **bound))


def template(key: str, locale: str, **bound: Fact) -> Say:
    return Say(bind(COMPOSED[key][locale], **bound))


def bind(text: str, **bound: Fact) -> str:
    for alias, fact in bound.items():
        text = text.replace("{" + alias + ".", "{" + fact.id + ".")
    return text
