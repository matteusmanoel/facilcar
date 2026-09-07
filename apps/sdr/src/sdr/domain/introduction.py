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
    "aqui é a júlia da facilcar",
    "aqui é a julia da facilcar",
    "como posso ajudar você hoje",
    "como posso te ajudar hoje",
    "em que posso te ajudar hoje",
    "en qué te puedo ayudar hoy",
    "como puedo ayudarte hoy",
    "estamos felizes pelo seu contato",
    "estamos felices de que nos hayas contactado",
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
                "e pergunte se o cliente busca comprar, trocar, vender, consignar ou refinanciar."
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


def display_first_name(full_name: str | None) -> str | None:
    """Extract and capitalise first name from full name string."""
    if not full_name:
        return None
    first = full_name.strip().split()[0]
    return first.capitalize() if first else None


def introduction_smalltalk_bubbles(language: str, customer_name: str | None = None) -> list[str]:
    first_name = display_first_name(customer_name)
    if (language or "").lower().startswith("es"):
        greeting = (
            f"Oi {first_name}, aqui é a Júlia da FacilCar. Estamos felizes pelo seu contato!"
            if first_name
            else "¡Hola! Soy Júlia de FacilCar. ¡Estamos felices de que nos hayas contactado!"
        )
        menu = (
            "Cuéntame, ¿estás pensando en:\n"
            "- Comprar\n"
            "- Permutar\n"
            "- Vender\n"
            "- Consignar\n"
            "- Refinanciar\n\n"
            "un vehículo?"
        )
        return [greeting, menu]
    greeting = (
        f"Oi {first_name}! Aqui é a Júlia da FacilCar. Estamos felizes pelo seu contato!"
        if first_name
        else "Oi! Aqui é a Júlia da FacilCar. Estamos felizes pelo seu contato!"
    )
    menu = (
        "Me conta, você está pensando em:\n"
        "- Comprar\n"
        "- Trocar\n"
        "- Vender\n"
        "- Consignar\n"
        "- Refinanciar\n\n"
        "um veículo?"
    )
    return [greeting, menu]


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
