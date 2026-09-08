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
from sdr.domain.question_adherence import (
    evaluate_adherence,
    replace_question_bubble,
)
from sdr.understanding.validator import (
    validate_bubbles,
    validate_dialogue_plan,
    validate_introduction_policy,
)

logger = logging.getLogger(__name__)

_FIELD_QUESTIONS_PT: dict[str, str] = {
    "name": "Me diga seu nome, por favor?",
    "desired_model": "Qual modelo ou tipo de carro você está buscando?",
    "model": "Qual modelo ou tipo de carro você está buscando?",
    "deal_type": "Seria compra ou troca?",
    "down_payment": "Prefere combinar uma entrada ou ir direto pela parcela?",
    "desired_installment": "Até quanto de parcela você tem em mente?",
    "income": "Pode me informar sua renda mensal aproximada?",
    "documents": "Pra montar a simulação, pode me enviar a CNH, um comprovante de residência e um comprovante de renda (holerite)?",
    "vehicle": "Qual modelo ou tipo de carro você está buscando?",
    "vehicle_interest": "Qual modelo ou tipo de carro você está buscando?",
    "brand": "Tem preferência por marca?",
    "trade_in": "Qual marca, modelo e ano do veículo?",
    "trade_model": "Qual marca e modelo do veículo?",
    "trade_year": "Qual o ano do veículo?",
    "trade_color": "Qual a cor do veículo?",
    "trade_has_financing": "O veículo tem financiamento em aberto?",
    "trade_installment_value": "Qual o valor atual da parcela?",
    "trade_installments_remaining": "Quantas parcelas ainda restam?",
    "trade_has_debts": "Tem algum débito pendente no veículo (multas ou licenciamento)?",
    "trade_price_expectation": "Qual o valor que você tem em mente para o seu veículo?",
    "trade_in_owner_is_client": "O documento do veículo está no seu nome?",
    "trade_renavam": "Pode me passar o RENAVAM do veículo?",
    "plate": "Se tiver a placa do veículo, pode me passar?",
    "location": "Você está de qual cidade?",
    "city": "Você é de em qual cidade?",
    "visit": "Que tal segunda-feira, 7/09 às 14h ou terça-feira, 8/09 às 9h30?",
    "timeline": "Em quanto tempo você pensa em fechar?",
    "mileage": "Quantos km rodados tem o veículo, aproximadamente?",
    "asking_price": "Até qual valor você tem em mente?",
    "amount_needed": "Quanto você precisa levantar com o refinanciamento?",
    "leave_at_store": "Topa deixar o carro na loja pra consignação?",
    "year": "Qual o ano do veículo?",
    "intent": "Você está buscando comprar, vender, trocar, consignar ou refinanciar?",
    "payment_method": "Seria à vista ou financiado?",
    "alternatives_ok": "Não encontrei exatamente o que você pediu no estoque atual. Posso te mostrar alternativas parecidas?",
}

