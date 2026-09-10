"""Pause vs handoff actionability, and document deferral without callback."""

from __future__ import annotations

import pytest

from sdr.application.followup_runtime import FollowUpRuntime
from sdr.application.process_turn import process_turn
from sdr.domain.clock import set_clock
from sdr.domain.conversation_revision import bump_context_revision
from sdr.domain.followup import inbound_is_followup_pause, suggest_pause_from_inbound
from sdr.domain.ownership import vendor_already_notified
from sdr.domain.types import (
    Action,
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    HandoffSignals,
    LifecycleStatus,
    TurnFacts,
)
from sdr.domain.visit import parse_visit_utterance

MONDAY = "2026-09-07T10:00:00-03:00"


@pytest.fixture(autouse=True)
def _clock():
    set_clock(MONDAY)
    yield
    set_clock(None)


def _understand(**kwargs) -> object:
    async def _fn(_text: str, _state: ConversationCanonicalState) -> TurnFacts:
        return TurnFacts(
            intent=kwargs.get("intent", BusinessIntent.PURCHASE_FINANCING),
            facts=kwargs.get("facts") or {"desired_model": "Strada"},
            signals=kwargs.get("signals") or HandoffSignals(),
        )

    return _fn


def _qualifying(*, named: bool, **kwargs) -> ConversationCanonicalState:
    facts = {"desired_model": "Strada", "payment_method": "financing"}
    if named:
        facts["name"] = "Bruno"
    state = ConversationCanonicalState(
        thread_id="t-pause-h",
        customer=CustomerState(phone="5511999000200", name="Bruno" if named else None),
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts=facts,
        assistant_turn_count=3,
        pending_question="documents",
        documents_asked=True,
        context_revision=1,
    )
    for key, value in kwargs.items():
        setattr(state, key, value)
    return state


@pytest.mark.asyncio
async def test_pause_when_not_actionable_acks_without_handoff() -> None:
    state = _qualifying(named=False, handoff_ready=False)
    result = await process_turn(
        state=state,
        inbound_text="Não estou com os comprovantes agora. Pode me chamar amanhã às 14h.",
        understand=_understand(),
        pool=None,
    )
    assert result.action_plan.action != Action.HANDOFF_VENDOR
    assert result.action_plan.handoff is False
    assert result.action_plan.reason_code == "followup_pause_ack"
    assert vendor_already_notified(result.state) is False
    assert result.outbound_texts
    assert "encaminh" not in " ".join(result.outbound_texts).lower()
    runtime = FollowUpRuntime(conversation_id="t-pause-h")
    bump_context_revision(result.state)
    runtime.apply_policy(result.state, "Não estou com os comprovantes agora. Pode me chamar amanhã às 14h.")
    await runtime.sync_task(
        result.state,
        "Não estou com os comprovantes agora. Pode me chamar amanhã às 14h.",
    )
    assert runtime.repo.all_rows()


@pytest.mark.asyncio
async def test_pause_when_actionable_acks_and_notifies_vendor_once() -> None:
    state = _qualifying(named=True, handoff_ready=True, visit_invited=True)
    inbound = "Vou ver com meu marido e te retorno."
    result = await process_turn(
        state=state,
        inbound_text=inbound,
        understand=_understand(facts={"desired_model": "Strada", "name": "Bruno"}),
        pool=None,
    )
    assert result.action_plan.action != Action.HANDOFF_VENDOR
    assert result.action_plan.reason_code == "followup_pause_ack"
    assert result.action_plan.handoff is True
    assert vendor_already_notified(result.state) is True
    assert result.state.lifecycle.status == LifecycleStatus.HANDOFF_SENT
    blob = " ".join(result.outbound_texts).lower()
    assert "encaminh" not in blob
    assert "handoff" not in blob
    assert result.state.profile_complete is False

    again = await process_turn(
        state=result.state,
        inbound_text=inbound,
        understand=_understand(facts={"desired_model": "Strada", "name": "Bruno"}),
        pool=None,
    )
    assert vendor_already_notified(again.state) is True
    assert again.state.vendor_notified_at == result.state.vendor_notified_at
    assert again.action_plan.handoff is False


