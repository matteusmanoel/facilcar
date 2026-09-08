"""Replay: visit handoff sequence — end-to-end process_turn coverage.

After REGISTER_VISIT_INTEREST, pending_question='visit' is set. The next
inbound must not loop the same slot offer:

  'Obrigado' (courtesy) → HANDOFF when qualification is already ready
  'Vou amanhã' (date, no hour) → HANDOFF

Visit is not a required field for handoff.
"""

from __future__ import annotations

import os

import pytest

from sdr.application.process_turn import process_turn
from sdr.domain.decision import decide
from sdr.domain.merge import deterministic_merge
from sdr.domain.types import (
    Action,
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    HandoffSignals,
    TurnFacts,
)
from sdr.config import get_settings


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _no_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    os.environ["OPENAI_API_KEY"] = ""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _triaged_state_with_visit_pending() -> ConversationCanonicalState:
    """Build a state that represents a fully triaged lead after visit invite.

    This is the state that should exist AFTER REGISTER_VISIT_INTEREST fires,
    i.e. pending_question='visit' has been set in process_turn.

    Key invariants for this fixture:
    - next_ask_field() must return None (all roteiro fields answered)
    - is_seller_actionable() must return True
    - pending_question='visit' is the guard that will be tested
    """
    facts = {
        "desired_model": "Corolla",
        "deal_type": "purchase",
        "payment_method": "financing",
        "down_payment": 0,
        "desired_installment": 2000,
        "name": "João Silva",
        "document_type": "CNH",
    }
    from sdr.domain.decision import inventory_search_key
    from sdr.domain.types import Actionability, LifecycleStatus

    state = ConversationCanonicalState(
        thread_id="visit-seq-replay",
        customer=CustomerState(phone="5511999999999"),
        intent=BusinessIntent.PURCHASE_FINANCING,
        language="pt-BR",
        facts=facts,
        last_inventory_search_key=inventory_search_key(facts),
        last_shown_vehicle_ids=["corolla-v1"],
    )
    state.assistant_turn_count = 5
    state.visit_invited = True
    state.pending_question = "visit"
    # Both these flags are required for next_ask_field() to return None:
    state.installment_asked = True
    state.documents_asked = True

    state.business.actionability = Actionability.ACTIONABLE
    state.lifecycle.status = LifecycleStatus.READY_FOR_HANDOFF
    return state


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_obrigado_after_visit_invite_asks_schedule() -> None:
    """'Obrigado' after visit invite is courtesy, not a schedule ask.

    Product: courtesy is not accept or refuse. Minimum qualification is
    already ready, so the thread hands off. Must not invent a visit, must
    not repeat the two slot offers, must not leak process language.
    """
    state = _triaged_state_with_visit_pending()

    async def _understand_obrigado(text: str, s: ConversationCanonicalState) -> TurnFacts:
        # "Obrigado" — no visit_intent, no new facts
        return TurnFacts(
            intent=BusinessIntent.PURCHASE_FINANCING,
            language="pt-BR",
            facts={},
        )

    result = await process_turn(
        state=state,
        inbound_text="Obrigado",
        understand=_understand_obrigado,
        pool=None,
    )

    assert result.action_plan.action == Action.HANDOFF_VENDOR, (
        f"Expected HANDOFF_VENDOR for courtesy after a ready visit invite, "
        f"got {result.action_plan.action!r}."
    )
    assert result.action_plan.handoff is True
    assert result.state.visit_accepted_offered is False
    assert result.state.visit_date is None
    assert len(result.outbound_texts) > 0, (
        "Must produce at least one outbound bubble."
    )
    joined = " ".join(result.outbound_texts).lower()
    assert "que tal" not in joined
    assert "confirmação do vendedor" not in joined
    assert "handoff" not in joined
    assert "triagem" not in joined
    assert "modelo" not in joined and "ano específico" not in joined, (
        f"Must not re-ask model/year after the vehicle was already shown. Got: {result.outbound_texts}"
    )


@pytest.mark.asyncio
async def test_vou_amanha_after_visit_invite_handoffs() -> None:
    """'Vou amanhã' (visit_intent=True) after invite must trigger HANDOFF through process_turn."""
    state = _triaged_state_with_visit_pending()

    async def _understand_visit_confirm(text: str, s: ConversationCanonicalState) -> TurnFacts:
        return TurnFacts(
            intent=BusinessIntent.PURCHASE_FINANCING,
            language="pt-BR",
            facts={},
            signals=HandoffSignals(visit_intent=True),
        )

    result = await process_turn(
        state=state,
        inbound_text="Vou amanhã sim",
        understand=_understand_visit_confirm,
        pool=None,
    )

    assert result.action_plan.action == Action.HANDOFF_VENDOR, (
        f"Expected HANDOFF_VENDOR for 'Vou amanhã' (visit_intent=True) after invite, "
        f"got {result.action_plan.action!r}."
    )
    assert result.action_plan.handoff is True


