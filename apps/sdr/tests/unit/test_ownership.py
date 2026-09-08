"""Conversation ownership: handoff is an event; AI stays active until a human assumes."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from sdr.application.process_turn import process_turn
from sdr.domain.clock import set_clock
from sdr.domain.decision import decide
from sdr.domain.handoff import is_ai_silenced, mark_handoff_sent
from sdr.domain.inbound import ContentType, InboundTurn, MediaStatus
from sdr.domain.inbound_batch import InboundSegment
from sdr.domain.ownership import (
    OwnershipConflict,
    StaleOwnershipRevision,
    assume_human,
    automation_enabled,
    handoff_sent,
    human_active,
    resume_ai,
)
from sdr.domain.types import (
    Action,
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    LifecycleState,
    LifecycleStatus,
    TurnFacts,
)
from sdr.infrastructure.conversation_repository import (
    ConversationRepository,
    canonical_state_from_json,
    canonical_state_to_json,
)


def _state(**kwargs) -> ConversationCanonicalState:
    base = ConversationCanonicalState(
        thread_id="t-own",
        customer=CustomerState(phone="5511999999999", name="Ana"),
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts={"desired_model": "Civic", "payment_method": "financing"},
    )
    for key, value in kwargs.items():
        setattr(base, key, value)
    return base


def _handed_off() -> ConversationCanonicalState:
    state = _state(lifecycle=LifecycleState(status=LifecycleStatus.READY_FOR_HANDOFF))
    mark_handoff_sent(state, "triage_actionable")
    return state


async def _understand_purchase(text, state):
    return TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING, facts={"desired_installment": 1500})


def test_a1_handoff_sent_does_not_silence_ai() -> None:
    state = _handed_off()
    assert state.lifecycle.status == LifecycleStatus.HANDOFF_SENT
    assert is_ai_silenced(state) is False
    assert automation_enabled(state) is True
    assert human_active(state) is False
    assert handoff_sent(state) is True
    plan = decide(state)
    assert plan.action != Action.NO_REPLY
    assert plan.action != Action.HANDOFF_VENDOR


def test_a2_assume_human_silences_ai() -> None:
    state = assume_human(_handed_off(), actor_user_id="user-alice", expected_revision=0)
    assert state.lifecycle.status == LifecycleStatus.HUMAN_ACTIVE
    assert state.ownership_revision == 1
    assert state.assumed_by_user_id == "user-alice"
    assert is_ai_silenced(state) is True
    assert automation_enabled(state) is False
    assert human_active(state) is True
    plan = decide(state)
    assert plan.action == Action.NO_REPLY


def test_a3_assume_same_actor_is_idempotent() -> None:
    set_clock("2026-09-08T15:00:00-03:00")
    try:
        first = assume_human(_handed_off(), actor_user_id="user-alice", expected_revision=0)
        assumed_at = first.assumed_at
        revision = first.ownership_revision
        second = assume_human(first, actor_user_id="user-alice", expected_revision=revision)
        assert second.lifecycle.status == LifecycleStatus.HUMAN_ACTIVE
        assert second.ownership_revision == revision
        assert second.assumed_at == assumed_at
        assert second.assumed_by_user_id == "user-alice"
    finally:
        set_clock(None)


def test_a4_second_distinct_human_conflicts() -> None:
    first = assume_human(_handed_off(), actor_user_id="user-alice", expected_revision=0)
    with pytest.raises(OwnershipConflict):
        assume_human(first, actor_user_id="user-bob", expected_revision=first.ownership_revision)


def test_a5_stale_revision_rejected() -> None:
    state = _handed_off()
    with pytest.raises(StaleOwnershipRevision):
        assume_human(state, actor_user_id="user-alice", expected_revision=3)


def test_a6_resume_ai_restores_automation() -> None:
    assumed = assume_human(_handed_off(), actor_user_id="user-alice", expected_revision=0)
    assumed.active_lead_ids = ["lead-qualified"]
    prior_revision = assumed.ownership_revision
    resumed = resume_ai(
        assumed,
        actor_user_id="user-alice",
        reason="customer asked to continue with julia",
        expected_revision=prior_revision,
    )
    assert resumed.lifecycle.status == LifecycleStatus.AI_RESUMED
    assert resumed.ownership_revision == prior_revision + 1
    assert resumed.resume_reason == "customer asked to continue with julia"
    assert resumed.resumed_by_user_id == "user-alice"
    assert resumed.assumed_by_user_id == "user-alice"
    assert resumed.active_lead_ids == ["lead-qualified"]
    assert is_ai_silenced(resumed) is False
    assert automation_enabled(resumed) is True
    assert human_active(resumed) is False
    assert handoff_sent(resumed) is True


def test_a7_resume_does_not_resend_handoff() -> None:
    assumed = assume_human(_handed_off(), actor_user_id="user-alice", expected_revision=0)
    resumed = resume_ai(
        assumed,
        actor_user_id="user-alice",
        reason="authorized resume",
        expected_revision=assumed.ownership_revision,
    )
    assert resumed.lifecycle.status != LifecycleStatus.HANDOFF_SENT
    plan = decide(resumed)
    assert plan.action != Action.HANDOFF_VENDOR
    assert plan.handoff is False


@pytest.mark.asyncio
async def test_a8_assume_resume_repo_does_not_touch_lead_status() -> None:
    conv_id = "conv-own"
    lead_id = "lead-qualified"
    now = datetime(2026, 9, 8, 18, 0, 0)
    handed = _handed_off()
    handed.active_lead_ids = [lead_id]
    handed.thread_id = conv_id
    current = {
        "id": conv_id,
        "phone": "5511999999999",
        "botStatus": LifecycleStatus.HANDOFF_SENT.value,
        "activeLeadIds": [lead_id],
        "canonicalStateJson": canonical_state_to_json(handed),
        "ownershipRevision": 0,
        "assumedByUserId": None,
        "assumedAt": None,
        "resumedByUserId": None,
        "resumedAt": None,
        "resumeReason": None,
        "handoffAt": now,
    }

    sqls: list[str] = []
    conn = AsyncMock()

    async def fetchrow(sql, *args):
        sqls.append(sql)
        if "UPDATE" in sql and '"Conversation"' in sql:
            if "HUMAN_ACTIVE" in sql:
                current["botStatus"] = LifecycleStatus.HUMAN_ACTIVE.value
                current["ownershipRevision"] = int(current["ownershipRevision"]) + 1
                current["assumedByUserId"] = "user-alice"
                current["assumedAt"] = now
                current["canonicalStateJson"] = args[1] if len(args) > 1 else current["canonicalStateJson"]
            elif "AI_RESUMED" in sql:
                current["botStatus"] = LifecycleStatus.AI_RESUMED.value
                current["ownershipRevision"] = int(current["ownershipRevision"]) + 1
                current["resumedByUserId"] = "user-alice"
                current["resumedAt"] = now
                current["resumeReason"] = "authorized resume"
                current["canonicalStateJson"] = args[1] if len(args) > 1 else current["canonicalStateJson"]
        return dict(current)

    async def execute(sql, *args):
        sqls.append(sql)
        return "UPDATE 1"

    conn.fetchrow = AsyncMock(side_effect=fetchrow)
    conn.execute = AsyncMock(side_effect=execute)
    conn.fetch = AsyncMock(return_value=[])
    pool = MagicMock()
    pool.acquire = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=conn), __aexit__=AsyncMock())
    )
    repo = ConversationRepository(pool)

    assumed = await repo.assume_human(
        conv_id, actor_user_id="user-alice", expected_revision=0
    )
    assert assumed.lifecycle.status == LifecycleStatus.HUMAN_ACTIVE

    resumed = await repo.resume_ai(
        conv_id,
        actor_user_id="user-alice",
        reason="authorized resume",
        expected_revision=assumed.ownership_revision,
    )
    assert resumed.lifecycle.status == LifecycleStatus.AI_RESUMED

    joined = "\n".join(sqls)
    assert '"Lead"' not in joined
    assert "facilcar\".\"Lead\"" not in joined
    assert "'NEW'" not in joined
    assert '"status" = \'NEW\'' not in joined


def test_a9_canonical_state_roundtrip_ownership_fields() -> None:
    state = _handed_off()
    assumed = assume_human(state, actor_user_id="user-alice", expected_revision=0)
    resumed = resume_ai(
        assumed,
        actor_user_id="user-alice",
        reason="continue",
        expected_revision=assumed.ownership_revision,
    )
    raw = canonical_state_to_json(resumed)
    loaded = canonical_state_from_json(
        raw,
        thread_id="other-thread",
        phone="000",
        bot_status=LifecycleStatus.AI_RESUMED.value,
        active_lead_ids=["lead-1"],
        ownership_revision=9,
        assumed_by_user_id="column-alice",
        assumed_at=datetime(2026, 9, 8, 12, 0, 0),
        resumed_by_user_id="column-alice",
        resumed_at=datetime(2026, 9, 8, 13, 0, 0),
        resume_reason="column-reason",
        handoff_at=datetime(2026, 9, 8, 11, 0, 0),
    )
    assert loaded.lifecycle.status == LifecycleStatus.AI_RESUMED
    assert loaded.ownership_revision == 9
    assert loaded.assumed_by_user_id == "column-alice"
    assert loaded.resumed_by_user_id == "column-alice"
    assert loaded.resume_reason == "column-reason"
    assert loaded.handoff_at is not None
    assert loaded.active_lead_ids == ["lead-1"]
    assert loaded.thread_id == resumed.thread_id or loaded.thread_id in {resumed.thread_id, "other-thread"}


@pytest.mark.asyncio
async def test_a9_save_canonical_state_writes_ownership_columns() -> None:
    conn = AsyncMock()
    captured: dict = {}

    async def execute(sql, *args):
        captured["sql"] = sql
        captured["args"] = args
        return "UPDATE 1"

    conn.execute = AsyncMock(side_effect=execute)
    pool = MagicMock()
    pool.acquire = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=conn), __aexit__=AsyncMock())
    )
    repo = ConversationRepository(pool)
    state = assume_human(_handed_off(), actor_user_id="user-alice", expected_revision=0)
    await repo.save_canonical_state("conv-own", state)
    sql = captured["sql"]
    args = captured["args"]
    assert '"ownershipRevision"' in sql
    assert '"assumedByUserId"' in sql
    assert '"Lead"' not in sql
    assert state.ownership_revision in args
    assert "user-alice" in args


@pytest.mark.asyncio
async def test_a10_post_handoff_document_keeps_active_lead_ids() -> None:
    state = _handed_off()
    state.active_lead_ids = ["lead-keep"]
    inbound = InboundTurn(
        thread_id=state.thread_id,
        content_type=ContentType.DOCUMENT,
        text="tipo: CNH",
        media_status=MediaStatus.OK,
        mime_type="application/pdf",
        raw_message_ref={"document_extracted": {"document_type": "CNH", "name": "Ana"}},
        segments=[
            InboundSegment(
                message_id="cnh-1",
                content_type=ContentType.DOCUMENT,
                text="tipo: CNH",
                media_status=MediaStatus.OK,
                document_extracted={"document_type": "CNH", "name": "Ana"},
            )
        ],
    )
    result = await process_turn(state=state, inbound=inbound, understand=_understand_purchase)
    assert result.state.active_lead_ids == ["lead-keep"]
    assert result.action_plan.action != Action.HANDOFF_VENDOR


@pytest.mark.asyncio
async def test_human_active_process_turn_skips_understanding() -> None:
    state = assume_human(_handed_off(), actor_user_id="user-alice", expected_revision=0)

    async def understand(text, current):
        raise AssertionError("understand must not run while HUMAN_ACTIVE")

    result = await process_turn(
        state=state,
        inbound_text="quero financiar",
        understand=understand,
    )
    assert result.outbound_texts == []
    assert result.action_plan.action == Action.NO_REPLY
    assert result.state.lifecycle.status == LifecycleStatus.HUMAN_ACTIVE
    assert result.state.active_lead_ids == state.active_lead_ids
