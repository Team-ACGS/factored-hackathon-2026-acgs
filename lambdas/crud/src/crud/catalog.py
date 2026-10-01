from dataclasses import dataclass
from datetime import timezone
from decimal import Decimal
from enum import StrEnum

from core.countries import zone


class Archetype(StrEnum):
    GROCERY = "grocery"
    CONVENIENCE = "convenience"
    PHARMACY = "pharmacy"
    FUEL = "fuel"
    RIDE = "ride"
    DELIVERY = "delivery"
    STREAMING = "streaming"
    CINEMA = "cinema"
    TELECOM = "telecom"
    RETAIL = "retail"
    AIRLINE = "airline"
    COFFEE = "coffee"


@dataclass(frozen=True)
class Profile:
    category: str
    channel: str
    usd_low: float
    usd_high: float
    weight: int
    recurring: bool = False


PROFILES: dict[Archetype, Profile] = {
    Archetype.GROCERY: Profile("Food", "POS", 15, 120, 14),
    Archetype.CONVENIENCE: Profile("Food", "POS", 2, 15, 12),
    Archetype.PHARMACY: Profile("Health", "POS", 5, 60, 6),
    Archetype.FUEL: Profile("Transport", "POS", 20, 70, 8),
    Archetype.RIDE: Profile("Transport", "App", 3, 25, 12),
    Archetype.DELIVERY: Profile("Food", "App", 8, 40, 11),
    Archetype.STREAMING: Profile("Entertainment", "Web", 8, 18, 1, recurring=True),
    Archetype.CINEMA: Profile("Entertainment", "POS", 6, 30, 3),
    Archetype.TELECOM: Profile("Services", "Web", 15, 50, 1, recurring=True),
    Archetype.RETAIL: Profile("Shopping", "POS", 25, 250, 6),
    Archetype.AIRLINE: Profile("Travel", "Web", 80, 450, 1),
    Archetype.COFFEE: Profile("Food", "POS", 3, 10, 12),
}


@dataclass(frozen=True)
class Merchant:
    name: str
    archetype: Archetype

    @property
    def profile(self) -> Profile:
        return PROFILES[self.archetype]


@dataclass(frozen=True)
class Country:
    code: str
    currency: str
    usd_rate: Decimal
    rounding: Decimal
    cities: tuple[str, ...]
    merchants: tuple[Merchant, ...]

    @property
    def zone(self) -> timezone:
        return zone(self.code)


def _merchants(names: dict[Archetype, str]) -> tuple[Merchant, ...]:
    return tuple(Merchant(name, archetype) for archetype, name in names.items())