@pytest.mark.asyncio
async def test_second_turn_after_visit_invite_handoffs_unconditionally() -> None:
    """Turn N+2 (pending_question cleared) must always produce HANDOFF regardless of message.

    After COMMERCIAL_UNKNOWN on turn N+1, pending_question resets to None.
    On turn N+2, the system must handoff with any message (is_seller_actionable is True).
    """
    # State as of turn N+2: pending_question is None (was cleared on N+1 COMMERCIAL_UNKNOWN)
    state = _triaged_state_with_visit_pending()
    state.pending_question = None  # simulate it was cleared

    async def _understand_any(text: str, s: ConversationCanonicalState) -> TurnFacts:
        return TurnFacts(
            intent=BusinessIntent.PURCHASE_FINANCING,
            language="pt-BR",
            facts={},
        )

    result = await process_turn(
        state=state,
        inbound_text="Ok, então até lá",
        understand=_understand_any,
        pool=None,
    )

    assert result.action_plan.action == Action.HANDOFF_VENDOR, (
        f"Expected HANDOFF_VENDOR on turn N+2 (pending_question=None, actionable), "
        f"got {result.action_plan.action!r}."
    )
    assert result.action_plan.handoff is True


@pytest.mark.asyncio
async def test_register_visit_interest_sets_pending_question() -> None:
    """process_turn sets pending_question='visit' after REGISTER_VISIT_INTEREST action.

    This tests the other side of the guard: the state must carry pending_question='visit'
    into the next turn so that decide() can apply the guard.

    We trigger REGISTER_VISIT_INTEREST by sending a DOCUMENT inbound when the roteiro
    is complete (all fields answered, documents not yet asked for a visit).
    """
    from sdr.domain.decision import inventory_search_key
    from sdr.domain.inbound import ContentType, InboundTurn, MediaStatus
    from sdr.domain.types import Actionability, LifecycleStatus

    facts = {
        "desired_model": "Corolla",
        "deal_type": "purchase",
        "payment_method": "financing",
        "down_payment": 0,
        "desired_installment": 2000,
        "name": "João Silva",
        "document_type": "CNH",
    }

    state = ConversationCanonicalState(
        thread_id="visit-pending-set-test",
        customer=CustomerState(phone="5511999999999"),
        intent=BusinessIntent.PURCHASE_FINANCING,
        language="pt-BR",
        facts=facts,
        last_inventory_search_key=inventory_search_key(facts),
        last_shown_vehicle_ids=["corolla-v1"],
    )
    state.assistant_turn_count = 4
    state.installment_asked = True
    state.documents_asked = True
    # visit_invited must be False for REGISTER_VISIT_INTEREST to fire
    state.visit_invited = False
    state.business.actionability = Actionability.ACTIONABLE
    state.lifecycle.status = LifecycleStatus.READY_FOR_HANDOFF

    # Verify the pre-condition directly: with document_received=True, decide() fires REGISTER_VISIT_INTEREST
    import copy
    state_with_doc = copy.deepcopy(state)
    state_with_doc.document_received = True
    plan = decide(state_with_doc)
    assert plan.action == Action.REGISTER_VISIT_INTEREST, (
        f"Pre-condition failed: expected REGISTER_VISIT_INTEREST, got {plan.action!r}. "
        "State fixture is incomplete — installment_asked/documents_asked may need adjustment."
    )

    async def _understand_doc(text: str, s: ConversationCanonicalState) -> TurnFacts:
        return TurnFacts(
            intent=BusinessIntent.PURCHASE_FINANCING,
            language="pt-BR",
            facts={"name": "João Silva", "document_type": "CNH"},
        )

    # Use DOCUMENT inbound so process_turn sets document_received=True internally
    doc_inbound = InboundTurn(
        thread_id="visit-pending-set-test",
        content_type=ContentType.DOCUMENT,
        text="CNH: João Silva",
        media_status=MediaStatus.OK,
    )

    result = await process_turn(
        state=state,
        inbound=doc_inbound,
        understand=_understand_doc,
        pool=None,
    )

    assert result.state.pending_question == "visit", (
        f"After REGISTER_VISIT_INTEREST, pending_question must be 'visit'. "
        f"Got: {result.state.pending_question!r}. "
        "process_turn must set this for the guard to work next turn."
    )
    assert result.state.visit_invited is True
