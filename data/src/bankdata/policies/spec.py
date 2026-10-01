from dataclasses import dataclass

FIELDS = ("doc_id", "title", "country", "language", "topic", "doc_type", "version", "effective_date")

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


@dataclass(frozen=True)
class Limits:
    min_words: int = 300
    max_words: int = 1500
    faq_sections: tuple[int, int] = (6, 10)
    faq_questions: tuple[int, int] = (40, 60)
    glossary_sections: tuple[int, int] = (5, 10)
    max_title: int = 90


SAMPLE_LIMITS = Limits(
    min_words=20, max_words=400, faq_sections=(2, 10), faq_questions=(4, 60), glossary_sections=(2, 10)
)


def locale(language: str) -> str:
    return language if language == "pt-BR" else language[:2]
