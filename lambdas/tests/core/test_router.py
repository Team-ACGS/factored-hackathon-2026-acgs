import pytest

from core.router import Route, floor, route

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
