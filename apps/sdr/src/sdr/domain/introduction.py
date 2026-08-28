"""Deterministic introduction / continuation policy.

Conversation phase is derived from assistant_turn_count, never from prompt:

    should_introduce = assistant_turn_count == 0

SMALLTALK after first contact is continuation, not a new greeting.
The Composer must receive inbound text and a response_objective; it must not
reopen with first-contact particles (Oi / Olá / Sou a Júlia / como posso ajudar hoje).
"""

from __future__ import annotations

import re
from typing import Sequence

from sdr.domain.types import Action

_GREETING_OPENER = re.compile(
    r"^\s*(?:oi+|ol[áa]|oie|hola)\b[!?.¡¿\s]*",
    re.IGNORECASE,
)

# First-contact reopen phrases — protocol, not product-term heuristics.
_REOPEN_PHRASES = (
    "sou a júlia",
    "sou a julia",
    "soy júlia",
    "soy julia",
    "como posso ajudar você hoje",
    "como posso te ajudar hoje",
    "em que posso te ajudar hoje",
    "en qué te puedo ayudar hoy",
    "como puedo ayudarte hoy",
)


def intro_instruction(should_introduce: bool) -> str:
    if should_introduce:
        return (
            "Esta é a primeira mensagem — apresente-se brevemente como Júlia da FacilCar."
        )
    return (
        "NÃO se apresente e NÃO cumprimente como primeiro contato. "
        "Não abra com Oi, Olá ou Hola. A Júlia já interagiu nesta conversa. "
        "Responda ao que o cliente acabou de dizer."
    )


def response_objective_for(*, action: Action | str, should_introduce: bool) -> str:
    """Deterministic Composer objective from action + conversation phase."""
    action_val = action.value if isinstance(action, Action) else str(action or "")
    if should_introduce:
        if action_val == Action.SMALLTALK.value:
            return (
                "Primeiro contato: apresente-se brevemente como Júlia da FacilCar "
                "e pergunte se o cliente busca compra, troca, financiamento ou refinanciamento."
            )
        return (
            "Primeira mensagem da Júlia nesta conversa: pode se apresentar "
            "brevemente se couber no objetivo do turno."
        )
    if action_val == Action.SMALLTALK.value:
        return (
            "Continuação: responda ao que o cliente acabou de dizer. "
            "Não cumprimente como primeiro contato. Não abra com Oi, Olá ou Hola. "
            "Não se apresente. Se for reciprocidade social, responda brevemente "
            "e convide a seguir para o que a pessoa busca."
        )
    return (
        "Continuação: a Júlia já está nesta conversa. Não se apresente e não "
        "reabra com saudação de primeiro contato. Responda o assunto do turno."
    )


def introduction_smalltalk_bubbles(language: str) -> list[str]:
    if (language or "").lower().startswith("es"):
        return [
            "¡Hola! Soy Júlia de FacilCar.",
            "¿Buscas compra, permuta, financiamiento o refinanciamiento?",
        ]
    return [
        "Olá! Sou a Júlia da FacilCar.",
        "Me conta: você busca compra, troca, financiamento ou refinanciamento?",
    ]


def continuation_smalltalk_bubbles(language: str) -> list[str]:
    if (language or "").lower().startswith("es"):
        return ["Todo bien por acá. Cuéntame qué estás buscando."]
    return ["Tudo certo por aqui! Me conta o que você está procurando."]


def _contains_reopen_phrase(text: str) -> bool:
    low = text.lower()
    return any(phrase in low for phrase in _REOPEN_PHRASES)


def is_first_contact_reopen(bubbles: Sequence[str]) -> bool:
    """True when outbound looks like a fresh first-contact greeting."""
    cleaned = [b.strip() for b in bubbles if isinstance(b, str) and b.strip()]
    if not cleaned:
        return False
    joined = " ".join(cleaned)
    if _contains_reopen_phrase(joined):
        return True
    return _GREETING_OPENER.match(cleaned[0]) is not None


def strip_greeting_opener(text: str) -> str:
    return _GREETING_OPENER.sub("", text, count=1).strip()
