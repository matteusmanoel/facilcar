"""Unit tests for deterministic_merge."""

from __future__ import annotations

from sdr.domain.merge import deterministic_merge
from sdr.domain.types import (
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    HandoffSignals,
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


def test_omission_preserves_cpf() -> None:
    prev = _state(facts={"cpf": "12345678901", "desired_model": "Hilux"})
    facts = TurnFacts(
        intent=BusinessIntent.PURCHASE,
        facts={"budget": 250000},
        signals=HandoffSignals(),
    )
    merged = deterministic_merge(prev, facts)
    assert merged.facts["cpf"] == "12345678901"
    assert merged.facts["desired_model"] == "Hilux"
    assert merged.facts["budget"] == 250000


def test_unknown_signal_does_not_become_false() -> None:
    prev = _state(signals=HandoffSignals(explicit_handoff=True))
    facts = TurnFacts(
        intent=BusinessIntent.PURCHASE,
        facts={},
        signals=HandoffSignals(explicit_handoff=None),  # omitted / unknown
    )
    merged = deterministic_merge(prev, facts)
    assert merged.signals.explicit_handoff is True


def test_missing_signal_does_not_clear_true() -> None:
    prev = _state(signals=HandoffSignals(high_purchase_intent=True))
    facts = TurnFacts(intent=BusinessIntent.PURCHASE, signals=HandoffSignals())
    merged = deterministic_merge(prev, facts)
    assert merged.signals.high_purchase_intent is True


def test_critical_conflict_sets_pending_confirmation() -> None:
    prev = _state(facts={"cpf": "11111111111"})
    facts = TurnFacts(
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts={"cpf": "22222222222"},
        signals=HandoffSignals(),
    )
    merged = deterministic_merge(prev, facts)
    assert merged.facts["cpf"] == "11111111111"
    assert "cpf" in merged.pending_confirmation


def test_explicit_correction_overwrites_critical() -> None:
    prev = _state(facts={"plate": "ABC1D23"})
    facts = TurnFacts(
        intent=BusinessIntent.SALE,
        facts={"plate": "XYZ9K87"},
        explicit_corrections=["plate"],
        signals=HandoffSignals(),
    )
    merged = deterministic_merge(prev, facts)
    assert merged.facts["plate"] == "XYZ9K87"
    assert "plate" not in merged.pending_confirmation


def test_prefer_more_specific_intent() -> None:
    prev = _state(intent=BusinessIntent.PURCHASE)
    facts = TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING, signals=HandoffSignals())
    merged = deterministic_merge(prev, facts)
    assert merged.intent == BusinessIntent.PURCHASE_FINANCING


def test_unknown_fact_does_not_delete() -> None:
    prev = _state(facts={"birth_date": "1990-01-01"})
    facts = TurnFacts(
        intent=BusinessIntent.PURCHASE,
        facts={"birth_date": "unknown"},
        signals=HandoffSignals(),
    )
    merged = deterministic_merge(prev, facts)
    assert merged.facts["birth_date"] == "1990-01-01"


def test_merge_preserves_operational_protocol_fields() -> None:
    """pending_question / visit_invited must survive merge — omission is not reset."""
    prev = _state(intent=BusinessIntent.PURCHASE, facts={"desired_model": "Corolla"})
    prev.pending_question = "deal_type"
    prev.visit_invited = True
    prev.documents_asked = True
    prev.engagement_low_streak = 2
    facts = TurnFacts(intent=BusinessIntent.PURCHASE, facts={"deal_type": "purchase"})
    merged = deterministic_merge(prev, facts)
    assert merged.pending_question == "deal_type"
    assert merged.visit_invited is True
    assert merged.documents_asked is True
    assert merged.engagement_low_streak == 2


def test_document_name_replaces_whatsapp_placeholder() -> None:
    prev = _state(
        customer=CustomerState(phone="554588230845", name="WhatsApp 0845"),
    )
    facts = TurnFacts(
        intent=BusinessIntent.PURCHASE,
        facts={"name": "João Souza", "desired_model": "corolla"},
    )
    merged = deterministic_merge(prev, facts)
    assert merged.customer.name == "João Souza"


def test_unknown_turn_intent_does_not_overwrite_canonical_sale() -> None:
    prev = _state(
        intent=BusinessIntent.SALE,
        facts={"trade_model": "Corolla", "trade_has_financing": False},
    )
    facts = TurnFacts(
        intent=BusinessIntent.UNKNOWN,
        facts={"name": "Bruno Azevedo"},
        signals=HandoffSignals(),
    )
    merged = deterministic_merge(prev, facts)
    assert facts.intent == BusinessIntent.UNKNOWN
    assert merged.intent == BusinessIntent.SALE
    assert merged.facts.get("name") == "Bruno Azevedo"
    assert merged.facts.get("trade_model") == "Corolla"


def test_merge_preserves_ownership_fields() -> None:
    from sdr.domain.types import LifecycleState, LifecycleStatus

    prev = _state(
        lifecycle=LifecycleState(status=LifecycleStatus.AI_RESUMED),
        ownership_revision=2,
        assumed_by_user_id="user-1",
        resumed_by_user_id="user-1",
        resume_reason="seller_released",
        handoff_at="2026-09-07T10:00:00-03:00",
        vendor_notified_at="2026-09-07T10:00:00-03:00",
    )
    facts = TurnFacts(intent=BusinessIntent.PURCHASE, facts={"desired_model": "Civic"})
    merged = deterministic_merge(prev, facts)
    assert merged.lifecycle.status == LifecycleStatus.AI_RESUMED
    assert merged.ownership_revision == 2
    assert merged.assumed_by_user_id == "user-1"
    assert merged.resumed_by_user_id == "user-1"
    assert merged.resume_reason == "seller_released"
    assert merged.handoff_at == "2026-09-07T10:00:00-03:00"
    assert merged.vendor_notified_at == "2026-09-07T10:00:00-03:00"


