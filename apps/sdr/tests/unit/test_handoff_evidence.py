"""Handoff evidence policy — irreversible handoff requires auditable evidence."""

from __future__ import annotations

from sdr.domain.decision import decide, inventory_search_key
from sdr.domain.handoff import should_handoff_now
from sdr.domain.types import (
    Action,
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    HandoffSignals,
)
from sdr.understanding.extractor import gate_handoff_signals


def _state(**kwargs) -> ConversationCanonicalState:
    base = ConversationCanonicalState(
        thread_id="t1",
        customer=CustomerState(phone="5511999999999"),
    )
    for key, value in kwargs.items():
        setattr(base, key, value)
    return base


def test_vehicle_plus_budget_not_high_purchase_handoff() -> None:
    gated = gate_handoff_signals(
        "até uns 15 mil",
        HandoffSignals(high_purchase_intent=True),
    )
    state = _state(
        intent=BusinessIntent.PURCHASE,
        facts={"desired_vehicle_text": "qualquer", "budget": 15000},
        signals=gated,
    )
    assert should_handoff_now(state) is False
    plan = decide(state)
    assert plan.reason_code != "high_purchase_intent"


def test_urban_use_plus_budget_not_high_purchase() -> None:
    gated = gate_handoff_signals(
        "uso urbano, até 20 mil",
        HandoffSignals(high_purchase_intent=True),
    )
    assert gated.high_purchase_intent is None


def test_availability_not_explicit_offer() -> None:
    gated = gate_handoff_signals(
        "Vocês têm disponível?",
        HandoffSignals(explicit_offer=True, high_purchase_intent=True),
    )
    assert gated.explicit_offer is None
    assert gated.high_purchase_intent is None


def test_explicit_vendor_request_handoff() -> None:
    state = _state(
        intent=BusinessIntent.PURCHASE,
        signals=HandoffSignals(explicit_handoff=True),
    )
    plan = decide(state)
    assert plan.action == Action.HANDOFF_VENDOR
    assert plan.reason_code == "explicit_vendor"


def test_explicit_offer_handoff() -> None:
    state = _state(
        intent=BusinessIntent.PURCHASE,
        signals=HandoffSignals(explicit_offer=True),
    )
    plan = decide(state)
    assert plan.action == Action.HANDOFF_VENDOR
    assert plan.reason_code == "explicit_offer"


def test_immediate_closing_intent_handoff() -> None:
    text = "Compro hoje"
    gated = gate_handoff_signals(text, HandoffSignals(high_purchase_intent=True))
    assert gated.high_purchase_intent is True
    state = _state(intent=BusinessIntent.PURCHASE, signals=gated)
    plan = decide(state)
    assert plan.action == Action.HANDOFF_VENDOR
    assert plan.reason_code == "high_purchase_intent"


def test_visit_intent_handoff() -> None:
    state = _state(
        intent=BusinessIntent.PURCHASE,
        signals=HandoffSignals(visit_intent=True),
    )
    plan = decide(state)
    assert plan.action == Action.HANDOFF_VENDOR
    assert plan.reason_code == "visit_intent"
    assert any(tc.get("tool") == "register_visit_interest" for tc in plan.tool_calls)


def test_triage_actionable_after_inventory_key_set() -> None:
    facts = {"desired_model": "Civic", "deal_type": "purchase", "payment_method": "cash", "name": "Mateus"}
    state = _state(
        intent=BusinessIntent.PURCHASE,
        facts=facts,
        last_inventory_search_key=inventory_search_key(facts),
    )
    # Visit invitation comes first for eligible intents.
    plan = decide(state)
    assert plan.action == Action.REGISTER_VISIT_INTEREST
    assert state.visit_invited is True

    # After visit invitation, handoff follows.
    plan2 = decide(state)
    assert plan2.action == Action.HANDOFF_VENDOR
    assert plan2.reason_code == "triage_actionable"
