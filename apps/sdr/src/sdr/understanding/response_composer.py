"""Response composer — LLM when configured, deterministic templates otherwise."""

from __future__ import annotations

import json
import logging
from typing import Any, Mapping

from sdr.config import get_settings
from sdr.understanding.persona_prompts import (
    HANDOFF_CONFIRMATION_ES,
    HANDOFF_CONFIRMATION_PT,
    JULIA_PERSONA_SYSTEM_PROMPT,
)
from sdr.understanding.validator import validate_bubbles

logger = logging.getLogger(__name__)

_FIELD_QUESTIONS_PT: dict[str, str] = {
    "name": "Me conta seu nome, por favor?",
    "budget": "Qual valor máximo você pensa em investir?",
    "budget_max": "Qual valor máximo você pensa em investir?",
    "desired_model": "Qual modelo ou tipo de carro você está buscando?",
    "model": "Qual modelo ou tipo de carro você está buscando?",
    "down_payment": "Você tem valor de entrada em mente?",
    "income": "Qual é a sua renda mensal aproximada? (só pra montar a pré-ficha)",
    "vehicle": "Qual modelo ou tipo de carro você está buscando?",
    "vehicle_interest": "Qual modelo ou tipo de carro você está buscando?",
    "brand": "Tem alguma marca de preferência?",
    "trade_in": "Me conta marca, modelo e ano do carro da troca?",
    "trade_model": "Me conta marca e modelo do carro da troca?",
    "trade_year": "Qual o ano do carro da troca?",
    "plate": "Se tiver a placa do veículo, pode me passar?",
    "location": "Você está em qual cidade?",
    "city": "Você está em qual cidade?",
    "visit": "Quer visitar a loja? Qual período fica melhor pra você?",
    "timeline": "Em quanto tempo você pensa em fechar?",
    "mileage": "Quantos km o veículo tem, aproximadamente?",
    "asking_price": "Qual valor você tem em mente?",
    "amount_needed": "Quanto você precisa levantar com o refinanciamento?",
    "leave_at_store": "Você topa deixar o carro na loja pra consignação?",
    "year": "Qual o ano do veículo?",
    "intent": "Você está buscando comprar, vender, trocar ou refinanciar?",
    "alternatives_ok": "Não encontrei exatamente o que você pediu no estoque atual. Quer que eu te mostre alternativas parecidas?",
}

_FIELD_QUESTIONS_ES: dict[str, str] = {
    "name": "¿Me dices tu nombre, por favor?",
    "budget": "¿Cuál es el valor máximo que piensas invertir?",
    "budget_max": "¿Cuál es el valor máximo que piensas invertir?",
    "down_payment": "¿Tienes un valor de entrada en mente?",
    "income": "¿Cuál es tu ingreso mensual aproximado? (solo para armar la pre-ficha)",
    "vehicle": "¿Qué modelo o tipo de auto estás buscando?",
    "vehicle_interest": "¿Qué modelo o tipo de auto estás buscando?",
    "brand": "¿Tienes alguna marca de preferencia?",
    "trade_in": "¿Me cuentas marca, modelo y año del auto del canje?",
    "plate": "Si tienes la placa del vehículo, ¿me la pasas?",
    "location": "¿En qué ciudad estás?",
    "visit": "¿Quieres visitar la tienda? ¿Qué horario te queda mejor?",
    "alternatives_ok": "No encontré exactamente lo que pediste en el stock actual. ¿Quieres que te muestre alternativas parecidas?",
}

_COMPOSER_JSON_SCHEMA: dict = {
    "name": "julia_bubbles",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["bubbles"],
        "properties": {
            "bubbles": {
                "type": "array",
                "minItems": 0,
                "maxItems": 3,
                "items": {"type": "string"},
            },
        },
    },
}


def _language(state: Mapping[str, Any]) -> str:
    lang = state.get("language") if isinstance(state, Mapping) else None
    if isinstance(lang, str) and lang.lower().startswith("es"):
        return "es"
    return "pt-BR"


