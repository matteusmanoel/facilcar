"""All irreversible handoff signals require deterministic inbound evidence."""

from __future__ import annotations

from sdr.domain.decision import decide
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
        customer=CustomerState(phone="1"),
        intent=BusinessIntent.PURCHASE,
    )
    for k, v in kwargs.items():
        setattr(base, k, v)
    return base


def test_llm_false_explicit_handoff_without_text_evidence() -> None:
    gated = gate_handoff_signals(
        "Quero um carro até 50 mil",
        HandoffSignals(explicit_handoff=True),
    )
    assert gated.explicit_handoff is None
    state = _state(signals=gated)
    assert should_handoff_now(state) is False


def test_llm_false_explicit_offer_without_text_evidence() -> None:
    gated = gate_handoff_signals(
        "Vocês têm disponível?",
        HandoffSignals(explicit_offer=True),
    )
    assert gated.explicit_offer is None


def test_llm_false_visit_intent_without_text_evidence() -> None:
    gated = gate_handoff_signals(
        "Quero saber o preço",
        HandoffSignals(visit_intent=True),
    )
    assert gated.visit_intent is None


def test_llm_false_high_purchase_without_text_evidence() -> None:
    gated = gate_handoff_signals(
        "uso urbano, até 15 mil",
        HandoffSignals(high_purchase_intent=True),
    )
    assert gated.high_purchase_intent is None


def test_genuine_salesperson_request() -> None:
    text = "Quero falar com um vendedor"
    gated = gate_handoff_signals(text, HandoffSignals(explicit_handoff=True))
    assert gated.explicit_handoff is True
    plan = decide(_state(signals=gated))
    assert plan.action == Action.HANDOFF_VENDOR
    assert plan.reason_code == "explicit_vendor"


def test_genuine_explicit_offer() -> None:
    text = "Dou 80 mil e fecho hoje"
    gated = gate_handoff_signals(text, HandoffSignals(explicit_offer=True))
    assert gated.explicit_offer is True
    plan = decide(_state(signals=gated))
    assert plan.reason_code == "explicit_offer"


def test_genuine_closing_intent() -> None:
    text = "Compro hoje, quero fechar agora"
    gated = gate_handoff_signals(text, HandoffSignals(high_purchase_intent=True))
    assert gated.high_purchase_intent is True
    plan = decide(_state(signals=gated))
    assert plan.reason_code == "high_purchase_intent"


def test_genuine_visit_intent() -> None:
    text = "Quero visitar a loja amanhã"
    gated = gate_handoff_signals(text, HandoffSignals(visit_intent=True))
    assert gated.visit_intent is True
    plan = decide(_state(signals=gated))
    assert plan.reason_code == "visit_intent"