def test_document_deferral_without_callback_is_not_pause_or_visit() -> None:
    inbound = "Não tenho os documentos agora."
    reason, _consent, _commitment = suggest_pause_from_inbound(inbound)
    assert reason is None
    assert inbound_is_followup_pause(inbound) is False
    parsed = parse_visit_utterance(inbound, [])
    assert parsed.date is None
    assert parsed.time is None
    assert parsed.interest is False


def test_document_deferral_with_callback_is_pause_not_visit() -> None:
    inbound = "Não tenho os documentos agora. Pode me chamar amanhã."
    reason, _consent, _commitment = suggest_pause_from_inbound(inbound)
    assert reason is not None
    assert inbound_is_followup_pause(inbound) is True


@pytest.mark.asyncio
async def test_document_deferral_without_callback_does_not_schedule() -> None:
    runtime = FollowUpRuntime(conversation_id="t-doc")
    state = _qualifying(named=False, handoff_ready=False)
    bump_context_revision(state)
    inbound = "Não tenho os documentos agora."
    result = await process_turn(
        state=state,
        inbound_text=inbound,
        understand=_understand(),
        pool=None,
    )
    runtime.apply_policy(result.state, inbound, result.turn_facts)
    await runtime.sync_task(result.state, inbound)
    assert runtime.repo.all_rows() == []
    assert result.state.facts.get("documents_deferred") is True
    assert result.state.wait_state != "PAUSED_WITH_FOLLOWUP"
    assert result.action_plan.action != Action.NO_REPLY


@pytest.mark.asyncio
async def test_document_deferral_without_callback_handoffs_when_actionable() -> None:
    state = _qualifying(named=True, handoff_ready=True, visit_invited=True)
    result = await process_turn(
        state=state,
        inbound_text="Não tenho os documentos agora.",
        understand=_understand(facts={"desired_model": "Strada", "name": "Bruno"}),
        pool=None,
    )
    assert result.state.facts.get("documents_deferred") is True
    assert result.state.wait_state != "PAUSED_WITH_FOLLOWUP"
    assert result.action_plan.action != Action.NO_REPLY
    assert result.action_plan.reason_code != "followup_pause_ack"
    runtime = FollowUpRuntime(conversation_id="t-doc-h")
    bump_context_revision(result.state)
    runtime.apply_policy(result.state, "Não tenho os documentos agora.", result.turn_facts)
    await runtime.sync_task(result.state, "Não tenho os documentos agora.")
    assert runtime.repo.all_rows() == []
    assert result.state.lifecycle.status != LifecycleStatus.HUMAN_CLOSED


@pytest.mark.asyncio
async def test_document_deferral_with_callback_schedules_one_attempt() -> None:
    runtime = FollowUpRuntime(conversation_id="t-doc-cb")
    state = _qualifying(named=False, handoff_ready=False)
    bump_context_revision(state)
    inbound = "Não tenho os documentos agora. Pode me chamar amanhã."
    result = await process_turn(
        state=state,
        inbound_text=inbound,
        understand=_understand(),
        pool=None,
    )
    runtime.apply_policy(result.state, inbound, result.turn_facts)
    await runtime.sync_task(result.state, inbound)
    rows = [t for t in runtime.repo.all_rows() if t.status == "PENDING"]
    assert len(rows) == 1
    assert rows[0].maximum_attempts == 1
    blob = " ".join(result.outbound_texts).lower()
    assert "documento será" not in blob
    assert result.action_plan.action != Action.REGISTER_VISIT_INTEREST
    assert result.action_plan.reason_code == "followup_pause_ack"
    assert result.state.wait_state == "PAUSED_WITH_FOLLOWUP"
    await runtime.sync_task(result.state, inbound)
    pending = [t for t in runtime.repo.all_rows() if t.status == "PENDING"]
    assert len(pending) == 1
