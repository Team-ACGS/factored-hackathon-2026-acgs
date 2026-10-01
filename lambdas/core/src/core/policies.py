import json
import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from functools import cache
from importlib.resources import files
from typing import Any

from core.facts.values import Channel, Count, Labels, Money, Percent, Status, Url, Value

COUNTRIES = ("MX", "CO", "AR", "PE", "BR", "US")
LANGUAGES = {"MX": "es-MX", "CO": "es-CO", "AR": "es-AR", "PE": "es-PE", "BR": "pt-BR", "US": "en-US"}
DOC_TYPES = ("policy", "procedure", "guide", "faq", "glossary")

TOPICS: dict[str, tuple[str, str]] = {
    "unrecognized_charge_rights": ("disputes", "policy"),
    "dispute_lifecycle": ("disputes", "procedure"),
    "unrecognized_charge_guide": ("disputes", "guide"),
    "dispute_deadlines": ("disputes", "policy"),
    "special_purchase_disputes": ("disputes", "guide"),
    "unrecognized_charges_faq": ("disputes", "faq"),
    "disputes_glossary": ("disputes", "glossary"),
    "lost_or_stolen_card": ("card_security", "guide"),
    "card_blocking": ("card_security", "policy"),
    "card_replacement": ("card_security", "policy"),
    "blocked_card_effects": ("card_security", "guide"),
    "transaction_alerts": ("card_security", "guide"),
    "unauthorized_use_liability": ("card_security", "policy"),
    "transaction_statuses": ("transactions", "guide"),
    "pending_charges": ("transactions", "guide"),
    "reversals_and_duplicates": ("transactions", "policy"),
    "recurring_payments": ("transactions", "guide"),
    "assistant_handoff": ("service", "procedure"),
    "assistant_scope": ("service", "policy"),
    "deadlines_calendar": ("service", "policy"),
}
GROUPS = ("disputes", "card_security", "transactions", "service")

PLACEHOLDER = re.compile(r"\{\{policy\.([a-z_]+\.[a-z_]+)\}\}")


class UnknownFigure(ValueError):
    pass


@dataclass(frozen=True)
class CountryFacts:
    country: str
    version: int
    language: str
    currency: str
    specs: Mapping[str, Mapping[str, Any]]

    def figure(self, key: str) -> Value:
        spec = self.specs.get(key)
        if spec is None:
            raise UnknownFigure(f"{self.country}: policy.{key}")
        return figure(spec)

    def verified(self, key: str) -> bool:
        return bool(self.specs[key].get("verified", True))


@cache
def policy_facts() -> dict[str, CountryFacts]:
    raw = tomllib.loads(files("core").joinpath("policy_facts.toml").read_text(encoding="utf-8"))
    return {country: _country(country, raw[country]) for country in COUNTRIES}


def _country(country: str, table: Mapping[str, Any]) -> CountryFacts:
    specs = {
        f"{group}.{key}": spec
        for group, entries in table.items()
        if isinstance(entries, dict)
        for key, spec in entries.items()
    }
    return CountryFacts(country, int(table["version"]), str(table["language"]), str(table["currency"]), specs)


def figure(spec: Mapping[str, Any]) -> Value:
    match spec["type"]:
        case "count":
            return Count(int(spec["value"]), str(spec["noun"]))
        case "money":
            return Money(Decimal(str(spec["amount"])), str(spec["currency"]))
        case "percent":
            return Percent(Decimal(str(spec["value"])))
        case "channel":
            return Channel(str(spec["kind"]), str(spec["value"]))
        case "url":
            return Url(str(spec["value"]))
        case "status":
            return Status(str(spec["domain"]), str(spec["value"]))
        case "enum_list":
            return Labels(str(spec["domain"]), tuple(str(value) for value in spec["values"]))
    raise UnknownFigure(str(spec["type"]))


def encode_figures(specs: Mapping[str, Mapping[str, Any]]) -> str:
    return json.dumps(dict(sorted(specs.items())), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def decode_figures(encoded: str) -> dict[str, Mapping[str, Any]]:
    decoded = json.loads(encoded) if encoded else {}
    if not isinstance(decoded, dict):
        raise ValueError("figures is not an object")
    return decoded


def doc_id(country: str, topic: str) -> str:
    return f"{country.lower()}-{topic.replace('_', '-')}"


def edition(document: str, version: int, facts_version: int) -> str:
    return f"{document}-v{version}-f{facts_version}"


def chunk_id(document: str, version: int, facts_version: int, section: int, chunk: int) -> str:
    return f"{edition(document, version, facts_version)}-s{section}-c{chunk}"


def pdf_key(country: str, document: str, version: int, facts_version: int) -> str:
    return f"{country}/{edition(document, version, facts_version)}.pdf"


def pdf_url(domain: str, key: str, page: int | None = None) -> str:
    url = f"https://{domain}/{key}"
    return url if page is None else f"{url}#page={page}"