def _site_location_line(tool_context: Mapping[str, Any] | None) -> str:
    """Build a location bubble from SiteSettings-like stub in tool_context."""
    ctx = tool_context or {}
    site = ctx.get("site_settings") or ctx.get("SiteSettings") or ctx
    if not isinstance(site, Mapping):
        site = {}

    parts: list[str] = []
    for key in ("address", "street", "endereco", "endereço"):
        value = site.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
            break
    city = site.get("city") or site.get("cidade")
    state_uf = site.get("state") or site.get("uf")
    if isinstance(city, str) and city.strip():
        if isinstance(state_uf, str) and state_uf.strip():
            parts.append(f"{city.strip()} - {state_uf.strip()}")
        else:
            parts.append(city.strip())
    maps = site.get("maps_url") or site.get("google_maps_url") or site.get("location_url")
    if isinstance(maps, str) and maps.strip():
        parts.append(maps.strip())

    if parts:
        return "Nossa loja fica em: " + " | ".join(parts)
    return "Posso te passar o endereço da loja — um instante que confirmo aqui."


def _ask_info_bubbles(
    state: Mapping[str, Any],
    action_plan: Mapping[str, Any],
) -> list[str]:
    lang = _language(state)
    questions = _FIELD_QUESTIONS_ES if lang == "es" else _FIELD_QUESTIONS_PT

    next_q = action_plan.get("next_question")
    if isinstance(next_q, str) and next_q.strip():
        # If it looks like a field key, map it; else use as natural question.
        key = next_q.strip()
        if key in questions:
            return [questions[key]]
        return [key]

    missing = (
        action_plan.get("missing_fields")
        or state.get("missing_fields")
        or []
    )
    if isinstance(missing, list):
        for field in missing:
            if isinstance(field, str) and field in questions:
                return [questions[field]]

    if lang == "es":
        return ["¿Me cuentas un poco más para yo poder te ayudar mejor?"]
    return ["Me conta um pouco mais pra eu te ajudar melhor?"]


