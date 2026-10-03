"""The turn's only two Bedrock call sites: slot extraction and composition.

Both are optional and both fail soft: on any error (throttling, a bad model
response, anything) they return ``None`` and the caller falls back to the
deterministic path (a rule in `turn.classify`/`turn.decide`, or
`core.facts.fallback`). This is the "one language model, Sonnet 5 at low
effort" decision from docs/ARD.md: the turn never makes a second guess with
a second model, it falls back to a template instead.

``compose`` asks the model to answer using exactly the reference syntax
`core.facts.render`/`core.facts.check` already understand (``{fN.field}``,
``{pN.field}``, ``[p:chunk_id]``), so the exact same deterministic grounding
check the rest of the turn relies on also covers the LLM's output. The model
never gets to invent a figure, a date or a merchant name that is not already
in the ledger.
"""

from __future__ import annotations

import json
import os
import re

from botocore.exceptions import BotoCoreError, ClientError

from core.facts import Ledger, Part, Say
from core.observability import logger
from core.vectors import bedrock_runtime

MAX_TOKENS_EXTRACT = 200
MAX_TOKENS_COMPOSE = 400

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)

_EXTRACT_SYSTEM = (
    'Return only a JSON object {"merchant": string|null} with the name of the '
    "merchant the customer's message mentions, or null if it mentions none. "
    "Do not add anything else."
)

_COMPOSE_SYSTEM = (
    "You draft one or two sentences for a bank's chat assistant, in locale '{locale}'. "
    "Use ONLY these references for any fact: {{fN.field}} or {{pN.field}}, where fN/pN "
    "are the ids in the ledger given to you, and cite every policy excerpt you use with "
    "[p:chunk_id] right after the sentence that uses it. Never state a number, date, "
    'name or figure that is not one of those references. Return only {{"say": string}}.'
)


def _invoke(system: str, user: str, max_tokens: int) -> str | None:
    try:
        client = bedrock_runtime()
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": [{"type": "text", "text": user}]}],
        }
        response = client.invoke_model(
            modelId=os.environ["BEDROCK_MODEL_ID"],
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )
        payload = json.loads(response["body"].read())
        texts = [block["text"] for block in payload["content"] if block.get("type") == "text"]
        return texts[0] if texts else None
    except (ClientError, BotoCoreError, KeyError, ValueError, json.JSONDecodeError) as error:
        logger.warning("bedrock call failed, falling back to a deterministic reply", error=str(error))
        return None


def _json_object(text: str) -> dict[str, object] | None:
    match = _JSON_BLOCK.search(text)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def extract_merchant(message_text: str, locale: str) -> str | None:
    """LLM-conditional slot: a merchant name free text mentions.

    Only called by `turn.extract` when the deterministic catalog lookup
    (`lexicon.mentioned_merchant`) found nothing.
    """
    text = _invoke(_EXTRACT_SYSTEM, message_text, MAX_TOKENS_EXTRACT)
    if text is None:
        return None
    parsed = _json_object(text)
    merchant = parsed.get("merchant") if parsed else None
    return merchant if isinstance(merchant, str) and merchant.strip() else None


def compose(message_text: str, ledger: Ledger, locale: str) -> list[Part] | None:
    """Drafts a grounded answer, or ``None`` if Bedrock failed or did not
    follow the reference format. The caller (`turn.compose`) still runs the
    result through `core.facts.check` before trusting it."""
    system = _COMPOSE_SYSTEM.format(locale=locale)
    user = f"Customer message: {message_text}\n\nLedger: {json.dumps(ledger.payload(), ensure_ascii=False)}"
    text = _invoke(system, user, MAX_TOKENS_COMPOSE)
    if text is None:
        return None
    parsed = _json_object(text)
    say = parsed.get("say") if parsed else None
    if not isinstance(say, str) or not say.strip():
        return None
    return [Say(say)]
