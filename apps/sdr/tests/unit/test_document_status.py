"""Granular document deferral and status."""

from __future__ import annotations

from sdr.domain.document_status import parse_document_deferral
from sdr.domain.merge import deterministic_merge
from sdr.domain.qualifications import next_ask_field, refresh_actionability
from sdr.domain.types import (
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    TurnFacts,
)


def _state(**kwargs) -> ConversationCanonicalState:
    base = ConversationCanonicalState(
        thread_id="t1",
        customer=CustomerState(phone="5511999999999"),
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts={"desired_model": "HB20", "desired_installment": 2500, "down_payment": 0},
        pending_question="documents",
        documents_asked=True,
    )
    for key, value in kwargs.items():
        setattr(base, key, value)
    return base


def test_cnh_later_defers_only_cnh() -> None:
    parsed = parse_document_deferral("Posso enviar a CNH depois")
    assert parsed == {"cnh": "deferred"}


def test_all_documents_later() -> None:
    parsed = parse_document_deferral("Não tenho os documentos no momento")
    assert parsed["cnh"] == "deferred"
    assert parsed["proof_of_residence"] == "deferred"
    assert parsed["proof_of_income"] == "deferred"


def test_merge_cnh_deferral_is_granular() -> None:
    prev = _state()
    facts = TurnFacts(
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts={"documents_deferred": True},
    )
    merged = deterministic_merge(prev, facts, inbound_text="Posso enviar a CNH depois")
    merged = refresh_actionability(merged)
    assert "cnh" in merged.deferred_fields
    assert "proof_of_residence" not in merged.deferred_fields
    assert "proof_of_income" not in merged.deferred_fields
    assert merged.facts.get("document_status", {}).get("cnh") == "deferred"
    assert "documents" not in merged.collected_fields
    assert merged.profile_complete is False
    assert next_ask_field(merged) == "name"


def test_handoff_allowed_with_deferred_cnh() -> None:
    prev = _state(facts={
        "desired_model": "HB20",
        "desired_installment": 2500,
        "down_payment": 0,
        "name": "Marina Dias",
        "documents_deferred": True,
        "document_status": {"cnh": "deferred"},
    })
    prev.customer.name = "Marina Dias"
    prev.deferred_fields = ["cnh"]
    prev.documents_asked = True
    prev = refresh_actionability(prev)
    assert prev.handoff_ready is True
    assert prev.profile_complete is False
    assert "proof_of_residence" in prev.missing_fields
    assert "proof_of_income" in prev.missing_fields


def test_cnh_received_leaves_other_docs_missing() -> None:
    prev = _state(facts={
        "desired_model": "HB20",
        "desired_installment": 2500,
        "down_payment": 0,
        "name": "Marina Dias",
        "document_status": {"cnh": "received"},
    })
    prev.customer.name = "Marina Dias"
    prev.document_received = True
    prev.documents_asked = True
    prev = refresh_actionability(prev)
    assert "cnh" in prev.collected_fields
    assert "proof_of_residence" in prev.missing_fields
    assert prev.profile_complete is False


def test_no_documents_now_defers_pack() -> None:
    parsed = parse_document_deferral("Não tenho agora")
    assert parsed["cnh"] == "deferred"
    assert parsed["proof_of_income"] == "deferred"
