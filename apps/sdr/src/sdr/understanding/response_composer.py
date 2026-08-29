"""Response composer — LLM when configured, deterministic templates otherwise."""

from __future__ import annotations

import json
import logging
from typing import Any, Mapping

from sdr.config import get_settings
from sdr.domain.display_name import display_first_name
from sdr.domain.introduction import (
    continuation_smalltalk_bubbles,
    intro_instruction,
    introduction_smalltalk_bubbles,
)
from sdr.understanding.persona_prompts import (
    HANDOFF_CONFIRMATION_ES,
    HANDOFF_CONFIRMATION_PT,
    JULIA_PERSONA_SYSTEM_PROMPT,
)
from sdr.understanding.validator import validate_bubbles, validate_introduction_policy

logger = logging.getLogger(__name__)

_FIELD_QUESTIONS_PT: dict[str, str] = {
    "name": "Me diga seu nome, por favor?",
    "desired_model": "Qual modelo ou tipo de carro você está buscando?",
    "model": "Qual modelo ou tipo de carro você está buscando?",
    "deal_type": "Seria compra ou troca?",
    "down_payment": "Você teria algum valor de entrada, ou prefere financiar o total?",
    "desired_installment": "Até quanto de parcela você tem em mente?",
    "income": "Pode me informar sua renda mensal aproximada?",
    "documents": "Pra montar a simulação, pode me enviar a CNH e um comprovante de renda (holerite)?",
    "vehicle": "Qual modelo ou tipo de carro você está buscando?",
    "vehicle_interest": "Qual modelo ou tipo de carro você está buscando?",
    "brand": "Tem preferência por marca?",
    "trade_in": "Qual marca, modelo e ano do carro da troca?",
    "trade_model": "Qual marca e modelo do carro da troca?",
    "trade_year": "Qual o ano do carro da troca?",
    "plate": "Se tiver a placa do veículo, pode me passar?",
    "location": "Você está de qual cidade?",
    "city": "Você é de em qual cidade?",
    "visit": "Quer visitar a loja? Qual período fica melhor pra você?",
    "timeline": "Em quanto tempo você pensa em fechar?",
    "mileage": "Quantos km rodados tem o veículo, aproximadamente?",
    "asking_price": "Até qual valor você tem em mente?",
    "amount_needed": "Quanto você precisa levantar com o refinanciamento?",
    "leave_at_store": "Topa deixar o carro na loja pra consignação?",
    "year": "Qual o ano do veículo?",
    "intent": "Você está buscando comprar, vender, trocar ou refinanciar?",
    "payment_method": "Seria à vista ou financiado?",
    "alternatives_ok": "Não encontrei exatamente o que você pediu no estoque atual. Posso te mostrar alternativas parecidas?",
}

