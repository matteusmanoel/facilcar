"""Handoff rules — irreversible silence after confirmation.

LLM may extract handoff-related signals. Deterministic code owns the final
decision. ``high_purchase_intent`` must already be gated by the extractor
(``gate_handoff_signals``) before reaching this module.

Evidence classes
----------------
- explicit_handoff: customer asked for salesperson/human
- explicit_offer: concrete monetary proposal / closing offer
- high_purchase_intent: immediate closing intent (deterministic evidence required)
- visit_intent: explicit desire to visit the store
- triage_actionable: seller can continue (separate from urgency) — decided
  in the Decision Engine, not here
"""

from __future__ import annotations

from sdr.domain.display_name import display_first_name
from sdr.domain.types import (
    ConversationCanonicalState,
    LeadTemperature,
    LifecycleStatus,
)

HANDOFF_CONFIRMATION_PT_BR = (
    "Perfeito. Já organizei as informações e vou encaminhar para nossa equipe "
    "continuar com você por aqui."
)

HANDOFF_SITE_URL = "https://facilcarmultimarcas.com.br"

HANDOFF_SITE_BUBBLE_PT = (
    "Consulte nosso estoque completo e fique por dentro das novidades em nosso site: "
    f"{HANDOFF_SITE_URL}"
)
HANDOFF_SITE_BUBBLE_ES = (
    "Consulta nuestro stock completo y novedades en nuestro sitio: "
    f"{HANDOFF_SITE_URL}"
)


def _interest_narrative(state: ConversationCanonicalState, *, es: bool) -> str:
    desired = (
        state.facts.get("desired_model")
        or state.facts.get("desired_vehicle_text")
        or state.facts.get("vehicle_interest")
    )
    vehicle = str(desired).strip() if isinstance(desired, str) and desired.strip() else None
    trade = state.facts.get("trade_model") or state.facts.get("vehicle_model")
    trade_txt = str(trade).strip() if isinstance(trade, str) and str(trade).strip() else None
    payment = str(state.facts.get("payment_method") or "").strip().lower()
    deal = str(state.facts.get("deal_type") or "").strip().lower()
    down = state.facts.get("down_payment")
    has_down = down not in (None, "", 0, "0")

    if es:
        if trade_txt and vehicle:
            return f"el canje de tu {trade_txt} por el {vehicle} y financiar el resto"
        if payment == "financing" or state.intent.value == "purchase_financing":
            if vehicle and has_down:
                return f"compra financiada con entrada en el {vehicle}"
            if vehicle:
                return f"compra financiada del {vehicle}"
            return "compra financiada"
        if payment in {"cash", "a_vista", "à vista"} or deal == "purchase":
            return f"compra de contado del {vehicle}" if vehicle else "compra de contado"
        if vehicle:
            return f"el {vehicle}"
        return "tu negociación"

    if trade_txt and vehicle:
        return f"trocar o {trade_txt} no {vehicle} e financiar o restante"
    if payment == "financing" or state.intent.value == "purchase_financing":
        if vehicle and has_down:
            return f"compra financiada com entrada no {vehicle}"
        if vehicle:
            return f"compra financiada no {vehicle}"
        return "compra financiada"
    if payment in {"cash", "a_vista", "à vista"}:
        return f"compra à vista no {vehicle}" if vehicle else "compra à vista"
    if deal == "purchase" and vehicle:
        return f"compra no {vehicle}"
    if vehicle:
        return f"o {vehicle}"
    return "sua negociação"


def customer_handoff_bubbles(state: ConversationCanonicalState) -> list[str]:
    """WhatsApp close: thanks + specialist, then site. CRM keeps vendor_summary."""
    es = (state.language or "").lower().startswith("es")
    name = display_first_name(state.customer.name)
    if es:
        thanks = (
            f"Yo te agradezco{f', {name}' if name else ''}. Ya reuní tu información "
            "y pronto uno de nuestros especialistas se pondrá en contacto. "
            "Que tengas un excelente día."
        )
        return [thanks, HANDOFF_SITE_BUBBLE_ES]
    thanks = (
        f"Eu quem agradeço{f', {name}' if name else ''}. Já reuni suas informações "
        "e logo um dos nossos especialistas entrará em contato. Tenha um excelente dia."
    )
    return [thanks, HANDOFF_SITE_BUBBLE_PT]


def should_handoff_now(state: ConversationCanonicalState) -> bool:
    """True when gated signals require immediate handoff (bypass triage).

    Does NOT include triage actionability — that is a separate decision path
    that must respect inventory-first policy in the Decision Engine.
    """
    if state.lifecycle.status in (
        LifecycleStatus.HANDOFF_SENT,
        LifecycleStatus.HUMAN_ACTIVE,
    ):
        return False
    sig = state.signals
    return any(
        (
            sig.explicit_handoff is True,
            sig.explicit_offer is True,
            sig.high_purchase_intent is True,
            sig.visit_intent is True,
        )
    )


def is_ai_silenced(state: ConversationCanonicalState) -> bool:
    """HUMAN_ACTIVE and HANDOFF_SENT forbid further AI replies."""
    return state.lifecycle.status in (
        LifecycleStatus.HANDOFF_SENT,
        LifecycleStatus.HUMAN_ACTIVE,
    )


def mark_handoff_sent(state: ConversationCanonicalState, reason: str | None = None) -> None:
    """Transition READY_FOR_HANDOFF → HANDOFF_SENT (exactly one auto message)."""
    if state.lifecycle.status == LifecycleStatus.HUMAN_ACTIVE:
        return
    state.lifecycle.status = LifecycleStatus.HANDOFF_SENT
    if reason:
        state.lifecycle.handoff_reason = reason


def mark_human_active(state: ConversationCanonicalState) -> None:
    """Irreversible for the active thread until HUMAN_CLOSED + new intent."""
    state.lifecycle.status = LifecycleStatus.HUMAN_ACTIVE


def confirmation_message(_: ConversationCanonicalState | None = None) -> str:
    """Single PT-BR handoff confirmation template."""
    return HANDOFF_CONFIRMATION_PT_BR


def compute_temperature(state: ConversationCanonicalState) -> LeadTemperature:
    """Visual aid only — never a handoff gate."""
    sig = state.signals
    if (
        sig.explicit_handoff is True
        or sig.explicit_offer is True
        or sig.high_purchase_intent is True
        or sig.visit_intent is True
    ):
        return LeadTemperature.HOT
    if state.business.actionability.value in ("ACTIONABLE", "HANDOFF_NOW"):
        return LeadTemperature.HOT
    if state.intent.value not in ("unknown", "smalltalk"):
        return LeadTemperature.WARM
    return LeadTemperature.COLD
