"""Handoff rules — commercial event, not automation shutdown.

LLM may extract handoff-related signals. Deterministic code owns the final
decision. ``high_purchase_intent`` must already be gated by the extractor
(``gate_handoff_signals``) before reaching this module.

``HANDOFF_SENT`` means the vendor was notified and the AI stays active.
Silence begins only on explicit ``HUMAN_ACTIVE`` (assume).

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


def customer_handoff_bubbles(
    state: ConversationCanonicalState,
    reason_code: str | None = None,
) -> list[str]:
    """WhatsApp close: honest about what was collected; never fake completeness."""
    es = (state.language or "").lower().startswith("es")
    name = display_first_name(state.customer.name)
    incomplete = not getattr(state, "profile_complete", False)
    empty_lead = not (state.facts or {}) and not name
    site = HANDOFF_SITE_BUBBLE_ES if es else HANDOFF_SITE_BUBBLE_PT

    if reason_code == "explicit_vendor" or (
        state.signals.explicit_handoff is True and empty_lead
    ):
        msg = (
            "Claro. Vou encaminhar seu atendimento para um dos nossos vendedores continuar com você."
            if not es
            else "Claro. Voy a pasar tu atención a uno de nuestros vendedores para que continúe contigo."
        )
        return [msg]

    from sdr.domain.visit import should_send_store_location, visit_confirmation_bubbles

    visit_bubbles = visit_confirmation_bubbles(
        state,
        include_location=should_send_store_location(state),
        handoff=True,
    )
    if visit_bubbles:
        return visit_bubbles

    if reason_code in {
        "triage_complete",
        "triage_actionable",
        "handoff_ready",
        "visit_invitation_pre_handoff",
    }:
        if incomplete:
            thanks = (
                f"Perfeito{f', {name}' if name else ''}! "
                "Vou encaminhar para um dos nossos vendedores continuar com você."
            )
        else:
            thanks = (
                f"Perfeito{f', {name}' if name else ''}! "
                "Já organizei as informações e vou encaminhar para nossa equipe continuar com você."
            )
        return [thanks, site]

    thanks = (
        f"Claro{f', {name}' if name else ''}. "
        "Vou encaminhar seu atendimento para um dos nossos vendedores continuar com você."
    )
    return [thanks, site]


def should_handoff_now(state: ConversationCanonicalState) -> bool:
    """True when gated signals require immediate handoff (bypass triage).

    Visit intent without a recorded preference is not immediate handoff —
    Decision may still invite once, then close when qualification is ready.
    Exact clock time is never required.
    """
    if state.lifecycle.status in (
        LifecycleStatus.HANDOFF_SENT,
        LifecycleStatus.HUMAN_ACTIVE,
        LifecycleStatus.AI_RESUMED,
    ):
        return False
    sig = state.signals
    if sig.explicit_handoff is True:
        return True
    if sig.explicit_offer is True:
        return True
    if sig.high_purchase_intent is True:
        return True
    if sig.visit_intent is True:
        from sdr.domain.visit import has_visit_preference

        if getattr(state, "visit_accepted_offered", False) or getattr(state, "visit_time", None):
            return True
        if state.visit_invited and has_visit_preference(state):
            return True
    return False


def is_ai_silenced(state: ConversationCanonicalState) -> bool:
    """Only HUMAN_ACTIVE forbids further AI replies."""
    return state.lifecycle.status == LifecycleStatus.HUMAN_ACTIVE


def mark_handoff_sent(state: ConversationCanonicalState, reason: str | None = None) -> None:
    """Transition READY_FOR_HANDOFF → HANDOFF_SENT (vendor notified, AI still active)."""
    if state.lifecycle.status == LifecycleStatus.HUMAN_ACTIVE:
        return
    state.lifecycle.status = LifecycleStatus.HANDOFF_SENT
    if reason:
        state.lifecycle.handoff_reason = reason
    if not state.handoff_at:
        from sdr.domain.clock import now_brt

        state.handoff_at = now_brt().isoformat()


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
