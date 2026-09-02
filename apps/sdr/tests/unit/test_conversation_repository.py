"""Unit tests for ConversationRepository — list_recent_turns and state persistence."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from sdr.infrastructure.conversation_repository import ConversationRepository


def _pool_with_rows(rows: list[dict]) -> MagicMock:
    """Build a mock asyncpg pool that returns the given rows from conn.fetch."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=rows)
    pool = MagicMock()
    pool.acquire = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(),
        )
    )
    return pool


def _row(direction: str, is_bot: bool, from_me: bool, text: str) -> dict:
    return {
        "direction": direction,
        "isBotSent": is_bot,
        "fromMe": from_me,
        "text": text,
    }


@pytest.mark.asyncio
async def test_list_recent_turns_labels_correctly() -> None:
    """Bot outbound messages must be labeled 'julia'; inbound must be 'customer'."""
    rows = [
        _row("OUTBOUND", True, True, "Olá! Sou a Júlia da FacilCar."),
        _row("INBOUND", False, False, "Gostaria de ver o Corolla"),
        _row("OUTBOUND", True, True, "Seria compra ou troca?"),
        _row("INBOUND", False, False, "Compra mesmo"),
    ]
    # list_recent_turns queries DESC then reverses → oldest first.
    # Mock returns rows in the DESC order (as DB would).
    pool = _pool_with_rows(list(reversed(rows)))  # DB returns newest first
    repo = ConversationRepository(pool)

    turns = await repo.list_recent_turns("conv-1", limit=5)

    assert len(turns) == 4
    assert turns[0] == {"role": "julia", "text": "Olá! Sou a Júlia da FacilCar."}
    assert turns[1] == {"role": "customer", "text": "Gostaria de ver o Corolla"}
    assert turns[2] == {"role": "julia", "text": "Seria compra ou troca?"}
    assert turns[3] == {"role": "customer", "text": "Compra mesmo"}


@pytest.mark.asyncio
async def test_list_recent_turns_excludes_empty_text() -> None:
    """Messages with empty or None text must be excluded from the result."""
    rows = [
        _row("INBOUND", False, False, ""),
        _row("OUTBOUND", True, True, "  "),
        _row("INBOUND", False, False, "Quero o Corolla"),
    ]
    pool = _pool_with_rows(rows)
    repo = ConversationRepository(pool)

    turns = await repo.list_recent_turns("conv-2", limit=5)

    assert len(turns) == 1
    assert turns[0]["text"] == "Quero o Corolla"


@pytest.mark.asyncio
async def test_list_recent_turns_empty_conversation() -> None:
    """No messages → empty list, no error."""
    pool = _pool_with_rows([])
    repo = ConversationRepository(pool)

    turns = await repo.list_recent_turns("conv-3", limit=5)

    assert turns == []


@pytest.mark.asyncio
async def test_list_recent_turns_passes_limit_to_sql() -> None:
    """The limit arg must be forwarded to the SQL query, not applied in Python only."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    pool = _pool_with_rows([])
    # Override pool to capture the fetch call args.
    pool.acquire = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(),
        )
    )
    repo = ConversationRepository(pool)

    await repo.list_recent_turns("conv-4", limit=6)

    call_args = conn.fetch.await_args
    assert call_args is not None
    args = call_args.args
    # Second positional arg after the SQL is the limit.
    assert args[2] == 6
