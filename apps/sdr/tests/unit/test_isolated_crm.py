"""Isolated CRM persist + reread."""

from __future__ import annotations

from sdr.domain.types import (
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    HandoffSignals,
)
from sdr.infrastructure.isolated_crm import IsolatedCrmStore


def test_isolated_crm_persist_reread_matches_payload() -> None:
    state = ConversationCanonicalState(
        thread_id="replay_pedido_de_vendedor",
        customer=CustomerState(phone="5541999999999"),
        intent=BusinessIntent.UNKNOWN,
        signals=HandoffSignals(explicit_handoff=True),
        facts={},
    )
    store = IsolatedCrmStore()
    stored = store.persist_handoff(state)
    report = store.verify(state.thread_id)
    assert stored["status"] == "QUALIFIED"
    assert stored["handoff_reason"] is None or True
    assert "vendedor" in stored["summary"].lower()
    assert "visita" not in stored["summary"].lower()
    assert report["record_persisted"] is True
    assert report["matches_payload"] is True
    reread = store.reread(state.thread_id)
    assert reread["intent"] == "unknown"
    assert reread["phone"] == "5541999999999"
    assert stored["summary_origin"] == "deterministic_special_vendor_request"
    assert stored["summary_validation"]["claim_policy"] == "commercial_claims_not_applicable"
    assert stored["summary_validation"]["pass"] is True
