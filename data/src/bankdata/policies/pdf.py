import html
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pymupdf
from core.facts.catalog import COUNTRY_NAMES, MONTHS
from core.facts.check import fold
from markdown_it import MarkdownIt
from weasyprint import HTML

from bankdata.policies.chunk import Chunk
from bankdata.policies.render import RenderedDocument
from bankdata.policies.spec import VERSIONING

TEMPLATE = Path(__file__).parent / "template"
MARKDOWN = MarkdownIt("commonmark", {"html": False})
NON_WORD = re.compile(r"[^a-z0-9]+")
MARKUP = re.compile(r"(\*\*|__|\*|_|`|^#+\s|^\s*[-+]\s|^\s*\d+\.\s)", re.MULTILINE)
OPENING_WORDS = (8, 5, 3)

TEXTS = {
    "es": {
        "version": "Versión {version} · Parámetros {facts}",
        "effective": "Vigente desde el {date}",
        "footer": "{title} · Versión {version} · Vigente desde el {date}",
        "synthetic": "Documento de un banco ficticio, con cifras ficticias, para demostración.",
        "versioning": (
            "Este documento es la versión {version}, vigente desde el {date}. "
            "Sus cifras corresponden a la versión {facts} de los parámetros del banco para {country}.\n\n"
            "Cada versión nueva reemplaza a la anterior desde su fecha de vigencia. "
            "Las versiones anteriores siguen disponibles en su propia dirección, "
            "de modo que una referencia a una versión anterior siempre abre el texto que citaba."
        ),
    },
    "pt-BR": {
        "version": "Versão {version} · Parâmetros {facts}",
        "effective": "Vigente desde {date}",
        "footer": "{title} · Versão {version} · Vigente desde {date}",
        "synthetic": "Documento de um banco fictício, com valores fictícios, para demonstração.",
        "versioning": (
            "Este documento é a versão {version}, vigente desde {date}. "
            "Seus valores correspondem à versão {facts} dos parâmetros do banco para {country}.\n\n"
            "Cada nova versão substitui a anterior a partir da data de vigência. "
            "As versões anteriores continuam disponíveis em seu próprio endereço, "
            "para que uma referência a uma versão anterior sempre abra o texto citado."
        ),
    },
    "en": {
        "version": "Version {version} · Parameters {facts}",
        "effective": "Effective {date}",
        "footer": "{title} · Version {version} · Effective {date}",
        "synthetic": "A document of a fictional bank, with fictional figures, for demonstration.",
        "versioning": (
            "This document is version {version}, effective {date}. "
            "Its figures come from version {facts} of the bank's parameters for {country}.\n\n"
            "Each new version replaces the previous one from its effective date. "
            "Earlier versions stay available at their own address, "
            "so a reference to an earlier version always opens the text it cited."
        ),
    },
}


@dataclass(frozen=True)
class Pdf:
    data: bytes
    section_pages: dict[int, int]
    pages: dict[tuple[int, int], tuple[int, int]]
    page_count: int


def long_date(day: date, locale: str) -> str:
    month = MONTHS[locale][day.month - 1]
    if locale == "en":
        return f"{month.capitalize()} {day.day}, {day.year}"
    return f"{day.day} de {month} de {day.year}"


def to_html(document: RenderedDocument) -> str:
    locale = document.locale
    texts = TEXTS[locale]
    values = {
        "title": document.title,
        "version": document.version,
        "facts": document.facts.version,
        "date": long_date(document.effective_date, locale),
        "country": COUNTRY_NAMES[document.country][locale],
    }
    sections = [(section.number, section.heading, section.text) for section in document.sections]
    if document.doc_type == "policy":
        sections.append((len(sections) + 1, VERSIONING[locale], texts["versioning"].format(**values)))
    body = "".join(
        f'<h2 id="s{number}"><span class="number">{number}.</span>{html.escape(heading)}</h2>'
        + MARKDOWN.render(text)
        for number, heading, text in sections
    )
    footer = texts["footer"].format(**values).replace("\\", "\\\\").replace('"', '\\"')
    return (
        f'<!doctype html><html lang="{html.escape(document.language)}"><head><meta charset="utf-8">'
        f"<title>{html.escape(document.title)}</title>"
        '<link rel="stylesheet" href="style.css">'
        f'<style>@page {{ @bottom-left {{ content: "{footer}"; }} }}</style></head><body>'
        '<section class="cover"><div class="brand"><img src="logo.svg" alt="">LATAM Bank</div>'
        f"<h1>{html.escape(document.title)}</h1>"
        f'<div class="country">{html.escape(str(values["country"]))}</div>'
        f'<div class="edition">{html.escape(texts["version"].format(**values))}<br>'
        f"{html.escape(texts['effective'].format(**values))}"
        f'<div class="synthetic">{html.escape(texts["synthetic"])}</div></div></section>'
        f"{body}</body></html>"
    )


def render_pdf(document: RenderedDocument, chunks: list[Chunk]) -> Pdf:
    rendered = HTML(string=to_html(document), base_url=str(TEMPLATE)).render()
    section_pages: dict[int, int] = {}
    for number, page in enumerate(rendered.pages, start=1):
        for anchor in page.anchors:
            if anchor.startswith("s") and anchor[1:].isdigit():
                section_pages.setdefault(int(anchor[1:]), number)
    data = rendered.write_pdf()
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        texts = [_plain(page.get_text()) for page in pdf]
    pages = {(chunk.section, chunk.number): _locate(chunk, section_pages, texts) for chunk in chunks}
    return Pdf(data, section_pages, pages, len(texts))


def _locate(chunk: Chunk, section_pages: dict[int, int], texts: list[str]) -> tuple[int, int]:
    first = section_pages[chunk.section]
    following = [page for number, page in section_pages.items() if number > chunk.section]
    last = min(following) if following else len(texts)
    words = _plain(MARKUP.sub(" ", chunk.text)).split()
    start = _find(words, first, last, texts, opening=True) or first
    end = _find(words, start, last, texts, opening=False) or start
    return start, end


def _find(words: list[str], first: int, last: int, texts: list[str], opening: bool) -> int | None:
    for count in OPENING_WORDS:
        probe = " ".join(words[:count] if opening else words[-count:])
        for page in range(first, last + 1):
            if probe and f" {probe} " in f" {texts[page - 1]} ":
                return page
    return None


def _plain(text: str) -> str:
    return " ".join(NON_WORD.sub(" ", fold(text)).split())
