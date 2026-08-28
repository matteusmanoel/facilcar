"""Unit tests for decide()."""

from __future__ import annotations

from sdr.domain.decision import decide, inventory_search_key
from sdr.domain.merge import deterministic_merge
from sdr.domain.types import (
    Action,
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    HandoffSignals,
    LifecycleState,
    LifecycleStatus,
    TurnFacts,
)


def _state(**kwargs) -> ConversationCanonicalState:
    base = ConversationCanonicalState(
        thread_id="t1",
        customer=CustomerState(phone="5511999999999"),
    )
    for key, value in kwargs.items():
        setattr(base, key, value)
    return base


# ---------------------------------------------------------------------------
# UNKNOWN → COMMERCIAL_UNKNOWN (critical contract)
# ---------------------------------------------------------------------------

def test_unknown_intent_produces_commercial_unknown_not_smalltalk() -> None:
    """UNKNOWN intent must produce COMMERCIAL_UNKNOWN, never SMALLTALK.

    SMALLTALK is for recognized greeting/chitchat.
    UNKNOWN is for unclassified language — must produce a recovery clarification.
    """
    state = _state(intent=BusinessIntent.UNKNOWN)
    plan = decide(state)
    assert plan.action == Action.COMMERCIAL_UNKNOWN, (
        f"UNKNOWN intent must produce COMMERCIAL_UNKNOWN, got {plan.action!r}. "
        "This was returning SMALLTALK, causing generic greeting responses for "
        "unrecognized commercial language."
    )
    assert plan.reason_code == "unresolved_intent"
    assert plan.handoff is False


def test_unknown_intent_is_not_classified_as_greeting_chitchat() -> None:
    """UNKNOWN intent reason_code must never be 'greeting_or_chitchat'."""
    state = _state(intent=BusinessIntent.UNKNOWN)
    plan = decide(state)
    assert plan.reason_code != "greeting_or_chitchat", (
        "reason_code='greeting_or_chitchat' is reserved for SMALLTALK intent only."
    )


def test_smalltalk_intent_produces_smalltalk_action() -> None:
    """SMALLTALK intent (recognized greeting) must still produce SMALLTALK action."""
    state = _state(intent=BusinessIntent.SMALLTALK)
    plan = decide(state)
    assert plan.action == Action.SMALLTALK
    assert plan.reason_code == "greeting_or_chitchat"
    assert plan.handoff is False


# ---------------------------------------------------------------------------
# Inventory search key deduplication
# ---------------------------------------------------------------------------

def test_inventory_lookup_when_model_known() -> None:
    """When model is known + commercial intent, show inventory FIRST."""
    state = _state(intent=BusinessIntent.PURCHASE, facts={"desired_model": "Civic"})
    plan = decide(state)
    assert plan.action == Action.SHOW_OFFERS
    assert any(tc.get("tool") == "inventory_search" for tc in plan.tool_calls)


def test_inventory_not_repeated_when_search_key_matches() -> None:
    """When search key matches last_inventory_search_key, skip re-search → ASK_INFO."""
    facts = {"desired_model": "Civic"}
    key = inventory_search_key(facts)
    state = _state(
        intent=BusinessIntent.PURCHASE,
        facts=facts,
        last_inventory_search_key=key,
    )
    plan = decide(state)
    assert plan.action == Action.ASK_INFO
    assert plan.ask_field == "deal_type"


def test_inventory_re_searched_when_preference_changes() -> None:
    """When customer changes preferred model, inventory_search_key changes → re-search."""
    old_key = inventory_search_key({"desired_model": "Civic"})
    state = _state(
        intent=BusinessIntent.PURCHASE,
        facts={"desired_model": "Corolla"},  # changed from Civic
        last_inventory_search_key=old_key,
    )
    plan = decide(state)
    assert plan.action == Action.SHOW_OFFERS
    assert any(tc.get("tool") == "inventory_search" for tc in plan.tool_calls)


def test_inventory_search_key_changes_with_budget() -> None:
    from sdr.domain.budget_status import BudgetStatus

    key1 = inventory_search_key({"desired_model": "Civic"})
    key2 = inventory_search_key(
        {"desired_model": "Civic", "budget": 50000},
        budget_status=BudgetStatus.PROVIDED,
    )
    assert key1 != key2


def test_inventory_search_key_ignores_qualification_status_without_budget() -> None:
    """Entrada / financing status must not retrigger SHOW_OFFERS."""
    from sdr.domain.budget_status import BudgetStatus

    facts = {"desired_model": "Corolla"}
    key1 = inventory_search_key(facts)
    key2 = inventory_search_key(facts, budget_status=BudgetStatus.PROVIDED)
    assert key1 == key2


def test_ask_info_after_inventory_already_searched() -> None:
    """After inventory, progress to qualification (deal type), never budget."""
    facts = {"desired_model": "Civic"}
    state = _state(
        intent=BusinessIntent.PURCHASE,
        facts=facts,
        last_inventory_search_key=inventory_search_key(facts),
    )
    plan = decide(state)
    assert plan.action == Action.ASK_INFO
    assert plan.ask_field == "deal_type"


def test_photo_request_sends_photos_of_last_shown_vehicle() -> None:
    facts = {"desired_model": "Civic"}
    state = _state(
        intent=BusinessIntent.PURCHASE,
        facts=facts,
        last_inventory_search_key=inventory_search_key(facts),
        last_shown_vehicle_ids=["veh-civic-1"],
        photo_request=True,
    )
    plan = decide(state)
    assert plan.action == Action.SEND_PHOTOS
    assert any(tc.get("tool") == "send_photos" for tc in plan.tool_calls)
    assert plan.ask_field != "budget"


