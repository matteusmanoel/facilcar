"""Partial debt inferences must not clear all debts."""

from __future__ import annotations

from sdr.domain.pending_question import overlay_pending_question
from sdr.domain.types import (
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    TurnFacts,
)


def test_no_fines_does_not_mean_no_debts() -> None:
    state = ConversationCanonicalState(
        thread_id="t",
        customer=CustomerState(phone="1"),
        intent=BusinessIntent.TRADE,
        pending_question="trade_has_debts",
        facts={"trade_model": "Ka", "trade_year": "2019"},
    )
    facts = overlay_pending_question(
        TurnFacts(intent=BusinessIntent.TRADE, facts={}),
        state,
        "Não tenho multas",
    )
    assert facts.facts.get("trade_has_debts") is not False
    assert facts.facts.get("debt_status") == "partial"
    checks = facts.facts.get("debt_checks") or {}
    nested = (facts.facts.get("customer_vehicle") or {}).get("debt_checks") or checks
    assert nested.get("fines") == "clear"
    assert nested.get("ipva") in (None, "unknown")
    assert facts.facts.get("trade_debt_type") not in {"sem_multas"}


def test_tudo_em_dia_clears_debts() -> None:
    state = ConversationCanonicalState(
        thread_id="t",
        customer=CustomerState(phone="1"),
        intent=BusinessIntent.TRADE,
        pending_question="trade_has_debts",
        facts={"trade_model": "Ka"},
    )
    facts = overlay_pending_question(
        TurnFacts(intent=BusinessIntent.TRADE, facts={}),
        state,
        "Tudo em dia",
    )
    assert facts.facts.get("trade_has_debts") is False


def test_ipva_and_licensing_complete_after_fines() -> None:
    state = ConversationCanonicalState(
        thread_id="t",
        customer=CustomerState(phone="1"),
        intent=BusinessIntent.TRADE,
        pending_question="trade_has_debts",
        facts={
            "trade_model": "Peugeot 2008",
            "customer_vehicle": {
                "model": "2008",
                "brand": "Peugeot",
                "debt_status": "partial",
                "debt_checks": {"fines": "clear", "ipva": "unknown", "licensing": "unknown"},
            },
        },
    )
    facts = overlay_pending_question(
        TurnFacts(intent=BusinessIntent.TRADE, facts={}),
        state,
        "IPVA e licenciamento estão em dia",
    )
    cv = facts.facts.get("customer_vehicle") or {}
    checks = cv.get("debt_checks") or facts.facts.get("debt_checks")
    assert checks.get("ipva") == "clear"
    assert checks.get("licensing") == "clear"
    assert (cv.get("debt_status") or facts.facts.get("debt_status")) == "clear"
