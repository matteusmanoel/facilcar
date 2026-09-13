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

# First-contact identity prefix that may follow (or replace) a greeting particle.
_INTRO_PREFIX = re.compile(
    r"^\s*(?:(?:oi+|ol[áa]|oie|hola)\b[!?.¡¿\s,]*)?"
    r"(?:aqui é a |sou a |soy )j[uú]lia(?: da facilcar| de facilcar)?"
    r"[^.!?\n]{0,80}[.!…]?\s*",
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
                "Primeiro contato: apresente-se brevemente como Júlia da FacilCar. "
                "Se o cliente perguntou se você está bem, responda com reciprocidade. "
        "Convide a pessoa a dizer como pode ajudar, sem presumir que ela já possui um veículo. "
        "Não use um menu rígido de comprar/trocar/vender/consignar/refinanciar."
            )
        return (
            "Primeira mensagem da Júlia nesta conversa: pode se apresentar "
            "brevemente se couber no objetivo do turno."
        )
    if action_val == Action.SMALLTALK.value:
        return (
            "Continuação: responda ao que o cliente acabou de dizer. "
            "Não cumprimente como primeiro contato. Não abra com Oi, Olá ou Hola. "
            "Não se apresente. Se for reciprocidade social, responda brevemente. "
            "Se for só agradecimento, retribua sem reabrir o roteiro."
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


def introduction_smalltalk_bubbles(
    language: str,
    customer_name: str | None = None,
    inbound_text: str = "",
    *,
    skip_intent_menu: bool = False,
) -> list[str]:
    from sdr.domain.dialogue_plan import has_wellbeing_question

    first_name = display_first_name(customer_name)
    wellbeing = has_wellbeing_question(inbound_text)
    es = (language or "").lower().startswith("es")
    if es:
        if wellbeing:
            greeting = (
                f"Hola{f', {first_name}' if first_name else ''}! Todo bien sí, ¿y tú? "
                "Soy Júlia de FacilCar."
            )
        elif first_name:
            greeting = f"Hola, {first_name}. Soy Júlia de FacilCar."
        else:
            greeting = "¡Hola! Soy Júlia de FacilCar."
        invite = (
            "¿Cómo puedo ayudarte?"
            if skip_intent_menu
            else "¿Cómo puedo ayudarte?"
        )
        return [greeting, invite]
    if wellbeing:
        greeting = (
            f"Oi{f', {first_name}' if first_name else ''}! Tudo bem sim, e com você? "
            "Sou a Júlia da FacilCar."
        )
    elif first_name:
        greeting = f"Oi, {first_name}! Sou a Júlia da FacilCar."
    else:
        greeting = "Oi! Sou a Júlia da FacilCar."
    invite = "Como posso te ajudar?"
    return [greeting, invite]


def continuation_smalltalk_bubbles(
    language: str,
    inbound_text: str = "",
    *,
    courtesy: bool = False,
) -> list[str]:
    from sdr.domain.dialogue_plan import has_wellbeing_question

    es = (language or "").lower().startswith("es")
    if courtesy:
        return ["¡De nada! Cualquier cosa, me avisas."] if es else ["Por nada! Qualquer coisa é só chamar."]
    if has_wellbeing_question(inbound_text):
        if es:
            return ["Todo bien sí, ¿y tú? Cuéntame cómo puedo ayudarte."]
        return ["Tudo bem sim, e com você? Me conta como posso te ajudar."]
    if es:
        return ["Cuéntame qué necesitas que te ayudo."]
    return ["Me conta o que você precisa que eu te ajudo."]


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
    stripped = _INTRO_PREFIX.sub("", text, count=1).strip()
    if stripped != text.strip():
        return stripped
    return _GREETING_OPENER.sub("", text, count=1).strip()