_FIELD_QUESTIONS_ES: dict[str, str] = {
    "name": "¿Me dices tu nombre, por favor?",
    "deal_type": "¿Sería compra o permuta?",
    "down_payment": "¿Tienes un valor de entrada, o prefieres financiar el valor completo?",
    "desired_installment": "¿Hasta cuánto de cuota tienes en mente?",
    "income": "¿Cuál es tu ingreso mensual aproximado? (solo para armar la pre-ficha)",
    "documents": "Para armar la pre-ficha, ¿puedes enviarme la licencia y un comprobante de ingresos?",
    "vehicle": "¿Qué modelo o tipo de auto estás buscando?",
    "vehicle_interest": "¿Qué modelo o tipo de auto estás buscando?",
    "brand": "¿Tienes alguna marca de preferencia?",
    "trade_in": "¿Me cuentas marca, modelo y año del auto del canje?",
    "plate": "Si tienes la placa del vehículo, ¿me la pasas?",
    "location": "¿En qué ciudad estás?",
    "visit": "¿Quieres visitar la tienda? ¿Qué horario te queda mejor?",
    "payment_method": "¿Sería de contado o financiado?",
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


def _first_name(state: Mapping[str, Any]) -> str | None:
    raw = state.get("customer_name") or (state.get("facts") or {}).get("name")
    if not isinstance(raw, str):
        return None
    return display_first_name(raw)


def _required_question(
    state: Mapping[str, Any],
    action_plan: Mapping[str, Any],
    lang: str,
) -> str | None:
    questions = _FIELD_QUESTIONS_ES if lang == "es" else _FIELD_QUESTIONS_PT
    next_q = action_plan.get("next_question") or action_plan.get("ask_field")
    if isinstance(next_q, str) and next_q.strip():
        key = next_q.strip()
        if key in {"budget", "budget_max"}:
            key = "deal_type"
        if key == "visit":
            return None
        if key == "alternatives_ok" and action_plan.get("reason_code") == "installment_tight":
            if lang == "es":
                return (
                    "Para esa cuota, puede ser necesaria una entrada más generosa. "
                    "¿Quieres que te muestre opciones más cercanas a esa cuota, o seguimos con este vehículo?"
                )
            return (
                "Para esse valor de parcela, uma entrada mais generosa pode ser necessária. "
                "Quer que eu veja opções mais próximas dessa parcela, ou seguimos com esse veículo?"
            )
        if key in questions:
            return questions[key]
        if key not in {"budget", "budget_max"}:
            return key
    missing = action_plan.get("missing_fields") or state.get("missing_fields") or []
    if isinstance(missing, list):
        for field in missing:
            if field in {"budget", "budget_max"}:
                return questions["deal_type"]
            if isinstance(field, str) and field == "visit":
                return None
            if isinstance(field, str) and field in questions:
                return questions[field]
    return None


def _visit_cta_bubbles(state: Mapping[str, Any], lang: str) -> list[str]:
    style = str(state.get("visit_cta_style") or "warm_invite")
    es = lang == "es"
    if style == "location_close":
        if es:
            return [
                "Podemos evaluar las condiciones de la negociación aquí en la tienda. "
                "Si te queda bien, pasa esta semana. ¡Te esperamos!"
            ]
        return [
            "Conseguimos avaliar as condições da negociação aqui na loja. "
            "Se fizer sentido, passa aqui esta semana. Esperamos você!"
        ]
    if style == "hot_schedule":
        if es:
            return [
                "Podemos evaluar las condiciones de negociación aquí en la tienda. "
                "Si te queda bien, pasa a conocernos esta semana — sin compromiso."
            ]
        return [
            "Conseguimos avaliar as condições da negociação aqui na loja. "
            "Se fizer sentido, passa aqui esta semana — sem compromisso."
        ]
    if es:
        return [
            "Nuestra tienda está de puertas abiertas. Pasa a tomar un café, sin compromiso."
        ]
    return [
        "Nossa loja está de portas abertas. Aparece tomar um café, sem compromisso."
    ]


def _document_received_bubbles(
    state: Mapping[str, Any],
    lang: str,
    *,
    question: str | None = None,
) -> list[str]:
    name = _first_name(state)
    kind = str(state.get("document_kind") or "").upper()
    es = lang == "es"
    if kind == "CNH":
        if es:
            ack = (
                f"Show, {name}! CNH guardada en tu ficha."
                if name
                else "Show! CNH guardada en tu ficha."
            )
            extra = (
                "Si tienes comprobante de ingresos, domicilio o acta de matrimonio, "
                "también puedes enviármelos. Cuanta más información tenermos, "
                "mejor margen tenemos para negociar una tasa menor para ti."
            )
        else:
            ack = (
                f"Show, {name}! CNH salva na sua ficha."
                if name
                else "Show! CNH salva na sua ficha."
            )
            extra = (
                "Se tiver comprovante de renda, residência ou certidão de casamento, "
                "pode me enviar também. Quanto mais informações tivermos, "
                "maiores as chances de boas taxas na simulação!"
            )
        bubbles = [ack, extra]
        if question:
            bubbles.append(question)
        return bubbles[:3]
    if es:
        ack = (
            f"Show, {name}! Recibí tu documento y ya lo anexé a tu ficha."
            if name
            else "Show! Recibí tu documento y ya lo anexé a tu ficha."
        )
    else:
        ack = (
            f"Show, {name}! Recebi seu documento e já anexei na sua ficha."
            if name
            else "Show! Recebi seu documento e já anexei na sua ficha."
        )
    return [ack, question] if question else [ack]


def _ack_followup_bubbles(
    state: Mapping[str, Any],
    action_plan: Mapping[str, Any],
    lang: str,
) -> list[str] | None:
    """Warm ack + next roteiro question. None → fall through to question-only."""
    kind = state.get("ack_kind")
    if not kind:
        return None
    question = _required_question(state, action_plan, lang)
    es = lang == "es"

    if kind == "deal_purchase":
        if es:
            text = (
                "Entendí tu interés en la compra, sin incluir un vehículo en la negociación."
            )
            if question:
                text = f"{text} {question}"
            return [text]
        text = (
            "Entendi seu interesse na compra, sem incluir veículo na negociação."
        )
        if question:
            text = f"{text} {question}"
        return [text]
    if kind == "deal_trade":
        if es:
            text = "Entendí: vamos incluir tu vehículo en la negociación."
        else:
            text = "Entendi: vamos incluir seu veículo na negociação."
        return [text, question] if question else [text]
    if kind == "payment_financing":
        if es:
            text = (
                "Legal, el financiamiento puede ser una buena opción. "
                "Conseguimos excelentes condiciones aquí en la tienda."
            )
        else:
            text = (
                "Legal, financiamento pode ser uma boa opção pra facilitar. "
                "Conseguimos ótimas condições aqui na loja."
            )
        return [text, question] if question else [text]
    if kind == "payment_cash":
        if es:
            text = "Recibí: de contado."
        else:
            text = "Recebi: à vista."
        return [text, question] if question else [text]
    if kind == "down_payment":
        # Distinguish zero-entry (financia o valor todo) from positive-entry cases.
        # A zero-entry template must not imply "com uma entrada" — the customer
        # explicitly said they have no entry.
        down_val = (state.get("facts") or {}).get("down_payment")
        no_down = down_val == 0 or down_val == "0"
        if es:
            if no_down:
                text = "Entendido, financiaremos el valor total."
            else:
                text = "Entendido, anotada la entrada."
        else:
            if no_down:
                text = "Entendido, vamos financiar o valor todo."
            else:
                text = "Certo, anotei a entrada."
        return [text, question] if question else [text]
    if kind == "desired_installment":
        return [question] if question else None
    if kind == "document_received":
        return _document_received_bubbles(state, lang, question=question)
    return None


def _follow_up_bubble(
    state: Mapping[str, Any],
    action_plan: Mapping[str, Any],
    lang: str,
) -> str:
    """Single next commercial question. Never solicit budget."""
    questions = _FIELD_QUESTIONS_ES if lang == "es" else _FIELD_QUESTIONS_PT
    next_q = action_plan.get("next_question") or action_plan.get("ask_field")
    if isinstance(next_q, str) and next_q.strip():
        key = next_q.strip()
        if key in {"budget", "budget_max"}:
            key = "deal_type"
        if key == "visit":
            return (
                "Nuestra tienda está de puertas abiertas. Pasa a tomar un café, sin compromiso."
                if lang == "es"
                else "Nossa loja está de portas abertas. Aparece tomar um café, sem compromisso."
            )
        if key in questions:
            return questions[key]
        if key not in {"budget", "budget_max"}:
            return key
    missing = action_plan.get("missing_fields") or state.get("missing_fields") or []
    if isinstance(missing, list):
        for field in missing:
            if field in {"budget", "budget_max"}:
                return questions["deal_type"]
            if isinstance(field, str) and field in questions:
                return questions[field]
    return questions.get("deal_type") or "Seria compra ou troca?"


def _ask_info_bubbles(
    state: Mapping[str, Any],
    action_plan: Mapping[str, Any],
) -> list[str]:
    lang = _language(state)
    combined = _ack_followup_bubbles(state, action_plan, lang)
    if combined:
        return [b for b in combined if b][:3]

    question = _required_question(state, action_plan, lang)
    if question:
        return [question]
    if lang == "es":
        return ["¿Me cuentas un poco más para yo poder te ayudar mejor?"]
    return ["Me conta um pouco mais pra eu te ajudar melhor?"]


def _document_ack(content_type: str, lang: str) -> str | None:
    """Brief acknowledgement when inbound was non-text media."""
    ct = (content_type or "TEXT").upper()
    if ct == "TEXT":
        return None
    labels_pt = {
        "IMAGE": "foto",
        "DOCUMENT": "documento",
        "AUDIO": "áudio",
        "VIDEO": "vídeo",
        "STICKER": "figurinha",
    }
    labels_es = {
        "IMAGE": "foto",
        "DOCUMENT": "documento",
        "AUDIO": "audio",
        "VIDEO": "video",
        "STICKER": "sticker",
    }
    labels = labels_es if lang == "es" else labels_pt
    label = labels.get(ct, ct.lower())
    if lang == "es":
        return f"Recibí tu {label}!"
    return f"Recebi seu {label}!"


def _first_contact_opener(state: Mapping[str, Any], lang: str) -> str:
    facts = state.get("facts") if isinstance(state.get("facts"), Mapping) else {}
    model = None
    if isinstance(facts, Mapping):
        raw = facts.get("desired_model") or facts.get("desired_vehicle_text")
        if isinstance(raw, str) and raw.strip():
            model = raw.strip()
    es = lang == "es"
    if es:
        if model:
            return (
                f"¡Hola! ¿Cómo va? Soy Júlia de FacilCar. "
                f"El {model} es una excelente opción. Déjame enviarte unas fotos"
            )
        return "¡Hola! ¿Cómo va? Soy Júlia de FacilCar."
    if model:
        return (
            f"Olá! Como vai? Eu sou a Júlia aqui da FacilCar. "
            f"O {model} é uma excelente opção. Deixa eu te enviar umas fotos"
        )
    return "Olá! Como vai? Eu sou a Júlia aqui da FacilCar."


def _with_first_contact(
    state: Mapping[str, Any],
    follow: str | None,
    lang: str,
) -> list[str]:
    if not state.get("should_introduce"):
        return [follow] if follow else []
    opener = _first_contact_opener(state, lang)
    if follow:
        return [opener, follow]
    return [opener]


def _engagement_prefix(lang: str) -> str:
    """Empathetic opener when engagement is low."""
    if lang == "es":
        return "Claro, con gusto te ayudo."
    return "Tudo certo, pode contar comigo!"


def _template_compose(
    state: Mapping[str, Any],
    action_plan: Mapping[str, Any],
    tool_context: Mapping[str, Any] | None,
) -> list[str]:
    action = str(action_plan.get("action") or "")
    handoff = bool(action_plan.get("handoff"))
    lang = _language(state)
    engagement_low = bool(state.get("engagement_low", False))
    inbound_ctype = str(state.get("inbound_content_type") or "TEXT")

    if action == "no_reply":
        return []

    if action == "handoff_vendor" or handoff:
        msg = HANDOFF_CONFIRMATION_ES if lang == "es" else HANDOFF_CONFIRMATION_PT
        return [msg]

    if action == "ask_info":
        bubbles = _ask_info_bubbles(state, action_plan)
        if engagement_low and not state.get("ack_kind") and not bubbles:
            bubbles = [_engagement_prefix(lang)]
        return bubbles[:3]

    if action == "send_location":
        return _visit_cta_bubbles(state, lang)[:1]

    if action == "smalltalk":
        # Introduction eligibility is deterministic — not decided by the Composer.
        should_introduce = bool(state.get("should_introduce", False))
        intro_style = str(state.get("intro_style") or "FULL")
        if should_introduce and intro_style == "BRIEF":
            # Intent was clear on first turn — skip full intro, go to first question.
            follow = _follow_up_bubble(state, action_plan, lang)
            if lang == "es":
                brief = "Hola, soy Júlia de FacilCar!"
            else:
                brief = "Oi, sou a Júlia da FacilCar!"
            return [brief, follow] if follow else [brief]
        if should_introduce:
            return introduction_smalltalk_bubbles(lang)
        return continuation_smalltalk_bubbles(lang)

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
            media_planned = bool((tool_context or {}).get("outbound_media_planned"))
            follow = _follow_up_bubble(state, action_plan, lang)
            if media_planned:
                return _with_first_contact(state, follow, lang)
            from sdr.domain.vehicle_presentation import format_vehicle_caption

            captions: list[str] = []
            for offer in offers[:3]:
                if isinstance(offer, Mapping):
                    captions.append(format_vehicle_caption(offer, language=lang))
                elif isinstance(offer, str):
                    captions.append(offer)
            bubbles = captions[:2]
            if follow:
                bubbles.append(follow)
            return bubbles[:3]
        # NOT_EXECUTED / unknown — never claim absence.
        if lang == "es":
            return ["Estoy consultando el stock publicado. ¿Tienes alguna preferencia?"]
        return ["Estou consultando o estoque publicado. Tem alguma preferência?"]


    if action == "send_photos":
        media_planned = bool((tool_context or {}).get("outbound_media_planned"))
        follow = _follow_up_bubble(state, action_plan, lang)
        if media_planned:
            return _with_first_contact(state, follow, lang)
        if lang == "es":
            return ["No encontré fotos de ese anuncio ahora.", follow][:2] if follow else [
                "No encontré fotos de ese anuncio ahora."
            ]
        return (
            ["Não encontrei fotos desse anúncio agora.", follow][:2]
            if follow
            else ["Não encontrei fotos desse anúncio agora."]
        )

    if action == "register_visit_interest":
        visit = _visit_cta_bubbles(state, lang)
        if state.get("ack_kind") == "document_received":
            docs = _document_received_bubbles(state, lang)
            return [*docs, visit[0]][:3]
        return visit[:1]

    # Fallback: one gentle clarifying bubble
    bubbles_fb: list[str] = []
    ack_fb = _document_ack(inbound_ctype, lang)
    if ack_fb:
        bubbles_fb.append(ack_fb)
    bubbles_fb.extend(_ask_info_bubbles(state, action_plan))
    return bubbles_fb[:3]


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
        "should_introduce": bool(getattr(directive, "should_introduce", False)),
        "facts": getattr(directive, "facts_context", None) or {},
        "conversational_affordance": affordance_val,
        "alternative_scope": scope_val,
    }
    plan = {
        "action": "show_offers",
        "handoff": False,
        "next_question": getattr(directive, "next_question", None),
    }
    ctx = dict(tool_context or {})
    ctx["inventory_outcome"] = state["inventory_outcome"]
    ctx["conversational_affordance"] = affordance_val
    ctx["alternative_scope"] = scope_val
    if getattr(directive, "inventory_alternatives", None):
        ctx["alternatives"] = directive.inventory_alternatives
        if outcome == InventoryOutcome.SUCCESS_FOUND and not ctx.get("offers"):
            ctx["offers"] = directive.inventory_alternatives
    return _template_compose(state, plan, ctx)