_FIELD_QUESTIONS_ES: dict[str, str] = {
    "name": "¿Me dices tu nombre, por favor?",
    "deal_type": "¿Sería compra o permuta?",
    "down_payment": "¿Prefieres combinar una entrada o ir directo por la cuota?",
    "desired_installment": "¿Hasta cuánto de cuota tienes en mente?",
    "income": "¿Cuál es tu ingreso mensual aproximado? (solo para armar la pre-ficha)",
    "documents": "Para armar la pre-ficha, ¿puedes enviarme la licencia y un comprobante de ingresos?",
    "vehicle": "¿Qué modelo o tipo de auto estás buscando?",
    "vehicle_interest": "¿Qué modelo o tipo de auto estás buscando?",
    "brand": "¿Tienes alguna marca de preferencia?",
    "trade_in": "¿Me cuentas marca, modelo y año del vehículo?",
    "trade_model": "¿Cuál es la marca y modelo del vehículo?",
    "trade_year": "¿De qué año es el vehículo?",
    "trade_color": "¿Cuál es el color del vehículo?",
    "trade_has_financing": "¿El vehículo tiene financiamiento vigente?",
    "trade_installment_value": "¿Cuánto es el valor de la cuota actual?",
    "trade_installments_remaining": "¿Cuántas cuotas quedan todavía?",
    "trade_has_debts": "¿Tiene alguna deuda pendiente en el vehículo (multas o patente)?",
    "trade_price_expectation": "¿Cuál es el valor que tienes en mente para tu vehículo?",
    "trade_in_owner_is_client": "¿El documento del vehículo está a tu nombre?",
    "trade_renavam": "¿Puedes pasarme el número de registro del vehículo?",
    "plate": "Si tienes la placa del vehículo, ¿me la pasas?",
    "location": "¿En qué ciudad estás?",
    "visit": "¿Qué día y horario te queda mejor para pasar por la tienda?",
    "payment_method": "¿Sería de contado o financiado?",
    "intent": "¿Estás pensando en comprar, vender, permutar, consignar o refinanciar?",
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
            from sdr.domain.scheduling import format_slot_suggestion, suggest_visit_slots

            offered = list(state.get("offered_visit_slots") or [])
            if not offered:
                inbound_low = str(state.get("inbound_text") or "").lower()
                prefer_sat = "sábado" in inbound_low or "sabado" in inbound_low
                offered = suggest_visit_slots(
                    lang=lang if lang else "pt",
                    prefer_saturday=prefer_sat,
                )
            return format_slot_suggestion(offered, lang=lang if lang else "pt")
        if key == "documents":
            plan = state.get("dialogue_plan") or {}
            remaining = plan.get("remaining_documents") or []
            if remaining and "cnh" not in remaining:
                if lang == "es":
                    return (
                        "Si puedes, envíame también los comprobantes de ingresos y domicilio "
                        "para completar la simulación."
                    )
                return (
                    "Se conseguir, pode me enviar também os comprovantes de renda e residência "
                    "para completar a simulação."
                )
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
            from sdr.domain.vehicle_roles import format_vehicle_label, get_customer_vehicle

            facts = state.get("facts") if isinstance(state.get("facts"), Mapping) else {}
            cv = get_customer_vehicle(facts or {})
            label = format_vehicle_label(cv) or (cv.get("model") if cv else None)
            intent_val = str(getattr(state.get("intent"), "value", state.get("intent") or ""))
            if key == "trade_has_debts" and (
                cv.get("debt_status") == "partial"
                or (isinstance(cv.get("debt_checks"), dict) and cv["debt_checks"].get("fines") == "clear")
            ):
                return "Além das multas, o IPVA e o licenciamento estão em dia?"
            if label and key in {
                "trade_year",
                "trade_color",
                "mileage",
                "trade_has_financing",
                "trade_has_debts",
                "trade_price_expectation",
            } and (intent_val == "trade" or (cv.get("model") and (facts or {}).get("desired_model"))):
                framed = {
                    "trade_year": f"Para avaliar seu {label} na troca, qual o ano dele?",
                    "trade_color": f"Para avaliar seu {label} na troca, qual a cor dele?",
                    "mileage": f"Para avaliar seu {label} na troca, quantos km ele tem?",
                    "trade_has_financing": f"O seu {label} tem financiamento em aberto?",
                    "trade_has_debts": f"O seu {label} tem algum débito pendente, como multas ou licenciamento?",
                    "trade_price_expectation": f"Qual o valor que você tem em mente para o seu {label}?",
                }
                return framed.get(key, questions[key])
            return questions[key]
        if key not in {"budget", "budget_max"}:
            return key
    missing = action_plan.get("missing_fields") or state.get("missing_fields") or []
    if isinstance(missing, list):
        for field in missing:
            if field in {"budget", "budget_max"}:
                return questions["deal_type"]
            if isinstance(field, str) and field == "visit":
                from sdr.domain.scheduling import format_slot_suggestion, suggest_visit_slots

                offered = list(state.get("offered_visit_slots") or [])
                if not offered:
                    offered = suggest_visit_slots(lang=lang if lang else "pt")
                return format_slot_suggestion(offered, lang=lang if lang else "pt")
            if isinstance(field, str) and field in questions:
                return questions[field]
    return None


def _visit_cta_bubbles(state: Mapping[str, Any], lang: str) -> list[str]:
    style = str(state.get("visit_cta_style") or "warm_invite")
    es = lang == "es"
    if state.get("visit_preferred_time") or state.get("visit_accepted_offered"):
        if es:
            return ["Perfecto, registré tu preferencia de visita."]
        return ["Perfeito, registrei sua preferência de visita."]
    if style == "location_close":
        if es:
            return [
                "Podemos evaluar las condiciones de la negociación aquí en la tienda. "
                "Si quieres conocer el vehículo, me dices un día o período."
            ]
        return [
            "Conseguimos avaliar as condições da negociação aqui na loja. "
            "Se quiser conhecer o veículo, me fala um dia ou período que fique melhor."
        ]
    from sdr.domain.scheduling import format_slot_suggestion, suggest_visit_slots

    offered = list(state.get("offered_visit_slots") or [])
    if not offered:
        inbound_low = str(state.get("inbound_text") or "").lower()
        prefer_sat = "sábado" in inbound_low or "sabado" in inbound_low
        offered = suggest_visit_slots(
            lang=lang if lang else "pt",
            prefer_saturday=prefer_sat,
        )
    slot_text = format_slot_suggestion(offered, lang=lang if lang else "pt")
    return [slot_text]


def _document_received_bubbles(
    state: Mapping[str, Any],
    lang: str,
    *,
    question: str | None = None,
) -> list[str]:
    name = _first_name(state)
    kind = str(state.get("document_kind") or "").upper()
    es = lang == "es"
    plan = state.get("dialogue_plan") if isinstance(state.get("dialogue_plan"), dict) else {}
    remaining = list((plan or {}).get("remaining_documents") or [])
    ask_remaining = (plan or {}).get("primary_action") == "ask_remaining_documents" or (
        remaining and "cnh" not in remaining
    )
    if kind == "CNH" or ask_remaining:
        if es:
            ack = f"Recibí tu CNH, {name}." if name else "Recibí tu CNH."
            extra = (
                "Si puedes, envíame también los comprobantes de ingresos y domicilio "
                "para completar la simulación."
            )
        else:
            ack = f"Recebi sua CNH, {name}." if name else "Recebi sua CNH."
            extra = (
                "Se conseguir, pode me enviar também os comprovantes de renda e residência "
                "para completar a simulação."
            )
        bubbles = [ack]
        if ask_remaining:
            bubbles.append(extra)
        return bubbles[:2]
    if es:
        ack = f"Recibí tu documento, {name}." if name else "Recibí tu documento."
    else:
        ack = f"Recebi seu documento, {name}." if name else "Recebi seu documento."
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
        facts = state.get("facts") or {}
        zero_down = facts.get("down_payment") in (0, "0") or facts.get("down_payment") == 0
        if es:
            text = "Entendí tu interés en la compra, sin incluir un vehículo en la negociación."
            if zero_down:
                financing_note = (
                    "Financiamiento sin entrada puede ser posible, "
                    "sujeto al análisis de crédito."
                )
                return [text, financing_note, question] if question else [text, financing_note]
            if question:
                text = f"{text} {question}"
            return [text]
        text = "Entendi seu interesse na compra, sem incluir veículo na negociação."
        if zero_down:
            financing_note = (
                "Financiamento sem entrada pode ser possível, "
                "sujeito à análise de crédito."
            )
            return [text, financing_note, question] if question else [text, financing_note]
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
        facts = state.get("facts") or {}
        zero_down = facts.get("down_payment") == 0 or facts.get("down_payment") == "0"
        if es:
            if zero_down:
                text = (
                    "Podemos hacer una simulación sin entrada. "
                    "La aprobación y las condiciones dependen del análisis de la financiera."
                )
            else:
                text = (
                    "Legal, el financiamiento puede ser una buena opción. "
                    "Conseguimos excelentes condiciones aquí en la tienda."
                )
        else:
            if zero_down:
                text = (
                    "Podemos fazer uma simulação sem entrada. "
                    "A aprovação e as condições dependem da análise da financeira."
                )
            else:
                text = (
                    "Legal, financiamento pode ser uma boa opção pra facilitar. "
                    "Conseguimos ótimas condições aqui na loja."
                )
        # When zero-down already captured, skip re-asking entrada even if
        # ask_field somehow still points at down_payment.
        if zero_down and question and ("entrada" in question.lower() or "entrada" in (question or "").lower()):
            # Fall through: use next question only if it's not the entrada ask.
            # Prefer installment/docs question from directive when present.
            ask = str(action_plan.get("ask_field") or action_plan.get("next_question") or "")
            if ask == "down_payment":
                question = None
        return [text, question] if question else [text]
    if kind == "payment_cash":
        if es:
            text = "Recibí: de contado."
        else:
            text = "Certo, então seria à vista."
        return [text, question] if question else [text]
    if kind == "down_payment":
        # Distinguish zero-entry (financia o valor todo) from positive-entry cases.
        # A zero-entry template must not imply "com uma entrada" — the customer
        # explicitly said they have no entry.
        down_val = (state.get("facts") or {}).get("down_payment")
        no_down = down_val == 0 or down_val == "0"
        if es:
            if no_down:
                text = "Entendido, podemos simular sin entrada. Las condiciones dependen de la financiera."
            else:
                text = "Entendido, anotada la entrada."
        else:
            if no_down:
                text = "Certo, então seria sem entrada. Podemos simular, sujeito à análise da financeira."
            else:
                text = "Certo, anotei a entrada."
        return [text, question] if question else [text]
    if kind == "desired_installment":
        from sdr.domain.vehicle_presentation import format_price_brl

        amount = (state.get("facts") or {}).get("desired_installment")
        formatted = format_price_brl(amount)
        if es:
            text = (
                f"Entendido, buscas una cuota cerca de {formatted}."
                if formatted
                else "Anoté la cuota deseada."
            )
        else:
            text = (
                f"Entendi, você busca uma parcela por volta de {formatted}."
                if formatted
                else "Anotei uma parcela desejada."
            )
        return [text, question] if question else [text]
    if kind == "difference_financing":
        if es:
            text = "De acuerdo, la diferencia será financiada."
        else:
            text = "Certo, a diferença será financiada."
        return [text, question] if question else [text]
    if kind == "difference_cash":
        if es:
            text = "De acuerdo, la diferencia será de contado."
        else:
            text = "Certo, a diferença será à vista."
        return [text, question] if question else [text]
    if kind == "document_received":
        return _document_received_bubbles(state, lang, question=question)
    return None


def _availability_prefix_bubble(state: Mapping[str, Any], lang: str) -> str | None:
    plan = state.get("dialogue_plan") if isinstance(state.get("dialogue_plan"), Mapping) else {}
    if not isinstance(plan, Mapping):
        return None
    kinds = {
        str(q.get("kind"))
        for q in (plan.get("direct_questions") or [])
        if isinstance(q, Mapping)
    }
    status = str(plan.get("availability_status") or "")
    if "availability" not in kinds and status != "available":
        return None
    facts = state.get("facts") if isinstance(state.get("facts"), Mapping) else {}
    label = plan.get("proven_vehicle_label")
    if not label and isinstance(facts, Mapping):
        label = facts.get("desired_model") or facts.get("desired_vehicle_text")
    label = str(label).strip() if label else ("o veículo" if lang != "es" else "el vehículo")
    es = lang == "es"
    if status == "sold":
        return f"Esse {label} já foi vendido." if not es else f"Ese {label} ya fue vendido."
    if status == "reserved":
        return f"Esse {label} está reservado no momento." if not es else f"Ese {label} está reservado."
    if status == "ambiguous":
        return (
            "Encontrei mais de uma possibilidade no estoque. Qual dessas opções é a sua?"
            if not es
            else "Encontré más de una posibilidad. ¿Cuál de esas opciones es la tuya?"
        )
    if status == "available":
        return f"Sim, {label} está disponível." if not es else f"Sí, {label} está disponible."
    if status in {"unresolved", "unpublished", "unknown", ""}:
        if "availability" in kinds:
            return (
                "Não consegui confirmar a disponibilidade desse veículo com segurança."
                if not es
                else "No pude confirmar la disponibilidad de ese vehículo con seguridad."
            )
    return None


def _follow_up_bubble(
    state: Mapping[str, Any],
    action_plan: Mapping[str, Any],
    lang: str,
) -> str:
    """Single next commercial question. Never solicit budget."""
    question = _required_question(state, action_plan, lang)
    if question:
        return question
    questions = _FIELD_QUESTIONS_ES if lang == "es" else _FIELD_QUESTIONS_PT
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
                f"Tenemos {model} en stock. Déjame enviarte las opciones."
            )
        return "¡Hola! ¿Cómo va? Soy Júlia de FacilCar."
    if model:
        media_planned = bool(state.get("outbound_media_planned") or state.get("media_planned"))
        if media_planned:
            return (
                f"Olá! Como vai? Eu sou a Júlia aqui da FacilCar. "
                f"Temos {model} no estoque. Deixa eu te enviar as opções."
            )
        return (
            f"Olá! Como vai? Eu sou a Júlia aqui da FacilCar. "
            f"Vou te mostrar as opções de {model} que encontrei."
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
    plan = state.get("dialogue_plan") if isinstance(state.get("dialogue_plan"), Mapping) else {}

    if action == "no_reply":
        return []

    if (plan or {}).get("primary_action") == "answer_direct_question" and action in (
        "ask_info",
        "register_visit_interest",
    ):
        from sdr.domain.dialogue_plan import DialoguePlan, fallback_bubbles

        parsed = DialoguePlan.from_mapping(plan)
        question = _required_question(state, action_plan, lang)
        bubbles = fallback_bubbles(
            parsed,
            language=lang,
            customer_name=state.get("customer_name") if isinstance(state.get("customer_name"), str) else None,
            next_question=question,
            document_kind=str(state.get("document_kind") or "") or None,
            should_introduce=bool(state.get("should_introduce")),
        )
        if bubbles:
            return bubbles[: parsed.max_text_bubbles or 3]

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
            plan = state.get("dialogue_plan") or {}
            skip_menu = bool(plan.get("skip_generic_intent_menu"))
            inbound = str(state.get("inbound_text") or "")
            return introduction_smalltalk_bubbles(
                lang,
                customer_name=state.get("customer_name"),
                inbound_text=inbound,
                skip_intent_menu=skip_menu,
            )
        courtesy = bool((state.get("dialogue_plan") or {}).get("courtesy_only"))
        return continuation_smalltalk_bubbles(
            lang,
            inbound_text=str(state.get("inbound_text") or ""),
            courtesy=courtesy,
        )

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
            # Extract the model the customer was looking for to use in the response.
            model = (
                (state.get("facts") or {}).get("desired_model")
                or (state.get("facts") or {}).get("desired_vehicle_text")
                or None
            )
            if lang == "es":
                if model:
                    return [
                        f"Hoy no tenemos {model} en stock.",
                        f"Además del {model}, ¿qué otros modelos te interesan?",
                    ]
                return [
                    "No encontré una opción con ese perfil en el stock actual.",
                    "¿Hay algún otro modelo que te interese?",
                ]
            if model:
                return [
                    f"Hoje não temos {model} em estoque.",
                    f"Além do {model}, quais outros modelos você procura?",
                ]
            return [
                "Não encontrei esse perfil no estoque atual.",
                "Quais outros modelos você está procurando?",
            ]

        if outcome == "SUCCESS_SOLD":
            sold_vehicle = (tool_context or {}).get("sold_vehicle") or {}
            if not sold_vehicle and isinstance(offers, list) and offers:
                sold_vehicle = offers[0] if isinstance(offers[0], dict) else {}
            model_sold = (
                (sold_vehicle.get("title") if isinstance(sold_vehicle, dict) else None)
                or (state.get("facts") or {}).get("desired_model")
                or (state.get("facts") or {}).get("desired_vehicle_text")
                or "esse veículo"
            )
            status = ""
            if isinstance(sold_vehicle, dict):
                status = str(sold_vehicle.get("status") or "").upper()
            plan = state.get("dialogue_plan") if isinstance(state.get("dialogue_plan"), Mapping) else {}
            if not status and isinstance(plan, Mapping):
                mapped = str(plan.get("availability_status") or "")
                status = {"sold": "SOLD", "reserved": "RESERVED", "unpublished": "DRAFT"}.get(mapped, "")
            if lang == "es":
                if status == "RESERVED":
                    return [f"El {model_sold} está reservado."]
                return [
                    f"El {model_sold} ya fue vendido.",
                    f"Además del {model_sold}, ¿qué otros modelos te interesan?",
                ]
            if status == "RESERVED":
                return [f"Esse {model_sold} está reservado no momento."]
            if status in {"DRAFT", "ARCHIVED"}:
                return [f"Esse {model_sold} não está disponível no estoque publicado."]
            return [
                f"Esse {model_sold} já foi vendido.",
                f"Além do {model_sold}, quais outros modelos você procura?",
            ]

        if isinstance(offers, list) and offers:
            media_planned = bool((tool_context or {}).get("outbound_media_planned"))
            follow = _follow_up_bubble(state, action_plan, lang)
            prefix = _availability_prefix_bubble(state, lang)
            if media_planned:
                media_state = dict(state)
                media_state["outbound_media_planned"] = True
                bubbles = _with_first_contact(media_state, follow, lang)
            else:
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
                bubbles = bubbles[:3]
            if prefix and prefix.lower() not in " ".join(bubbles).lower():
                bubbles = [prefix, *bubbles]
            return bubbles[:4]
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
        plan = state.get("dialogue_plan") or {}
        if plan.get("primary_action") == "ask_remaining_documents":
            return _document_received_bubbles(state, lang, question=None)[:2]
        if state.get("ack_kind") == "document_received":
            docs = _document_received_bubbles(state, lang)
            # Acknowledgment only — visit is the primary action, do not re-ask remaining docs.
            ack = docs[0] if docs else None
            return [ack, visit[0]][:2] if ack else visit[:1]
        ack = _ack_followup_bubbles(state, {"action": "ask_info"}, lang)
        if ack:
            ack_text = ack[0]
            return [ack_text, visit[0]][:3] if ack_text != visit[0] else visit[:1]
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
        "intent": getattr(getattr(directive, "intent", None), "value", getattr(directive, "intent", None)),
        "outbound_media_planned": bool((tool_context or {}).get("outbound_media_planned")),
        "dialogue_plan": dict(getattr(directive, "dialogue_plan", None) or {}),
        "inbound_text": getattr(directive, "inbound_text", "") or "",
    }
    plan = {
        "action": "show_offers",
        "handoff": False,
        "next_question": getattr(directive, "next_question", None),
        "ask_field": getattr(directive, "next_question", None),
    }
    ctx = dict(tool_context or {})
    ctx["inventory_outcome"] = state["inventory_outcome"]
    ctx["conversational_affordance"] = affordance_val
    ctx["alternative_scope"] = scope_val
    if getattr(directive, "inventory_alternatives", None):
        ctx["alternatives"] = directive.inventory_alternatives
        if outcome == InventoryOutcome.SUCCESS_FOUND and not ctx.get("offers"):
            ctx["offers"] = directive.inventory_alternatives
    bubbles = _template_compose(state, plan, ctx)
    bubbles, meta = _enforce_ask_field_adherence(bubbles, state, plan, _language(state))
    _LAST_COMPOSE_META.update(meta)
    return bubbles


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


