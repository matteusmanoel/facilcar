"""profile_complete / deferred / collected semantics."""

from __future__ import annotations

from sdr.domain.qualifications import collected_fields, is_handoff_ready, refresh_actionability
from sdr.domain.types import BusinessIntent, ConversationCanonicalState, CustomerState


def test_deferred_documents_are_not_collected_and_profile_incomplete() -> None:
    state = ConversationCanonicalState(
        thread_id="t",
        customer=CustomerState(phone="1", name="Carlos Souza"),
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts={
            "desired_model": "HB20",
            "desired_vehicle": {"model": "HB20"},
            "down_payment": 10000,
            "desired_installment": 1200,
            "documents_deferred": True,
            "name": "Carlos Souza",
        },
        deferred_fields=["cnh", "proof_of_residence", "proof_of_income"],
        documents_asked=True,
    )
    refresh_actionability(state)
    assert "documents" not in (state.collected_fields or [])
    assert state.deferred_fields
    assert state.profile_complete is False
    assert is_handoff_ready(state) is True


def test_cnh_later_does_not_mark_documents_collected() -> None:
    state = ConversationCanonicalState(
        thread_id="t",
        customer=CustomerState(phone="1", name="Marina Dias"),
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts={
            "desired_model": "HB20",
            "down_payment": 0,
            "desired_installment": 2500,
            "documents_deferred": True,
            "name": "Marina Dias",
        },
        deferred_fields=["cnh"],
        documents_asked=True,
    )
    refresh_actionability(state)
    assert "documents" not in collected_fields(state)
    assert state.profile_complete is False
    assert is_handoff_ready(state) is True


def test_renavam_is_not_a_missing_blocker() -> None:
    state = ConversationCanonicalState(
        thread_id="t",
        customer=CustomerState(phone="1", name="Bruno Azevedo"),
        intent=BusinessIntent.SALE,
        facts={
            "trade_model": "Corolla",
            "trade_year": "2020",
            "trade_color": "prata",
            "mileage": 50000,
            "trade_has_financing": False,
            "trade_has_debts": False,
            "trade_price_expectation": 80000,
            "name": "Bruno Azevedo",
            "customer_vehicle": {
                "model": "Corolla",
                "year": "2020",
                "color": "prata",
                "mileage": 50000,
                "financing_status": "paid_off",
                "debt_status": "clear",
                "price_expectation": 80000,
            },
        },
    )
    refresh_actionability(state)
    assert "trade_renavam" not in (state.missing_fields or [])
    if state.profile_complete:
        assert not state.missing_fields