COUNTRIES: dict[str, Country] = {
    country.code: country
    for country in (
        Country(
            code="PE",
            currency="PEN",
            usd_rate=Decimal("3.75"),
            rounding=Decimal("0.10"),
            cities=("Lima", "Arequipa", "Trujillo", "Cusco"),
            merchants=_merchants(
                {
                    Archetype.GROCERY: "Plaza Vea",
                    Archetype.CONVENIENCE: "Tambo+",
                    Archetype.PHARMACY: "Inkafarma",
                    Archetype.FUEL: "Primax",
                    Archetype.RIDE: "Cabify",
                    Archetype.DELIVERY: "Rappi",
                    Archetype.STREAMING: "Netflix",
                    Archetype.CINEMA: "Cineplanet",
                    Archetype.TELECOM: "Movistar",
                    Archetype.RETAIL: "Saga Falabella",
                    Archetype.AIRLINE: "LATAM Airlines",
                    Archetype.COFFEE: "Starbucks",
                }
            ),
        ),
        Country(
            code="MX",
            currency="MXN",
            usd_rate=Decimal("18.50"),
            rounding=Decimal("0.50"),
            cities=("Ciudad de México", "Guadalajara", "Monterrey", "Puebla"),
            merchants=_merchants(
                {
                    Archetype.GROCERY: "Walmart Supercenter",
                    Archetype.CONVENIENCE: "OXXO",
                    Archetype.PHARMACY: "Farmacias Guadalajara",
                    Archetype.FUEL: "Pemex",
                    Archetype.RIDE: "Uber",
                    Archetype.DELIVERY: "Rappi",
                    Archetype.STREAMING: "Netflix",
                    Archetype.CINEMA: "Cinépolis",
                    Archetype.TELECOM: "Telcel",
                    Archetype.RETAIL: "Liverpool",
                    Archetype.AIRLINE: "Aeroméxico",
                    Archetype.COFFEE: "Starbucks",
                }
            ),
        ),
        Country(
            code="CO",
            currency="COP",
            usd_rate=Decimal("4100"),
            rounding=Decimal("100"),
            cities=("Bogotá", "Medellín", "Cali", "Barranquilla"),
            merchants=_merchants(
                {
                    Archetype.GROCERY: "Éxito",
                    Archetype.CONVENIENCE: "D1",
                    Archetype.PHARMACY: "Drogas La Rebaja",
                    Archetype.FUEL: "Terpel",
                    Archetype.RIDE: "DiDi",
                    Archetype.DELIVERY: "Rappi",
                    Archetype.STREAMING: "Netflix",
                    Archetype.CINEMA: "Cine Colombia",
                    Archetype.TELECOM: "Claro",
                    Archetype.RETAIL: "Falabella",
                    Archetype.AIRLINE: "Avianca",
                    Archetype.COFFEE: "Juan Valdez Café",
                }
            ),
        ),
        Country(
            code="AR",
            currency="ARS",
            usd_rate=Decimal("1400"),
            rounding=Decimal("10"),
            cities=("Buenos Aires", "Córdoba", "Rosario", "Mendoza"),
            merchants=_merchants(
                {
                    Archetype.GROCERY: "Carrefour",
                    Archetype.CONVENIENCE: "Coto",
                    Archetype.PHARMACY: "Farmacity",
                    Archetype.FUEL: "YPF",
                    Archetype.RIDE: "Cabify",
                    Archetype.DELIVERY: "PedidosYa",
                    Archetype.STREAMING: "Netflix",
                    Archetype.CINEMA: "Cinemark Hoyts",
                    Archetype.TELECOM: "Personal",
                    Archetype.RETAIL: "Mercado Libre",
                    Archetype.AIRLINE: "Aerolíneas Argentinas",
                    Archetype.COFFEE: "Café Martínez",
                }
            ),
        ),
        Country(
            code="US",
            currency="USD",
            usd_rate=Decimal("1"),
            rounding=Decimal("0.01"),
            cities=("New York", "Miami", "Houston", "Los Angeles"),
            merchants=_merchants(
                {
                    Archetype.GROCERY: "Whole Foods Market",
                    Archetype.CONVENIENCE: "7-Eleven",
                    Archetype.PHARMACY: "CVS Pharmacy",
                    Archetype.FUEL: "Shell",
                    Archetype.RIDE: "Uber",
                    Archetype.DELIVERY: "DoorDash",
                    Archetype.STREAMING: "Netflix",
                    Archetype.CINEMA: "AMC Theatres",
                    Archetype.TELECOM: "Verizon",
                    Archetype.RETAIL: "Target",
                    Archetype.AIRLINE: "Delta Air Lines",
                    Archetype.COFFEE: "Starbucks",
                }
            ),
        ),
        Country(
            code="BR",
            currency="BRL",
            usd_rate=Decimal("5.40"),
            rounding=Decimal("0.01"),
            cities=("São Paulo", "Rio de Janeiro", "Belo Horizonte", "Curitiba"),
            merchants=_merchants(
                {
                    Archetype.GROCERY: "Pão de Açúcar",
                    Archetype.CONVENIENCE: "Oxxo Brasil",
                    Archetype.PHARMACY: "Drogasil",
                    Archetype.FUEL: "Ipiranga",
                    Archetype.RIDE: "99",
                    Archetype.DELIVERY: "iFood",
                    Archetype.STREAMING: "Netflix",
                    Archetype.CINEMA: "Cinemark",
                    Archetype.TELECOM: "Vivo",
                    Archetype.RETAIL: "Magazine Luiza",
                    Archetype.AIRLINE: "LATAM Airlines",
                    Archetype.COFFEE: "Starbucks",
                }
            ),
        ),
    )
}

LANGUAGES = ("en", "es", "pt-BR")


@dataclass(frozen=True)
class OnlineMerchant:
    name: str
    category: str
    usd_low: float
    usd_high: float


SUSPICIOUS_POOL: tuple[OnlineMerchant, ...] = (
    OnlineMerchant("ALIEXPRESS", "Shopping", 20, 180),
    OnlineMerchant("SHEIN.COM", "Shopping", 25, 150),
    OnlineMerchant("TEMU.COM", "Shopping", 15, 120),
    OnlineMerchant("STEAMGAMES.COM", "Entertainment", 10, 90),
    OnlineMerchant("G2A.COM", "Entertainment", 15, 110),
    OnlineMerchant("PLAYSTATION NETWORK", "Entertainment", 10, 80),
    OnlineMerchant("NORDVPN.COM", "Services", 12, 130),
    OnlineMerchant("BINANCE.COM", "Services", 50, 400),
    OnlineMerchant("PAYPAL *EBAY", "Shopping", 30, 300),
    OnlineMerchant("BOOKING.COM", "Travel", 90, 450),
    OnlineMerchant("APPLE.COM/BILL", "Services", 5, 60),
    OnlineMerchant("GOOGLE *PLAY", "Entertainment", 5, 60),
)

MAX_PURCHASE_USD = max(
    *(profile.usd_high for profile in PROFILES.values()),
    *(merchant.usd_high for merchant in SUSPICIOUS_POOL),
)
