from dataclasses import dataclass

FIELDS = ("doc_id", "title", "language", "topic", "doc_type", "version", "effective_date")

HEADINGS: dict[str, dict[str, tuple[str, ...]]] = {
    "policy": {
        "es": (
            "Propósito",
            "Alcance",
            "Definiciones",
            "Principios",
            "Reglas",
            "Derechos del cliente",
            "Obligaciones del banco",
            "Excepciones",
            "Plazos",
            "Marco regulatorio",
        ),
        "pt-BR": (
            "Objetivo",
            "Abrangência",
            "Definições",
            "Princípios",
            "Regras",
            "Direitos do cliente",
            "Obrigações do banco",
            "Exceções",
            "Prazos",
            "Base regulatória",
        ),
        "en": (
            "Purpose",
            "Scope",
            "Definitions",
            "Principles",
            "Rules",
            "Customer rights",
            "Bank obligations",
            "Exceptions",
            "Deadlines",
            "Regulatory basis",
        ),
    },
    "procedure": {
        "es": (
            "Propósito",
            "Participantes",
            "Condiciones previas",
            "Pasos",
            "Puntos de decisión",
            "Plazos por paso",
            "Evidencia",
            "Resultados",
            "Escalamiento",
            "Registros",
        ),
        "pt-BR": (
            "Objetivo",
            "Participantes",
            "Pré-requisitos",
            "Etapas",
            "Pontos de decisão",
            "Prazos por etapa",
            "Evidências",
            "Resultados",
            "Escalonamento",
            "Registros",
        ),
        "en": (
            "Purpose",
            "Actors",
            "Preconditions",
            "Steps",
            "Decision points",
            "Deadlines per step",
            "Evidence",
            "Outcomes",
            "Escalation",
            "Records",
        ),
    },
    "guide": {
        "es": (
            "Qué es",
            "Cuándo aplica",
            "Qué hacer",
            "Qué sigue",
            "Tiempos",
            "Qué se necesita",
            "Situaciones frecuentes",
            "Dónde pedir ayuda",
        ),
        "pt-BR": (
            "O que é",
            "Quando se aplica",
            "O que fazer",
            "O que acontece depois",
            "Prazos",
            "O que é necessário",
            "Situações comuns",
            "Onde pedir ajuda",
        ),
        "en": (
            "What this is",
            "When it applies",
            "What to do",
            "What happens next",
            "Timelines",
            "What you will need",
            "Common situations",
            "Where to get help",
        ),
    },
}

VERSIONING = {"es": "Control de versiones", "pt-BR": "Controle de versões", "en": "Versioning"}

GLOSSARY_LABELS = {
    "es": ("**Definición:**", "**Ejemplo:**", "**Términos relacionados:**"),
    "pt-BR": ("**Definição:**", "**Exemplo:**", "**Termos relacionados:**"),
    "en": ("**Definition:**", "**Example:**", "**Related terms:**"),
}

DISCLAIMER = {
    "es": "según la lectura que hace el banco de la norma aplicable",
    "pt-BR": "conforme a leitura que o banco faz da norma aplicável",
    "en": "as the bank reads the applicable rule",
}

EXEMPT_WORDS = (r"terceros", r"terceiros", r"third parties")


INFORMAL = {
    "es": ("tú", "tu", "tus", "ti", "te", "contigo", "vos"),
    "pt-BR": ("tu", "teu", "teus", "tua", "tuas", "ti", "contigo"),
}

LITERAL_NAMES = (
    "México",
    "Colombia",
    "Colômbia",
    "Argentina",
    "Perú",
    "Brasil",
    "Brazil",
    "Estados Unidos",
    "United States",
    "mexicano",
    "mexicana",
    "mexicanos",
    "mexicanas",
    "Mexican",
    "Mexicans",
    "colombiano",
    "colombiana",
    "colombianos",
    "colombianas",
    "Colombian",
    "Colombians",
    "argentino",
    "argentinos",
    "argentinas",
    "Argentine",
    "Argentines",
    "Argentinian",
    "Argentinians",
    "peruano",
    "peruana",
    "peruanos",
    "peruanas",
    "Peruvian",
    "Peruvians",
    "brasileño",
    "brasileña",
    "brasileños",
    "brasileñas",
    "brasilero",
    "brasilera",
    "brasileros",
    "brasileras",
    "brasileiro",
    "brasileira",
    "brasileiros",
    "brasileiras",
    "Brazilian",
    "Brazilians",
    "estadounidense",
    "estadounidenses",
    "estadunidense",
    "estadunidenses",
    "norteamericano",
    "norteamericana",
    "norteamericanos",
    "norteamericanas",
    "norte-americano",
    "norte-americana",
    "norte-americanos",
    "norte-americanas",
    "American",
    "Americans",
    "Condusef",
    "Indecopi",
    "Bacen",
    "Procon",
    "Comisión Nacional Bancaria y de Valores",
    "Comisión Nacional para la Protección y Defensa de los Usuarios de Servicios Financieros",
    "Unidad Especializada de Atención a Usuarios",
    "Superintendencia Financiera",
    "Superintendencia de Industria y Comercio",
    "Defensor del Consumidor Financiero",
    "Banco Central de la República Argentina",
    "Dirección Nacional de Defensa del Consumidor",
    "Superintendencia de Banca, Seguros y AFP",
    "Superintendencia de Banca",
    "Instituto Nacional de Defensa de la Competencia y de la Protección de la Propiedad Intelectual",
    "Defensoría del Cliente Financiero",
    "Banco Central do Brasil",
    "Programa de Proteção e Defesa do Consumidor",
    "Consumer Financial Protection Bureau",
    "Office of the Comptroller of the Currency",
    "Comptroller of the Currency",
    "Ley para la Transparencia y Ordenamiento de los Servicios Financieros",
    "Régimen de Protección al Consumidor Financiero",
    "Estatuto del Consumidor",
    "Ley de Tarjetas de Crédito",
    "Reglamento de Tarjetas de Crédito y Débito",
    "Código de Protección y Defensa del Consumidor",
    "Código de Defesa do Consumidor",
    "Truth in Lending Act",
    "Electronic Fund Transfer Act",
    "Fair Credit Billing Act",
    "Regulation Z",
    "Regulation E",
    "Reg Z",
    "Reg E",
)

LITERAL_ACRONYMS = (
    "CNBV",
    "CONDUSEF",
    "UNE",
    "SFC",
    "SIC",
    "BCRA",
    "SBS",
    "INDECOPI",
    "BACEN",
    "CDC",
    "CFPB",
    "OCC",
    "TILA",
    "EFTA",
    "FCBA",
    "EE. UU.",
    "EE.UU.",
    "EEUU",
    "EUA",
    "USA",
    "U.S.A.",
    "U.S.",
    "US",
)


@dataclass(frozen=True)
class Limits:
    section_words: tuple[int, int] = (60, 250)
    document_words: tuple[int, int] = (600, 1050)
    faq_sections: tuple[int, int] = (4, 6)
    faq_questions: tuple[int, int] = (12, 16)
    glossary_sections: tuple[int, int] = (4, 6)
    max_title: int = 90


RENDERABLE = frozenset(
    {
        "section_length",
        "document_length",
        "chunk_length",
        "number_word",
        "raw_date",
        "forbidden_word",
        "register",
        "literal_name",
        "parity",
    }
)


def locale(language: str) -> str:
    return language if language == "pt-BR" else language[:2]