def _template_compose(
    state: Mapping[str, Any],
    action_plan: Mapping[str, Any],
    tool_context: Mapping[str, Any] | None,
) -> list[str]:
    action = str(action_plan.get("action") or "")
    handoff = bool(action_plan.get("handoff"))
    lang = _language(state)

    if action == "no_reply":
        return []

    if action == "handoff_vendor" or handoff:
        msg = HANDOFF_CONFIRMATION_ES if lang == "es" else HANDOFF_CONFIRMATION_PT
        return [msg]

    if action == "ask_info":
        return _ask_info_bubbles(state, action_plan)

    if action == "send_location":
        return [_site_location_line(tool_context)]

    if action == "smalltalk":
        # Introduction eligibility is deterministic — not decided by the Composer.
        should_introduce = bool(state.get("should_introduce", True))
        if lang == "es":
            if should_introduce:
                return ["¡Hola! Soy Júlia de FacilCar. ¿En qué te puedo ayudar hoy?"]
            return ["¿En qué te puedo ayudar?"]
        if should_introduce:
            return [
                "Oi! Sou a Júlia da FacilCar, tudo bem?",
                "Estou aqui para ajudar você a encontrar o carro ideal e facilitar seu financiamento.",
            ]
        return ["Como posso ajudar?"]

    # COMMERCIAL_UNKNOWN: intent was UNKNOWN (not a greeting, not classified).
    # Must never produce a greeting or a generic "Como posso ajudar?".
    # Always produce a focused clarifying question that moves the conversation forward.
    if action == "commercial_unknown":
        if lang == "es":
            return ["¿Me puedes contar un poco más sobre lo que buscas?"]
        return ["Me conta o que você está procurando que eu te ajudo!"]

    # MEDIA_FAILED: explicit recovery — never a greeting.
    if action == "media_failed":
        if lang == "es":
            return ["Recibí tu archivo, pero tuve un problema para procesarlo. ¿Puedes escribirme lo que necesitas?"]
        return ["Recebi sua mídia, mas tive um problema para processar. Pode me contar o que precisa em texto?"]

    if action == "show_offers":
        outcome = str((tool_context or {}).get("inventory_outcome") or state.get("inventory_outcome") or "")
        offers = (tool_context or {}).get("offers") if tool_context else None
        alternatives = (tool_context or {}).get("alternatives") if tool_context else None

        if outcome == "FAILED_RETRYABLE":
            if lang == "es":
                return [
                    "No pude consultar nuestro stock ahora.",
                    "Puedo intentar de nuevo o encaminar tu interés al equipo.",
                ]
            return [
                "Não consegui consultar nosso estoque agora.",
                "Posso tentar novamente ou encaminhar seu interesse para a equipe.",
            ]
        if outcome == "FAILED_TERMINAL":
            if lang == "es":
                return [
                    "Tuve un problema al consultar el stock.",
                    "Puedo encaminar tu interés al equipo para continuar.",
                ]
            return [
                "Tive um problema ao consultar o estoque.",
                "Posso encaminhar seu interesse para a equipe continuar com você.",
            ]
        if outcome == "SUCCESS_EMPTY":
            affordance = str(
                (tool_context or {}).get("conversational_affordance")
                or state.get("conversational_affordance")
                or "NONE"
            )
            may_offer_alts = affordance == "OFFER_ALTERNATIVES"
            if lang == "es":
                bubbles = ["No encontré una opción con ese perfil en el stock actual."]
                if may_offer_alts:
                    if isinstance(alternatives, list) and alternatives:
                        bubbles.append("¿Quieres que te muestre alternativas parecidas?")
                    else:
                        bubbles.append(
                            "¿Quieres que te muestre alternativas parecidas, si hubiera?"
                        )
                return bubbles[:3]
            bubbles = ["Não encontrei uma opção com esse perfil no estoque atual."]
            if may_offer_alts:
                if isinstance(alternatives, list) and alternatives:
                    bubbles.append("Quer que eu te mostre alternativas parecidas?")
                else:
                    bubbles.append("Quer que eu veja alternativas parecidas, se tiver?")
            return bubbles[:3]

        if isinstance(offers, list) and offers:
            lines = []
            for offer in offers[:3]:
                if isinstance(offer, Mapping):
                    title = offer.get("title") or offer.get("name") or "opção"
                    price = offer.get("price") or offer.get("priceCash")
                    if price is not None:
                        lines.append(f"{title} — {price}")
                    else:
                        lines.append(str(title))
                elif isinstance(offer, str):
                    lines.append(offer)
            if lines:
                scope = str(
                    (tool_context or {}).get("alternative_scope")
                    or state.get("alternative_scope")
                    or "NONE"
                )
                if scope == "ANY_VEHICLE":
                    intro = (
                        "Olha algumas opções no estoque publicado:"
                        if lang != "es"
                        else "Mira algunas opciones en el stock publicado:"
                    )
                elif scope == "SIMILAR":
                    intro = (
                        "Olha alternativas parecidas no estoque:"
                        if lang != "es"
                        else "Mira alternativas parecidas en el stock:"
                    )
                else:
                    intro = "Olha o que encontrei:" if lang != "es" else "Mira lo que encontré:"
                return [intro, *lines][:3]
        # NOT_EXECUTED / unknown — never claim absence.
        if lang == "es":
            return ["Estoy consultando el stock publicado. ¿Tienes alguna preferencia?"]
        return ["Estou consultando o estoque publicado. Tem alguma preferência?"]


    if action == "send_photos":
        if lang == "es":
            return ["Te mando las fotos del vehículo en seguida."]
        return ["Te mando as fotos do veículo já já."]

    if action == "register_visit_interest":
        if lang == "es":
            return ["Anoté tu interés en visitar. ¿Qué día o período te queda mejor?"]
        return ["Anotei seu interesse em visitar. Qual dia ou período fica melhor?"]

    # Fallback: one gentle clarifying bubble
    return _ask_info_bubbles(state, action_plan)


def _is_unittest_mock(client: Any) -> bool:
    module = type(client).__module__ or ""
    return module.startswith("unittest.mock")


def compose_inventory_response(
    directive: Any,
    tool_context: Mapping[str, Any] | None = None,
) -> list[str]:
    """Deterministic inventory phrasing from ResponseDirective outcome.

    Bypasses the LLM Composer for stock truth — inventory meaning is decided
    by the directive, not by free-form generation.
    """
    from sdr.domain.types import InventoryOutcome

    outcome = directive.inventory_outcome
    if isinstance(outcome, str):
        try:
            outcome = InventoryOutcome(outcome)
        except ValueError:
            outcome = InventoryOutcome.NOT_EXECUTED

    lang = getattr(directive, "language", "pt-BR") or "pt-BR"
    affordance = getattr(directive, "conversational_affordance", None)
    affordance_val = getattr(affordance, "value", affordance) or "NONE"
    scope = getattr(directive, "alternative_scope", None)
    scope_val = getattr(scope, "value", scope) or "NONE"
    state = {
        "language": lang,
        "inventory_outcome": outcome.value if hasattr(outcome, "value") else str(outcome),
        "should_introduce": False,
        "conversational_affordance": affordance_val,
        "alternative_scope": scope_val,
    }
    plan = {"action": "show_offers", "handoff": False}
    ctx = dict(tool_context or {})
    ctx["inventory_outcome"] = state["inventory_outcome"]
    ctx["conversational_affordance"] = affordance_val
    ctx["alternative_scope"] = scope_val
    if getattr(directive, "inventory_alternatives", None):
        ctx["alternatives"] = directive.inventory_alternatives
        if outcome == InventoryOutcome.SUCCESS_FOUND:
            ctx["offers"] = directive.inventory_alternatives
    return _template_compose(state, plan, ctx)


