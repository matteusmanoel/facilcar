"""OpenAI Vision brief image description — no mechanical / value / accident claims."""

from __future__ import annotations

import base64
import logging
import re
from typing import Any

from sdr.config import get_settings

logger = logging.getLogger(__name__)

# Claims we never allow in outbound descriptions (fabrication / overreach).
FORBIDDEN_CLAIM_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bpre[cç]o\b", re.I),
    re.compile(r"\bvalor\s+(de\s+mercado|venal|fipe)\b", re.I),
    re.compile(r"\bsinistro\b", re.I),
    re.compile(r"\bgarantia\b", re.I),
    re.compile(r"\b(R\$|USD)\s*\d", re.I),
    re.compile(r"\bkm\b|\bquilometragem\b", re.I),
    re.compile(r"\bestado\s+mec[aâ]nico\b", re.I),
    re.compile(r"\bhist[oó]rico\s+de\s+acidente", re.I),
)

SYSTEM_PROMPT = """\
Você descreve imagens enviadas por clientes de uma loja de veículos (WhatsApp).

Regras OBRIGATÓRIAS:
- Descreva apenas o que é VISIVELMENTE observável (tipo de veículo, cor, ângulo, interior/exterior).
- NUNCA afirme estado mecânico, histórico de acidente/sinistro, quilometragem, garantia ou valor de mercado/preço.
- NUNCA invente dados que não aparecem na imagem.
- Resposta: 1–2 frases curtas em pt-BR. Sem listas. Sem markdown.
"""


def _is_unittest_mock(client: Any) -> bool:
    module = type(client).__module__ or ""
    return module.startswith("unittest.mock")


def contains_forbidden_claims(text: str) -> bool:
    """Return True if description includes forbidden fabrication keywords."""
    if not text:
        return False
    return any(p.search(text) for p in FORBIDDEN_CLAIM_PATTERNS)


def sanitize_description(text: str) -> str:
    """Drop sentences that contain forbidden claim patterns."""
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    kept = [p for p in parts if p and not contains_forbidden_claims(p)]
    return " ".join(kept).strip() or "Imagem recebida; descrição objetiva indisponível."


async def describe_image(
    data: bytes,
    *,
    mime_type: str | None = None,
    client: Any | None = None,
) -> str:
    """Return a brief visual description; never claim mechanical state, sinistro, or price."""
    if not data:
        return ""

    settings = get_settings()
    api_key = (settings.openai_api_key or "").strip()
    mime = mime_type or "image/jpeg"

    if client is None:
        if not api_key:
            logger.warning("describe_image: no OPENAI_API_KEY; returning stub")
            return "Imagem recebida."
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key)

    b64 = base64.b64encode(data).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"
    model = settings.sdr_vision_model

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Descreva brevemente o que aparece na imagem, só o observável.",
                },
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        },
    ]

    if _is_unittest_mock(client):
        create = client.chat.completions.create
        response = create(model=model, temperature=0, messages=messages)
        if hasattr(response, "__await__"):
            response = await response
    else:
        response = await client.chat.completions.create(
            model=model,
            temperature=0,
            messages=messages,
        )

    raw = ""
    try:
        raw = (response.choices[0].message.content or "").strip()
    except (AttributeError, IndexError, TypeError):
        if isinstance(response, dict):
            raw = str(response.get("text") or response.get("content") or "")
        elif isinstance(response, str):
            raw = response

    return sanitize_description(raw)