def compose_photos_response(
    directive: Any,
    tool_context: Mapping[str, Any] | None = None,
) -> list[str]:
    """Deterministic follow-up after listing photos — never permission, never budget."""
    lang = getattr(directive, "language", "pt-BR") or "pt-BR"
    state = {
        "language": lang,
        "should_introduce": bool(getattr(directive, "should_introduce", False)),
        "facts": getattr(directive, "facts_context", None) or {},
        "missing_fields": [directive.next_question] if directive.next_question else [],
    }
    plan = {
        "action": "send_photos",
        "handoff": False,
        "next_question": getattr(directive, "next_question", None),
    }
    ctx = dict(tool_context or {})
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
    if action in (
        "send_photos",
        "show_offers",
        "send_location",
        "media_failed",
    ):
        use_templates = True
    elif state.get("ack_kind"):
        # Roteiro acks use deterministic templates — prevents LLM from echoing
        # amounts, re-asking known fields, or generating unreliable phrasing.
        use_templates = True
    elif client is not None and _is_unittest_mock(client):
        use_templates = True
    elif client is None and not api_key:
        use_templates = True
    elif client is None and api_key:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key)

    should_introduce = bool(state.get("should_introduce", False))
    lang = _language(state)

    if use_templates:
        bubbles = _template_compose(state, action_plan, tool_context)
        bubbles = validate_bubbles(bubbles, language=lang)
        bubbles, _ = validate_introduction_policy(
            bubbles,
            should_introduce=should_introduce,
            action=action,
            language=lang,
        )
        return bubbles

    model = settings.sdr_response_model
    objective = str(state.get("response_objective") or intro_instruction(should_introduce))
    inbound_text = str(state.get("inbound_text") or "")[:500]

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
        media_planned = bool((tool_context or {}).get("outbound_media_planned"))
        if media_planned:
            inventory_rule = (
                "\nRegra de estoque: as fotos do veículo JÁ serão enviadas com a "
                "descrição no caption. NÃO liste o carro em texto, NÃO diga "
                "'Olha o que encontrei'. Se should_introduce, apresente-se na primeira "
                "bolha; a pergunta de follow-up vai depois das fotos."
            )
        else:
            inventory_rule = (
                "\nRegra de estoque: há veículos publicados — descreva com os "
                "campos do anúncio (preço formatado). NÃO use 'Olha o que encontrei'."
            )
    inventory_rule += (
        "\nNUNCA pergunte orçamento, valor máximo ou quanto o cliente quer investir."
    )
    next_q_text = _required_question(state, action_plan, lang)
    ack_kind = state.get("ack_kind")
    tone_rule = (
        "\nTom: informal, empático e com leve entusiasmo. NÃO valide a última fala "
        "com eco robótico (proibido: 'Anotei:', 'Beleza, então é', 'Recebi seu text'). "
        "NÃO soe como formulário. Uma pergunta por vez."
        "\nPagamento: é XOR — à vista OU financiado. NUNCA ofereça 'os dois'."
    )
    cadence_mode = state.get("cadence_mode")
    if cadence_mode:
        tone_rule += f"\nCadência deste turno (obrigatória): {cadence_mode}."
    if ack_kind == "deal_purchase":
        tone_rule += (
            "\nRecap corrigível: 'Entendi seu interesse na compra, sem incluir veículo "
            "na negociação.' Depois a pergunta à vista ou financiado. Sem 'que ótimo'."
        )
    elif ack_kind == "payment_financing":
        tone_rule += "\nConfirme o recebimento (financiamento) e avance para a entrada."
    elif ack_kind == "down_payment":
        tone_rule += (
            "\nConfirme que recebeu a informação sobre a entrada e avance. "
            "NÃO diga que as condições tendem a ser melhores."
        )
    elif ack_kind == "document_received":
        tone_rule += (
            "\nDocumento recebido: agradeça pelo nome (se houver) e diga que anexou "
            "na ficha para a simulação. NÃO reacuse 'financiado'."
        )
    if next_q_text:
        tone_rule += f"\nPergunta obrigatória deste turno: {next_q_text}"

    system_prompt = (
        f"{JULIA_PERSONA_SYSTEM_PROMPT}\n\n"
        f"Regra de apresentação: {intro_instruction(should_introduce)}\n"
        f"Objetivo deste turno: {objective}"
        f"{inventory_rule}"
        f"{tone_rule}"
    )

    payload = {
        "context": {
            "intent": state.get("intent", "unknown"),
            "language": state.get("language", "pt-BR"),
            "customer_name": state.get("customer_name"),
            "facts": state.get("facts", {}),
            "lifecycle_status": state.get("lifecycle_status", "BOT_ACTIVE"),
            "should_introduce": should_introduce,
            "response_objective": objective,
            "inbound_text": inbound_text,
            "ack_kind": state.get("ack_kind"),
            "visit_cta_style": state.get("visit_cta_style"),
            "required_question": next_q_text,
            "claims_forbidden": state.get("claims_forbidden", []),
            "claims_allowed": state.get("claims_allowed", []),
            "inventory_outcome": inv_outcome,
        },
        "action_plan": dict(action_plan),
        "tool_results": dict(tool_context or {}),
        "inbound_text": inbound_text,
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

    bubbles = validate_bubbles(list(bubbles)[:3], language=lang)
    bubbles, _ = validate_introduction_policy(
        bubbles,
        should_introduce=should_introduce,
        action=action,
        language=lang,
    )
    return bubbles