def _enforce_ask_field_adherence(
    bubbles: list[str],
    state: Mapping[str, Any],
    action_plan: Mapping[str, Any],
    lang: str,
) -> tuple[list[str], dict[str, Any]]:
    expected = str(action_plan.get("ask_field") or action_plan.get("next_question") or "")
    action = str(action_plan.get("action") or "")
    inv = str(state.get("inventory_outcome") or "")
    if inv in {"SUCCESS_EMPTY", "FAILED_RETRYABLE", "FAILED_TERMINAL", "SUCCESS_SOLD"}:
        return bubbles, {
            "expected_question_field": expected or None,
            "detected_question_field": None,
            "outbound_question": None,
            "match": True,
            "skipped": True,
            "retries": 0,
            "questions_rejected": 0,
            "used_template_fallback": False,
        }
    report = evaluate_adherence(bubbles, expected, action=action)
    if report.get("match"):
        return bubbles, {**report, "retries": 0, "questions_rejected": 0, "used_template_fallback": False}
    safe = _required_question(state, action_plan, lang)
    fixed = replace_question_bubble(bubbles, safe)
    report = evaluate_adherence(fixed, expected, action=action)
    return fixed, {
        **report,
        "retries": 0,
        "questions_rejected": 1,
        "used_template_fallback": True,
    }


