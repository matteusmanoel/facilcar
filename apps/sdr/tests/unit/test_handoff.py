"""Unit tests for handoff irreversibility."""

from __future__ import annotations

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
