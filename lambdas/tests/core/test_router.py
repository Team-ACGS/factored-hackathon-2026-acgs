import pytest

from core.router import Route, abstain, floor, route, short_answer

PHRASES = [
    ("No fui yo, ¿qué es este cargo?", "not_me"),
    ("YO NO FUÍ", "not_me"),
    ("Não fui eu!", "not_me"),
    ("eu não fiz essa compra", "not_me"),
    ("that wasn't me", "not_me"),
    ("Me robaron la tarjeta en el bus", "lost_stolen"),
    ("perdí mi tarjeta", "lost_stolen"),
    ("me roubaram ontem", "lost_stolen"),
    ("my card was stolen", "lost_stolen"),
    ("perdí la tarjeta ayer", "lost_stolen"),
    ("Se me perdió la tarjeta", "lost_stolen"),
    ("perdi o cartão no ônibus", "lost_stolen"),
    ("roubaram o cartão", "lost_stolen"),
    ("roubaram o meu cartão", "lost_stolen"),
    ("fui roubado", "lost_stolen"),
    ("fui roubada no centro", "lost_stolen"),
]


@pytest.mark.parametrize(("text", "kind"), PHRASES)
def test_a_safety_phrase_raises_the_floor_on_the_raw_text(text: str, kind: str) -> None:
    assert floor(text) == kind
    assert route(text) == Route("safety", kind)


@pytest.mark.parametrize(
    "text",
    [
        "¿Cuánto gasté en Primax este mes vs el pasado?",
        "no reconozco este cargo",
        "nofuiyo",
        "quiero hablar con una persona",
        "¿cuándo me devuelven la plata de mi aclaración?",
    ],
)
def test_everything_else_goes_to_the_graph(text: str) -> None:
    assert route(text) == Route("open_mode")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Sí", ("yes", "")),
        ("sí, era la gasolina del viaje", ("yes", "era la gasolina del viaje")),
        ("¡Sí, fui yo!", ("yes", "")),
        ("Sim, fui eu. Comprei no aeroporto", ("yes", "Comprei no aeroporto")),
        ("no, nunca compré ahí", ("no", "nunca compré ahí")),
        ("Não reconheço", ("no", "")),
        ("No lo reconozco\nnunca fui", ("no", "nunca fui")),
        ("si no lo reconozco, ¿qué hago?", None),
        ("¿sí?", None),
        ("no sé", None),
        ("creo que sí", None),
        ("sí era la gasolina", None),
        ("sí, no fui yo", None),
        ("sí, me robaron la tarjeta", None),
        ("sí, no lo reconozco", None),
        ("no, sí fui yo", None),
        ("Sí, ¿pero cuándo fue?", None),
    ],
)
def test_only_a_short_unambiguous_answer_at_the_start_closes_an_ask(
    text: str, expected: tuple[str, str] | None
) -> None:
    assert short_answer(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Desbloquea mi tarjeta", "unblock"),
        ("¿me la pueden desbloquear?", "unblock"),
        ("desbloqueia meu cartão", "unblock"),
        ("¿cuándo me devuelven la plata?", "refund"),
        ("quero meu dinheiro de volta", "refund"),
        ("quando vou receber o dinheiro da minha contestação?", "refund"),
        ("can I get a refund", "refund"),
        ("quiero hablar con una persona", "human"),
        ("quero falar com uma pessoa", "human"),
        ("¿cuánto gasté en Primax este mes?", None),
        ("¿qué es este cargo?", None),
    ],
)
def test_the_abstention_lexicon_names_what_only_a_person_does(text: str, expected: str | None) -> None:
    assert abstain(text) == expected
