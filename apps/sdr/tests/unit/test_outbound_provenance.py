"""Outbound provenance: bot echoes must not be treated as human fromMe.

D1–D8 cover correlation (isBotSent / providerMessageId), missing provenance,
instance scoping, replay admin events, and HUMAN_ACTIVE auto-reply skip.
Evolution is faked — no live WhatsApp.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from sdr.application.process_turn import process_turn
from sdr.domain.ownership import assume_human
from sdr.domain.types import (
    Action,
    ConversationCanonicalState,
    CustomerState,
    LifecycleState,
    LifecycleStatus,
)
from sdr.infrastructure.conversation_repository import ConversationRepository
from sdr.replay.runner import _admin_event, _apply_admin_event, _has_customer_inbound


def _pool_with_conn(conn: AsyncMock) -> MagicMock:
    pool = MagicMock()
    pool.acquire = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(),
        )
    )
    return pool


def _state() -> ConversationCanonicalState:
    return ConversationCanonicalState(
        thread_id="t-prov",
        customer=CustomerState(phone="5545988432998", name="Ana"),
        lifecycle=LifecycleState(status=LifecycleStatus.HANDOFF_SENT),
        ownership_revision=0,
    )


@pytest.mark.asyncio
async def test_d1_insert_bot_outbound_is_bot_not_human() -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"id": "msg-bot"})
    repo = ConversationRepository(_pool_with_conn(conn))

    msg_id = await repo.insert_bot_outbound(
        conversation_id="conv-a",
        instance_name="facilcar-sdr",
        text="Olá! Sou a Júlia da FacilCar.",
        provider_message_id="wa-julia-1",
    )

    assert msg_id == "msg-bot"
    sql = " ".join(conn.fetchrow.await_args.args[0].split())
    assert '"isBotSent"' in sql
    assert "$5, true, false, true, 'DONE'" in sql
    assert 'ON CONFLICT ("instanceName", "providerMessageId") DO NOTHING' in sql
    args = conn.fetchrow.await_args.args
    assert args[2] == "conv-a"
    assert args[3] == "wa-julia-1"
    assert args[4] == "facilcar-sdr"


@pytest.mark.asyncio
async def test_d3_duplicate_provider_id_conflict_is_noop() -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    repo = ConversationRepository(_pool_with_conn(conn))

    msg_id = await repo.insert_bot_outbound(
        conversation_id="conv-a",
        instance_name="facilcar-sdr",
        text="echo",
        provider_message_id="wa-julia-1",
    )

    sql = conn.fetchrow.await_args.args[0]
    assert "ON CONFLICT" in sql and "DO NOTHING" in sql
    assert msg_id  # reserved uuid when conflict returns no row


@pytest.mark.asyncio
async def test_d4_known_bot_provider_id_is_instance_scoped() -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"?column?": 1})
    repo = ConversationRepository(_pool_with_conn(conn))

    found = await repo.has_bot_outbound_provider_id(
        instance_name="facilcar-sdr",
        provider_message_id="wa-julia-1",
    )
    assert found is True
    sql, instance, pid = conn.fetchrow.await_args.args
    assert '"instanceName" = $1' in sql
    assert '"providerMessageId" = $2' in sql
    assert '"isBotSent" = true' in sql
    assert instance == "facilcar-sdr"
    assert pid == "wa-julia-1"


@pytest.mark.asyncio
async def test_d5_blank_provider_id_is_insufficient_and_gets_reserved_id() -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    repo = ConversationRepository(_pool_with_conn(conn))

    assert (
        await repo.has_bot_outbound_provider_id(
            instance_name="facilcar-sdr",
            provider_message_id="",
        )
        is False
    )
    assert (
        await repo.has_bot_outbound_provider_id(
            instance_name="facilcar-sdr",
            provider_message_id="   ",
        )
        is False
    )
    conn.fetchrow.assert_not_awaited()

    conn.fetchrow = AsyncMock(return_value={"id": "msg-reserved"})
    await repo.insert_bot_outbound(
        conversation_id="conv-a",
        instance_name="facilcar-sdr",
        text="ok",
        provider_message_id="  ",
    )
    reserved = conn.fetchrow.await_args.args[3]
    assert reserved.startswith("bot-")


@pytest.mark.asyncio
async def test_d6_other_instance_does_not_satisfy_bot_correlation() -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    repo = ConversationRepository(_pool_with_conn(conn))

    found = await repo.has_bot_outbound_provider_id(
        instance_name="other-instance",
        provider_message_id="wa-julia-1",
    )
    assert found is False
    assert conn.fetchrow.await_args.args[1] == "other-instance"
    assert conn.fetchrow.await_args.args[2] == "wa-julia-1"


def test_d7_replay_admin_event_is_not_outbound_fromme() -> None:
    turn = {"admin_event": {"type": "assume", "actor_user_id": "user-1"}}
    admin = _admin_event(turn)
    assert admin is not None
    assert _has_customer_inbound(turn) is False

    state, name = _apply_admin_event(_state(), admin)
    assert name == "assume"
    assert state.lifecycle.status == LifecycleStatus.HUMAN_ACTIVE
    assert state.assumed_by_user_id == "user-1"


@pytest.mark.asyncio
async def test_d8_human_active_process_turn_does_not_auto_reply() -> None:
    state = assume_human(_state(), actor_user_id="user-alice", expected_revision=0)

    async def understand(text, current):
        raise AssertionError("understand must not run while HUMAN_ACTIVE")

    result = await process_turn(
        state=state,
        inbound_text="quero o civic",
        understand=understand,
    )
    assert result.outbound_texts == []
    assert result.action_plan.action == Action.NO_REPLY
    assert result.state.lifecycle.status == LifecycleStatus.HUMAN_ACTIVE
