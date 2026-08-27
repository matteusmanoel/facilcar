"""Tests for PROTOCOL_DETERMINISTIC ``/deletar`` memory reset."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from sdr.domain.commands import (
    RESET_MEMORY_CONFIRMATION_PT,
    is_reset_memory_command,
)
from sdr.domain.inbound import ContentType
from sdr.domain.inbound_batch import BatchStatus, InboundBatch, InboundSegment
from sdr.domain.types import (
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    LifecycleStatus,
)
from sdr.orchestrator import Orchestrator


def test_reset_command_exact_only() -> None:
    assert is_reset_memory_command("/deletar")
    assert is_reset_memory_command(" /deletar ")
    assert is_reset_memory_command("/DELETAR")
    assert not is_reset_memory_command("deletar")
    assert not is_reset_memory_command("quero /deletar agora")
    assert not is_reset_memory_command("Oi\n/deletar")
    assert not is_reset_memory_command("")
    assert not is_reset_memory_command(None)


@pytest.mark.asyncio
async def test_handle_reset_memory_clears_state_and_confirms() -> None:
    pool = MagicMock()
    orch = Orchestrator(pool, redis_client=None, evolution=MagicMock())
    orch.evolution.send_text = AsyncMock(return_value="wa-reset-1")
    orch.conversations = MagicMock()
    fresh = ConversationCanonicalState(
        thread_id="conv-1",
        customer=CustomerState(phone="5511999990000"),
    )
    orch.conversations.reset_conversation_memory = AsyncMock(return_value=fresh)
    orch.conversations.insert_bot_outbound = AsyncMock(return_value="out-1")
    orch.conversations.finalize_batch_messages = AsyncMock()

    batch = InboundBatch(
        batch_id="batch-reset",
        conversation_id="conv-1",
        phone="5511999990000",
        instance_name="facilcar",
        anchor_message_id="m1",
        cutoff=datetime(2026, 8, 27, 12, 0, 0),
        message_ids=["m1"],
        segments=[
            InboundSegment(
                message_id="m1",
                content_type=ContentType.TEXT,
                text="/deletar",
                order=0,
            )
        ],
        status=BatchStatus.PROCESSING,
    )

    result = await orch._handle_reset_memory_command(
        batch=batch, phone="5511999990000", instance="facilcar"
    )

    orch.conversations.reset_conversation_memory.assert_awaited_once_with(
        "conv-1", phone="5511999990000"
    )
    orch.evolution.send_text.assert_awaited_once()
    assert result.outbound_texts == [RESET_MEMORY_CONFIRMATION_PT]
    assert result.state.intent == BusinessIntent.UNKNOWN
    assert result.state.lifecycle.status == LifecycleStatus.BOT_ACTIVE
    assert result.state.facts == {}
    assert result.action_plan.reason_code == "command_deletar"
    finalize = orch.conversations.finalize_batch_messages
    finalize.assert_awaited_once()
    kwargs = finalize.await_args.kwargs
    assert kwargs["status"] == "DONE"
    assert kwargs["batch_patch"]["result"]["action"] == "reset_memory"
    assert kwargs["batch_patch"]["result"]["outbound_sent"] is True