def test_location_request_interrupts_visit_and_handoff() -> None:
    facts = {
        "desired_model": "Corolla",
        "deal_type": "purchase",
        "payment_method": "financing",
        "down_payment": 20000,
    }
    state = _state(
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts=facts,
        last_inventory_search_key=inventory_search_key(facts),
        documents_asked=True,
        location_request=True,
    )
    plan = decide(state)
    assert plan.action == Action.SEND_LOCATION
    assert plan.ask_field == "visit"
    assert any(tc.get("tool") == "send_location" for tc in plan.tool_calls)
    assert plan.handoff is False


def test_document_received_acks_instead_of_visit() -> None:
    facts = {
        "desired_model": "Corolla",
        "deal_type": "purchase",
        "down_payment": 20000,
    }
    state = _state(
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts=facts,
        last_inventory_search_key=inventory_search_key(facts),
        documents_asked=True,
        document_received=True,
    )
    plan = decide(state)
    assert plan.action == Action.ASK_INFO
    assert plan.reason_code == "document_received_ack"
    assert plan.handoff is False


# ---------------------------------------------------------------------------
# Standard decision paths
# ---------------------------------------------------------------------------

def test_explicit_vendor_handoff() -> None:
    state = _state(
        intent=BusinessIntent.UNKNOWN,
        signals=HandoffSignals(explicit_handoff=True),
    )
    plan = decide(state)
    assert plan.action == Action.HANDOFF_VENDOR
    assert plan.handoff is True
    assert plan.reason_code == "explicit_vendor"


def test_actionable_purchase_handoff() -> None:
    """Vehicle + deal_type triggers visit invitation, then handoff."""
    facts = {
        "desired_model": "Hilux",
        "deal_type": "purchase",
        "payment_method": "cash",
    }
    from sdr.domain.decision import inventory_search_key

    state = _state(
        intent=BusinessIntent.PURCHASE,
        facts=facts,
        last_inventory_search_key=inventory_search_key(facts),
    )
    # First: visit invitation (pre-handoff step for eligible intents).
    plan = decide(state)
    assert plan.action == Action.REGISTER_VISIT_INTEREST
    assert plan.handoff is False
    assert state.visit_invited is True

    # Second: actual handoff after visit invitation was sent.
    plan2 = decide(state)
    assert plan2.action == Action.HANDOFF_VENDOR
    assert plan2.handoff is True
    assert plan2.reason_code == "triage_actionable"


def test_vehicle_and_budget_inventory_before_handoff() -> None:
    """Preference + budget must not skip inventory on first opportunity."""
    state = _state(
        intent=BusinessIntent.PURCHASE,
        facts={"desired_vehicle_text": "scooter elétrico", "budget": 15000},
    )
    plan = decide(state)
    assert plan.action == Action.SHOW_OFFERS
    assert any(tc.get("tool") == "inventory_search" for tc in plan.tool_calls)
    assert plan.handoff is False


def test_budget_alone_does_not_set_high_purchase_handoff() -> None:
    state = _state(
        intent=BusinessIntent.PURCHASE,
        facts={"desired_vehicle_text": "qualquer", "budget": 15000},
        signals=HandoffSignals(high_purchase_intent=True),  # would be gated upstream
    )
    # Even if a stale True leaked, inventory-first still applies when key mismatch;
    # should_handoff_now WOULD fire if signal is True. Gate must strip it upstream.
    # Here we verify explicit vendor path still works when signal is real.
    from sdr.understanding.extractor import gate_handoff_signals

    gated = gate_handoff_signals(
        "É pra uso urbano mesmo, até uns 15 mil",
        HandoffSignals(high_purchase_intent=True),
    )
    assert gated.high_purchase_intent is None
    state.signals = gated
    plan = decide(state)
    assert plan.reason_code != "high_purchase_intent"
    assert plan.action != Action.HANDOFF_VENDOR or plan.reason_code == "triage_actionable"
    # With inventory pending, must be show_offers:
    assert plan.action == Action.SHOW_OFFERS



def test_human_active_no_reply() -> None:
    state = _state(
        lifecycle=LifecycleState(status=LifecycleStatus.HUMAN_ACTIVE),
        signals=HandoffSignals(explicit_handoff=True),
        intent=BusinessIntent.PURCHASE,
        facts={"desired_model": "Hilux", "budget": 100000},
    )
    plan = decide(state)
    assert plan.action == Action.NO_REPLY


def test_handoff_sent_no_reply() -> None:
    state = _state(
        lifecycle=LifecycleState(status=LifecycleStatus.HANDOFF_SENT),
        intent=BusinessIntent.PURCHASE,
    )
    plan = decide(state)
    assert plan.action == Action.NO_REPLY


def test_merge_then_decide_high_purchase() -> None:
    prev = _state(intent=BusinessIntent.PURCHASE, facts={"desired_model": "Onix"})
    facts = TurnFacts(
        intent=BusinessIntent.PURCHASE,
        facts={"budget": 70000},
        signals=HandoffSignals(high_purchase_intent=True),
    )
    merged = deterministic_merge(prev, facts)
    plan = decide(merged)
    assert plan.action == Action.HANDOFF_VENDOR
    assert plan.handoff is True
