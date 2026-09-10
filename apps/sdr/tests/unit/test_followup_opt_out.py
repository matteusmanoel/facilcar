"""Durable opt-out: not Lead.status, not wiped by /deletar, blocks compose/send."""

from __future__ import annotations

import pytest

from sdr.application.followup_runtime import FollowUpRuntime
from sdr.domain.clock import GOLDEN_CLOCK_ISO, set_clock
from sdr.domain.followup import PauseReason, enrich_turn_facts_from_inbound, followup_record
from sdr.domain.followup_cancel import is_opt_out_text
from sdr.domain.types import (
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    LifecycleState,
    LifecycleStatus,
    TurnFacts,
)
from sdr.infrastructure.followup_repository import STATUS_PENDING


def setup_function() -> None:
    set_clock(GOLDEN_CLOCK_ISO)


def teardown_function() -> None:
    set_clock(None)


def _state() -> ConversationCanonicalState:
    return ConversationCanonicalState(
        thread_id="t-opt",
        customer=CustomerState(phone="5511999000099"),
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts={"desired_model": "Strada"},
        context_revision=1,
    )


@pytest.mark.asyncio
async def test_opt_out_phrase_is_protocol_deterministic() -> None:
    assert is_opt_out_text("Não quero mais receber mensagens.")
    assert is_opt_out_text("nao quero mais receber")


@pytest.mark.asyncio
async def test_opt_out_before_claim_cancels_and_blocks_tick() -> None:
    runtime = FollowUpRuntime(conversation_id="t-opt")
    state = _state()
    runtime.apply_policy(state, "Pode me chamar amanhã às 14h.")
    await runtime.sync_task(state, "Pode me chamar amanhã às 14h.")
    assert runtime.has_pending()
    runtime.apply_policy(state, "Não quero mais receber mensagens.")
    await runtime.cancel("OPT_OUT")
    runtime.persist_opt_out(state)
    assert not runtime.has_pending()
    assert runtime.is_opted_out()
    await runtime.tick()
    assert runtime.sends == []
    assert runtime.composer_calls == 0


@pytest.mark.asyncio
async def test_opt_out_repeated_is_idempotent() -> None:
    runtime = FollowUpRuntime(conversation_id="t-opt")
    state = _state()
    runtime.apply_policy(state, "Não quero mais receber mensagens.")
    first = runtime.opted_out_at
    runtime.apply_policy(state, "Não quero mais receber mensagens.")
    assert runtime.opted_out_at == first
    await runtime.sync_task(state, "oi")
    assert not runtime.has_pending()


@pytest.mark.asyncio
async def test_opt_out_survives_reset_and_blocks_new_task() -> None:
    runtime = FollowUpRuntime(conversation_id="t-opt")
    state = _state()
    runtime.apply_policy(state, "Pode me chamar amanhã às 14h.")
    await runtime.sync_task(state, "Pode me chamar amanhã às 14h.")
    runtime.apply_policy(state, "Não quero mais receber mensagens.")
    await runtime.cancel("OPT_OUT")
    runtime.persist_opt_out(state)
    await runtime.on_reset()
    fresh = ConversationCanonicalState(
        thread_id="t-opt",
        customer=CustomerState(phone="5511999000099"),
    )
    runtime.stamp_opt_out_on_state(fresh)
    assert runtime.is_opted_out()
    assert followup_record(fresh).opted_out is True
    runtime.apply_policy(fresh, "Pode me chamar amanhã às 14h.")
    await runtime.sync_task(fresh, "Pode me chamar amanhã às 14h.")
    pending = [t for t in runtime.repo.all_rows() if t.status == STATUS_PENDING]
    assert pending == []


@pytest.mark.asyncio
async def test_opt_out_during_compose_skips_llm_and_send() -> None:
    runtime = FollowUpRuntime(conversation_id="t-opt")
    state = _state()
    runtime.apply_policy(state, "Pode me chamar amanhã às 14h.")
    await runtime.sync_task(state, "Pode me chamar amanhã às 14h.")
    runtime.persist_opt_out(state)
    snap = runtime.snapshot()
    task = runtime.repo.all_rows()[0]
    task.status = "PROCESSING"
    text = await runtime.compose_task(task, snap)
    assert text == ""
    assert runtime.composer_calls == 0


@pytest.mark.asyncio
async def test_opt_out_immediately_before_send_via_snapshot() -> None:
    runtime = FollowUpRuntime(conversation_id="t-opt")
    state = _state()
    runtime.apply_policy(state, "Pode me chamar amanhã às 14h.")
    await runtime.sync_task(state, "Pode me chamar amanhã às 14h.")
    runtime.persist_opt_out()
    await runtime.tick()
    assert runtime.sends == []


@pytest.mark.asyncio
async def test_opt_out_after_handoff_still_blocks() -> None:
    runtime = FollowUpRuntime(conversation_id="t-opt")
    state = _state()
    state.lifecycle = LifecycleState(status=LifecycleStatus.HANDOFF_SENT)
    runtime.apply_policy(state, "Pode me chamar amanhã às 14h.")
    await runtime.sync_task(state, "Pode me chamar amanhã às 14h.")
    runtime.apply_policy(state, "Não quero mais receber mensagens.")
    await runtime.cancel("OPT_OUT")
    runtime.persist_opt_out(state)
    await runtime.tick()
    assert runtime.sends == []
    assert followup_record(state).pause_reason == PauseReason.OPT_OUT


@pytest.mark.asyncio
async def test_human_active_does_not_call_composer() -> None:
    runtime = FollowUpRuntime(conversation_id="t-opt")
    state = _state()
    runtime.apply_policy(state, "Pode me chamar amanhã às 14h.")
    await runtime.sync_task(state, "Pode me chamar amanhã às 14h.")
    runtime.bot_status = LifecycleStatus.HUMAN_ACTIVE.value
    task = runtime.repo.all_rows()[0]
    task.status = "PROCESSING"
    text = await runtime.compose_task(task, runtime.snapshot())
    assert text == ""
    assert runtime.composer_calls == 0


def test_lead_status_is_not_opt_out() -> None:
    state = _state()
    state.facts["lead_status"] = "QUALIFIED"
    facts = TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING, facts={"lead_status": "QUALIFIED"})
    from sdr.domain.followup import followup_decision

    enrich_turn_facts_from_inbound(facts, "Pode me chamar amanhã às 14h.")
    decision = followup_decision(state, facts, inbound_text="Pode me chamar amanhã às 14h.")
    assert decision.cancel_intent is None
    assert decision.eligible is True