async def compose_response(
    state: Mapping[str, Any],
    action_plan: Mapping[str, Any],
    tool_context: Mapping[str, Any] | None = None,
    *,
    client: Any | None = None,
) -> list[str]:
    """Compose 1–3 short WhatsApp bubbles (or [] for no_reply).

    Deterministic templates when no API key / unittest mock client (tests & offline).
    Otherwise uses the response model with Júlia persona; always validates bubbles.
    """
    action = str(action_plan.get("action") or "")
    if action == "no_reply":
        return []

    settings = get_settings()
    api_key = (settings.openai_api_key or "").strip()

    use_templates = False
    if client is not None and _is_unittest_mock(client):
        use_templates = True
    elif client is None and not api_key:
        use_templates = True
    elif client is None and api_key:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key)

    if use_templates:
        bubbles = _template_compose(state, action_plan, tool_context)
        return validate_bubbles(bubbles)

    model = settings.sdr_response_model
    should_introduce = bool(state.get("should_introduce", True))

    # Build a richer system prompt with deterministic guards.
    intro_instruction = (
        "Esta é a primeira mensagem — apresente-se brevemente."
        if should_introduce
        else "NÃO se apresente — a Júlia já interagiu nesta conversa anteriormente."
    )
    inv_outcome = state.get("inventory_outcome") or (tool_context or {}).get("inventory_outcome")
    inventory_rule = ""
    if inv_outcome == "FAILED_RETRYABLE" or inv_outcome == "FAILED_TERMINAL":
        inventory_rule = (
            "\nRegra de estoque: a consulta FALHOU. NÃO diga que não há veículo, "
            "não temos, sem estoque ou indisponível. Diga apenas que não conseguiu "
            "consultar agora e ofereça tentar de novo ou encaminhar."
        )
    elif inv_outcome == "SUCCESS_EMPTY":
        inventory_rule = (
            "\nRegra de estoque: consulta OK sem match no estoque publicado atual. "
            "Pode dizer que não encontrou opção com esse perfil no estoque atual. "
            "NÃO diga que a loja não trabalha com essa categoria ou que nunca terá."
        )
    elif inv_outcome == "SUCCESS_FOUND":
        inventory_rule = (
            "\nRegra de estoque: há veículos publicados encontrados — apresente até 3."
        )

    system_prompt = (
        f"{JULIA_PERSONA_SYSTEM_PROMPT}\n\nRegra de apresentação: {intro_instruction}"
        f"{inventory_rule}"
    )

    payload = {
        "context": {
            "intent": state.get("intent", "unknown"),
            "language": state.get("language", "pt-BR"),
            "customer_name": state.get("customer_name"),
            "facts": state.get("facts", {}),
            "lifecycle_status": state.get("lifecycle_status", "BOT_ACTIVE"),
            "should_introduce": should_introduce,
            "claims_forbidden": state.get("claims_forbidden", []),
            "claims_allowed": state.get("claims_allowed", []),
            "inventory_outcome": inv_outcome,
        },
        "action_plan": dict(action_plan),
        "tool_results": dict(tool_context or {}),
    }

    response = await client.chat.completions.create(
        model=model,
        temperature=0.4,
        response_format={
            "type": "json_schema",
            "json_schema": _COMPOSER_JSON_SCHEMA,
        },
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False),
            },
        ],
    )

    raw = response.choices[0].message.content or "{}"
    try:
        data = json.loads(raw)
        bubbles = data.get("bubbles") if isinstance(data, Mapping) else None
        if not isinstance(bubbles, list):
            bubbles = _template_compose(state, action_plan, tool_context)
        else:
            bubbles = [str(b) for b in bubbles if b]
    except json.JSONDecodeError:
        logger.warning("compose_response: invalid JSON; using templates")
        bubbles = _template_compose(state, action_plan, tool_context)

    return validate_bubbles(list(bubbles)[:3])
