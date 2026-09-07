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
    assert facts.facts.get("trade_debt_type") == "sem_multas"


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
