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

from sdr.domain.types import (
    ConversationCanonicalState,
    LeadTemperature,
    LifecycleStatus,
)

HANDOFF_CONFIRMATION_PT_BR = (
    "Perfeito. Já organizei as informações e vou encaminhar para nossa equipe "
    "continuar com você por aqui."
)


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
