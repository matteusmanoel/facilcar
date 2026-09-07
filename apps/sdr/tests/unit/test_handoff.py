"""Unit tests for handoff irreversibility."""

from __future__ import annotations

import pytest

from sdr.domain.decision import decide
from sdr.domain.handoff import (
    HANDOFF_CONFIRMATION_PT_BR,
    confirmation_message,
    is_ai_silenced,
    mark_handoff_sent,
    mark_human_active,
)
from sdr.domain.types import (
    Action,
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    HandoffSignals,
    LifecycleState,
    LifecycleStatus,
)


def _state(**kwargs) -> ConversationCanonicalState:
    base = ConversationCanonicalState(
        thread_id="t1",
        customer=CustomerState(phone="5511999999999"),
    )
    for key, value in kwargs.items():
        setattr(base, key, value)
    return base


def test_human_active_irreversible_no_reply() -> None:
    state = _state(
        lifecycle=LifecycleState(status=LifecycleStatus.HUMAN_ACTIVE),
        intent=BusinessIntent.PURCHASE,
        signals=HandoffSignals(explicit_handoff=True),
        facts={"desired_model": "Hilux", "budget": 200000},
    )
    assert is_ai_silenced(state) is True
    plan = decide(state)
    assert plan.action == Action.NO_REPLY


def test_mark_handoff_sent_silences() -> None:
    state = _state(
        lifecycle=LifecycleState(status=LifecycleStatus.READY_FOR_HANDOFF),
        intent=BusinessIntent.SALE,
    )
    mark_handoff_sent(state, "triage_actionable")
    assert state.lifecycle.status == LifecycleStatus.HANDOFF_SENT
    assert is_ai_silenced(state) is True
    plan = decide(state)
    assert plan.action == Action.NO_REPLY


def test_mark_human_active_overrides() -> None:
    state = _state(lifecycle=LifecycleState(status=LifecycleStatus.HANDOFF_SENT))
    mark_human_active(state)
    assert state.lifecycle.status == LifecycleStatus.HUMAN_ACTIVE
    plan = decide(state)
    assert plan.action == Action.NO_REPLY


def test_confirmation_message_pt_br() -> None:
    msg = confirmation_message()
    assert msg == HANDOFF_CONFIRMATION_PT_BR
    assert "encaminhar" in msg.lower()


def test_customer_handoff_bubbles_title_case_and_site() -> None:
    from sdr.domain.handoff import HANDOFF_SITE_URL, customer_handoff_bubbles

    state = _state(
        intent=BusinessIntent.PURCHASE_FINANCING,
        customer=CustomerState(phone="5511999999999", name="MATEUS MANOEL FERREIRA"),
        facts={
            "desired_model": "Corolla",
            "deal_type": "purchase",
            "payment_method": "financing",
            "down_payment": 30000,
        },
    )
    bubbles = customer_handoff_bubbles(state)
    assert len(bubbles) == 2
    assert "Mateus" in bubbles[0]
    assert bubbles[0].startswith("Eu quem agradeço")
    assert "MATEUS MANOEL" not in bubbles[0]
    assert "excelente dia" in bubbles[0].lower()
    assert "CPF" not in bubbles[0]
    assert HANDOFF_SITE_URL in bubbles[1]
    joined = " ".join(bubbles).lower()
    assert "encaminhar para nossa equipe continuar" not in joined


@pytest.mark.asyncio
async def test_process_turn_handoff_uses_narrative_not_ficha() -> None:
    from sdr.application.process_turn import process_turn

    async def understand(text, state):
        from sdr.domain.types import TurnFacts

        return TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING)

    facts = {
        "desired_model": "Civic",
        "deal_type": "purchase",
        "payment_method": "financing",
        "down_payment": 10000,
        "desired_installment": 1500,
    }
    from sdr.domain.decision import inventory_search_key

    state = _state(
        intent=BusinessIntent.PURCHASE_FINANCING,
        customer=CustomerState(phone="5511999999999", name="ANA SOUZA"),
        facts=facts,
        last_inventory_search_key=inventory_search_key(facts),
        documents_asked=True,
        installment_asked=True,
        visit_invited=True,
        assistant_turn_count=4,
    )
    result = await process_turn(state=state, inbound_text="ok", understand=understand)
    assert result.action_plan.action == Action.HANDOFF_VENDOR
    joined = " ".join(result.outbound_texts)
    assert "Ana" in joined
    # triage_actionable reason_code → "Perfeito, Ana!" (not the explicit-handoff template)
    assert "perfeito" in joined.lower()
    assert "facilcarmultimarcas.com.br" in joined.lower()
    assert "ANA SOUZA" not in joined
    assert "Intent:" not in joined