_LAST_COMPOSE_META: dict[str, Any] = {
    "adherence": {},
    "retries": 0,
    "questions_rejected": 0,
}


def _finalize_composed_bubbles(
    bubbles: list[str],
    state: Mapping[str, Any],
    action_plan: Mapping[str, Any],
    *,
    language: str,
    should_introduce: bool,
    action: str,
) -> tuple[list[str], dict[str, Any]]:
    bubbles = validate_bubbles(list(bubbles), language=language)
    bubbles, intro_meta = validate_introduction_policy(
        bubbles,
        should_introduce=should_introduce,
        action=action,
        language=language,
    )
    question = _required_question(state, action_plan, language)
    dialogue_meta: dict[str, Any] = {}
    plan = state.get("dialogue_plan")
    if plan:
        bubbles, dialogue_meta = validate_dialogue_plan(
            bubbles,
            plan,
            language=language,
            customer_name=state.get("customer_name") if isinstance(state.get("customer_name"), str) else None,
            next_question=question,
            document_kind=str(state.get("document_kind") or "") or None,
            should_introduce=should_introduce,
        )
    bubbles, meta = _enforce_ask_field_adherence(bubbles, state, action_plan, language)
    meta = {
        **meta,
        "introduction": intro_meta,
        "dialogue": dialogue_meta,
        "requested_acts": (dialogue_meta or {}).get("requested_acts") or (plan or {}).get("acts") or [],
        "realized_acts": (dialogue_meta or {}).get("realized_acts") or [],
        "used_template_fallback": bool((dialogue_meta or {}).get("fallback_used")),
    }
    return bubbles, meta


def last_compose_meta() -> dict[str, Any]:
    return dict(_LAST_COMPOSE_META)


def reset_compose_meta() -> None:
    _LAST_COMPOSE_META.update(
        {
            "adherence": {},
            "retries": 0,
            "questions_rejected": 0,
            "match": True,
            "skipped": True,
            "used_template_fallback": False,
        }
    )


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
    dialogue = state.get("dialogue_plan") if isinstance(state.get("dialogue_plan"), Mapping) else {}
    answering_question = (dialogue or {}).get("primary_action") == "answer_direct_question"

    use_templates = False
    if action in (
        "send_photos",
        "show_offers",
        "send_location",
        "media_failed",
    ):
        use_templates = True
    elif action == "register_visit_interest" and not answering_question:
        use_templates = True
    elif (
        action == "ask_info"
        and str(action_plan.get("ask_field") or action_plan.get("next_question") or "") == "visit"
    ):
        use_templates = True
    elif client is not None and _is_unittest_mock(client):
        use_templates = True
    elif client is None and not api_key:
        use_templates = True
    elif client is None and api_key:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key)

    # ack_kind no longer forces templates: the LLM phrases acknowledgments
    # when a key is present; templates remain the offline / invalid-LLM fallback.

    should_introduce = bool(state.get("should_introduce", False))
    lang = _language(state)

    if use_templates:
        bubbles = _template_compose(state, action_plan, tool_context)
        bubbles, meta = _finalize_composed_bubbles(
            bubbles,
            state,
            action_plan,
            language=lang,
            should_introduce=should_introduce,
            action=action,
        )
        _LAST_COMPOSE_META.update(meta)
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
            "Diga honestamente que não temos esse modelo em estoque no momento. "
            "Em seguida, pergunte quais outros modelos o cliente procura. "
            "NÃO diga que a loja não trabalha com essa categoria ou que nunca terá. "
            "NÃO pergunte 'Quer ver alternativas?' — passe direto para a próxima pergunta."
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
        facts = state.get("facts") or {}
        if facts.get("down_payment") == 0 or facts.get("down_payment") == "0":
            tone_rule += (
                "\nCliente perguntou se financia 100%/sem entrada: responda que "
                "é possível SIMULAR sem entrada; aprovação, taxa e prazo dependem "
                "da financeira. NÃO diga 'vamos financiar o valor todo', "
                "'financiamos 100%', 'você consegue financiar 100%' ou "
                "'dá para financiar todo o valor'. NÃO afirme aprovação. "
                "NÃO pergunte entrada de novo. Depois uma pergunta principal."
            )
        else:
            tone_rule += "\nConfirme o recebimento (financiamento) e avance para a entrada."
    elif ack_kind == "down_payment":
        tone_rule += (
            "\nConfirme que recebeu a informação sobre a entrada e avance. "
            "NÃO diga que as condições tendem a ser melhores."
        )
    elif ack_kind == "document_received":
        tone_rule += (
            "\nDocumento recebido: confirme o recebimento pelo nome (se houver). "
            "NÃO diga que salvou no sistema, na ficha, no Storage ou que já está "
            "disponível para o vendedor. NÃO peça reenvio por falha interna."
        )
    if next_q_text:
        intent_val = str(state.get("intent") or "")
        ask = str(action_plan.get("next_question") or action_plan.get("ask_field") or "")
        # Provide intent-specific framing so the LLM doesn't default to "da troca" language
        if "trade_model" in ask:
            if intent_val in ("sale", "consignment", "refinancing"):
                tone_rule += f"\nPergunta obrigatória deste turno: pergunte sobre o veículo do cliente (NÃO use 'da troca' — este é um atendimento de {intent_val})."
            elif intent_val == "trade":
                tone_rule += f"\nPergunta obrigatória deste turno: {next_q_text}"
            else:
                tone_rule += f"\nPergunta obrigatória deste turno: {next_q_text}"
        elif intent_val == "trade" and ask in {
            "trade_year",
            "trade_color",
            "mileage",
            "trade_has_financing",
            "trade_has_debts",
            "trade_price_expectation",
        }:
            tone_rule += (
                f"\nPergunta obrigatória deste turno: {next_q_text} "
                "Identifique o veículo do cliente (o da troca), não o desejado. "
                "NÃO pergunte genericamente 'Qual a cor do veículo?' / 'Qual o ano do veículo?'."
            )
        else:
            tone_rule += f"\nPergunta obrigatória deste turno: {next_q_text}"
    forbidden = state.get("claims_forbidden") or []
    if "reask_shown_vehicle" in forbidden:
        tone_rule += (
            "\nVeículo já apresentado neste atendimento. NÃO pergunte modelo, ano, "
            "versão ou 'o que você está buscando'. O interesse atual é o veículo "
            "já mostrado (facts.desired_model), salvo o cliente pedir outro explicitamente."
        )
    if state.get("visit_cta_style") == "hot_ask_slot":
        tone_rule += (
            "\nConvite de visita: peça dia e horário concreto. Não use 'sem compromisso'. "
            "Não anuncie que vai encaminhar para um especialista neste turno."
        )

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
            "customer_name": state.get("customer_name") if (state.get("dialogue_plan") or {}).get("use_name") else None,
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
            "dialogue_plan": state.get("dialogue_plan") or {},
        },
        "action_plan": dict(action_plan),
        "tool_results": dict(tool_context or {}),
        "inbound_text": inbound_text,
        "dialogue_plan": state.get("dialogue_plan") or {},
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
    used_llm_fallback = False
    try:
        data = json.loads(raw)
        bubbles = data.get("bubbles") if isinstance(data, Mapping) else None
        if not isinstance(bubbles, list):
            bubbles = _template_compose(state, action_plan, tool_context)
            used_llm_fallback = True
        else:
            bubbles = [str(b) for b in bubbles if b]
    except json.JSONDecodeError:
        logger.warning("compose_response: invalid JSON; using templates")
        bubbles = _template_compose(state, action_plan, tool_context)
        used_llm_fallback = True

    bubbles, meta = _finalize_composed_bubbles(
        bubbles,
        state,
        action_plan,
        language=lang,
        should_introduce=should_introduce,
        action=action,
    )
    retries = 0
    questions_rejected = 0
    dialogue_failed = bool((meta.get("dialogue") or {}).get("violations"))
    report = evaluate_adherence(
        bubbles,
        str(action_plan.get("ask_field") or action_plan.get("next_question") or ""),
        action=action,
    )
    if (not report.get("match") or dialogue_failed) and not used_llm_fallback:
        questions_rejected = 1
        retries = 1
        retry_prompt = (
            system_prompt
            + "\nA resposta anterior violou o plano semântico ou a pergunta canônica. "
            + f"Pergunta canônica: {next_q_text or action_plan.get('ask_field') or 'nenhuma'}. "
            + "Cumpra os atos do dialogue_plan. Não invente, não aprove financiamento, "
            "não use menu genérico, não se reapresente."
        )
        try:
            retry_resp = await client.chat.completions.create(
                model=model,
                temperature=0.2,
                response_format={
                    "type": "json_schema",
                    "json_schema": _COMPOSER_JSON_SCHEMA,
                },
                messages=[
                    {"role": "system", "content": retry_prompt},
                    {
                        "role": "user",
                        "content": json.dumps(payload, ensure_ascii=False),
                    },
                ],
            )
            retry_raw = retry_resp.choices[0].message.content or "{}"
            retry_data = json.loads(retry_raw)
            retry_bubbles = retry_data.get("bubbles") if isinstance(retry_data, Mapping) else None
            if isinstance(retry_bubbles, list) and retry_bubbles:
                bubbles, meta = _finalize_composed_bubbles(
                    [str(b) for b in retry_bubbles if b][:3],
                    state,
                    action_plan,
                    language=lang,
                    should_introduce=should_introduce,
                    action=action,
                )
        except Exception:
            logger.warning("compose_response: semantic retry failed; using validated fallback")
            bubbles = _template_compose(state, action_plan, tool_context)
            bubbles, meta = _finalize_composed_bubbles(
                bubbles,
                state,
                action_plan,
                language=lang,
                should_introduce=should_introduce,
                action=action,
            )
            meta["used_template_fallback"] = True
        meta["retries"] = retries
        meta["questions_rejected"] = questions_rejected + int(meta.get("questions_rejected") or 0)
        _LAST_COMPOSE_META.update(meta)
        return bubbles

    meta["retries"] = 0
    meta["questions_rejected"] = 0
    _LAST_COMPOSE_META.update(meta)
    return bubbles
