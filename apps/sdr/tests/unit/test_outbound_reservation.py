"""Reserve bot outbound before Evolution send (Phase 11 Frente F).

F1–F8: intent before transport, early echo reconcile, provider id later,
send timeout, duplicate external id, retry no dup, echo does not assume,
real human still distinguishable. Evolution is faked — no sleep.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sdr.debounce import QuietWindowResult
from sdr.domain.inbound_batch import BATCH_JSON_KEY
from sdr.domain.outbound_reservation import (
    RESERVED_BOT_PROVIDER_PREFIX,
    is_reserved_bot_provider_id,
    new_reserved_bot_provider_id,
)
from sdr.infrastructure.conversation_repository import ConversationRepository
from sdr.infrastructure.evolution_client import EvolutionError
from sdr.orchestrator import StubEvolutionSender
from tests.unit.test_ownership_suppression import (
    MSG_ID,
    LiveStore,
    _message_result,
    _orchestrator,
)


class _UniqueHit(Exception):
    sqlstate = "23505"


def _pool_with_conn(conn: AsyncMock) -> MagicMock:
    pool = MagicMock()
    pool.acquire = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(),
        )
    )
    return pool


@pytest.fixture
def patch_quiet():
    async def _immediate(*args, **kwargs):
        return QuietWindowResult(close_reason="quiet", window_ms=0, waited_ms=0, extensions=0)

    with patch("sdr.orchestrator.wait_until_quiet", side_effect=_immediate):
        yield


def test_reserved_provider_id_shape() -> None:
    pid = new_reserved_bot_provider_id()
    assert pid.startswith(RESERVED_BOT_PROVIDER_PREFIX)
    assert is_reserved_bot_provider_id(pid) is True
    assert is_reserved_bot_provider_id("wa-seller-1") is False
    assert is_reserved_bot_provider_id("") is False


@pytest.mark.asyncio
async def test_f1_intent_persisted_before_transport(patch_quiet) -> None:
    store = LiveStore()
    log: list[str] = []
    evolution = StubEvolutionSender()
    orig_send = evolution.send_text

    async def send_text(*args, **kwargs):
        log.append("send")
        await orig_send(*args, **kwargs)
        return "wa-f1"

    evolution.send_text = send_text  # type: ignore[method-assign]
    orch = _orchestrator(store, evolution=evolution)
    orig_insert = orch.conversations.insert_bot_outbound
    orig_update = orch.conversations.update_bot_provider_id

    async def insert(**kwargs):
        log.append("insert")
        pid = str(kwargs.get("provider_message_id") or "")
        assert pid.startswith(RESERVED_BOT_PROVIDER_PREFIX)
        return await orig_insert(**kwargs)

    async def update(**kwargs):
        log.append("update")
        return await orig_update(**kwargs)

    orch.conversations.insert_bot_outbound = AsyncMock(side_effect=insert)
    orch.conversations.update_bot_provider_id = AsyncMock(side_effect=update)

    async def fake_process_turn(**kwargs):
        return _message_result(["Olá, sou a Júlia da FacilCar."])

    with patch("sdr.orchestrator.process_turn", side_effect=fake_process_turn):
        await orch.process_batch_seed(store.seed())

    assert log == ["insert", "send", "update"]
    assert store.outbound[0]["provider_message_id"] == "wa-f1"


@pytest.mark.asyncio
async def test_f2_early_echo_unique_conflict_reconciles_pending() -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(
        side_effect=[
            _UniqueHit("instanceName_providerMessageId"),
            {"id": "msg-echo"},
        ]
    )
    conn.execute = AsyncMock()
    repo = ConversationRepository(_pool_with_conn(conn))

    correlated = await repo.update_bot_provider_id(
        message_id="msg-pending",
        instance_name="facilcar-sdr",
        provider_message_id="wa-julia-echo",
    )

    assert correlated == "msg-echo"
    mark_sql = conn.fetchrow.await_args_list[1].args[0]
    assert '"isBotSent" = true' in mark_sql
    assert '"isHumanSent" = false' in mark_sql
    delete_sql = conn.execute.await_args.args[0]
    assert "DELETE FROM" in delete_sql
    assert conn.execute.await_args.args[1] == "msg-pending"
    assert "bot-pending-%" in conn.execute.await_args.args[2]


@pytest.mark.asyncio
async def test_f3_provider_id_later_updates_reserved_row() -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"id": "msg-pending"})
    repo = ConversationRepository(_pool_with_conn(conn))

    result = await repo.update_bot_provider_id(
        message_id="msg-pending",
        instance_name="facilcar-sdr",
        provider_message_id="wa-julia-1",
    )

    assert result == "msg-pending"
    sql, msg_id, new_id, instance, like = conn.fetchrow.await_args.args
    assert "SET \"providerMessageId\" = $2" in sql
    assert '"isBotSent" = true' in sql
    assert msg_id == "msg-pending"
    assert new_id == "wa-julia-1"
    assert instance == "facilcar-sdr"
    assert like.startswith(RESERVED_BOT_PROVIDER_PREFIX)


@pytest.mark.asyncio
async def test_f4_send_timeout_keeps_reserved_bot_row(patch_quiet) -> None:
    store = LiveStore()
    log: list[str] = []
    evolution = StubEvolutionSender()

    async def send_text(*args, **kwargs):
        log.append("send")
        raise TimeoutError("read timeout")

    evolution.send_text = send_text  # type: ignore[method-assign]
    orch = _orchestrator(store, evolution=evolution)
    orig_insert = orch.conversations.insert_bot_outbound
    orig_update = orch.conversations.update_bot_provider_id

    async def insert(**kwargs):
        log.append("insert")
        return await orig_insert(**kwargs)

    async def update(**kwargs):
        log.append("update")
        return await orig_update(**kwargs)

    orch.conversations.insert_bot_outbound = AsyncMock(side_effect=insert)
    orch.conversations.update_bot_provider_id = AsyncMock(side_effect=update)

    async def fake_process_turn(**kwargs):
        return _message_result(["Olá, sou a Júlia da FacilCar."])

    with patch("sdr.orchestrator.process_turn", side_effect=fake_process_turn):
        with pytest.raises(EvolutionError):
            await orch.process_batch_seed(store.seed())

    assert log == ["insert", "send"]
    assert len(store.outbound) == 1
    assert str(store.outbound[0]["provider_message_id"]).startswith(
        RESERVED_BOT_PROVIDER_PREFIX
    )


@pytest.mark.asyncio
async def test_f5_duplicate_external_id_is_idempotent() -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"id": "msg-pending"})
    repo = ConversationRepository(_pool_with_conn(conn))

    first = await repo.update_bot_provider_id(
        message_id="msg-pending",
        instance_name="facilcar-sdr",
        provider_message_id="wa-dup-1",
    )
    second = await repo.update_bot_provider_id(
        message_id="msg-pending",
        instance_name="facilcar-sdr",
        provider_message_id="wa-dup-1",
    )
    assert first == second == "msg-pending"
    sql = conn.fetchrow.await_args.args[0]
    assert '"providerMessageId" = $2' in sql

    conn.fetchrow = AsyncMock(return_value=None)
    msg_id = await repo.insert_bot_outbound(
        conversation_id="conv-a",
        instance_name="facilcar-sdr",
        text="echo",
        provider_message_id="wa-dup-1",
    )
    sql = conn.fetchrow.await_args.args[0]
    assert "ON CONFLICT" in sql and "DO NOTHING" in sql
    assert msg_id


@pytest.mark.asyncio
async def test_f6_retry_reuses_reserved_row(patch_quiet) -> None:
    store = LiveStore()
    evolution = StubEvolutionSender()
    sends = {"n": 0}

    async def send_text(*args, **kwargs):
        sends["n"] += 1
        if sends["n"] == 1:
            raise TimeoutError("read timeout")
        return "wa-retry-1"

    evolution.send_text = send_text  # type: ignore[method-assign]
    orch = _orchestrator(store, evolution=evolution)

    async def fake_process_turn(**kwargs):
        return _message_result(["Olá, sou a Júlia da FacilCar."])

    with patch("sdr.orchestrator.process_turn", side_effect=fake_process_turn):
        with pytest.raises(EvolutionError):
            await orch.process_batch_seed(store.seed())

        assert len(store.outbound) == 1
        reserved = store.outbound[0]["provider_message_id"]
        assert str(reserved).startswith(RESERVED_BOT_PROVIDER_PREFIX)

        patch_body = store.finalizes[-1]["batch_patch"]
        store.messages[MSG_ID]["processingStatus"] = "ERROR"
        store.messages[MSG_ID]["turnFactsJson"] = {BATCH_JSON_KEY: patch_body}
        seed = store.seed()
        seed["processingStatus"] = "ERROR"
        seed["turnFactsJson"] = store.messages[MSG_ID]["turnFactsJson"]
        await orch.process_batch_seed(seed)

    assert len(store.outbound) == 1
    assert store.outbound[0]["provider_message_id"] == "wa-retry-1"
    assert orch.conversations.insert_bot_outbound.await_count == 1


@pytest.mark.asyncio
async def test_f7_reserved_then_correlated_id_is_bot_not_human() -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"id": "msg-bot", "?column?": 1})
    repo = ConversationRepository(_pool_with_conn(conn))

    await repo.insert_bot_outbound(
        conversation_id="conv-a",
        instance_name="facilcar-sdr",
        text="Olá, sou a Júlia da FacilCar.",
        provider_message_id="bot-pending-f7",
    )
    insert_sql = conn.fetchrow.await_args.args[0]
    assert "$5, true, false, true, 'DONE'" in insert_sql

    conn.fetchrow = AsyncMock(return_value={"id": "msg-bot"})
    await repo.update_bot_provider_id(
        message_id="msg-bot",
        instance_name="facilcar-sdr",
        provider_message_id="wa-julia-f7",
    )
    conn.fetchrow = AsyncMock(return_value={"?column?": 1})
    found = await repo.has_bot_outbound_provider_id(
        instance_name="facilcar-sdr",
        provider_message_id="wa-julia-f7",
    )
    assert found is True


@pytest.mark.asyncio
async def test_f8_unmatched_human_id_is_not_a_bot_row() -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    repo = ConversationRepository(_pool_with_conn(conn))

    found = await repo.has_bot_outbound_provider_id(
        instance_name="facilcar-sdr",
        provider_message_id="wa-seller-real",
    )
    assert found is False
    assert conn.fetchrow.await_args.args[2] == "wa-seller-real"


@pytest.mark.asyncio
async def test_f4_blank_update_keeps_reservation() -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock()
    repo = ConversationRepository(_pool_with_conn(conn))

    kept = await repo.update_bot_provider_id(
        message_id="msg-pending",
        instance_name="facilcar-sdr",
        provider_message_id="  ",
    )
    assert kept == "msg-pending"
    conn.fetchrow.assert_not_awaited()


@pytest.mark.asyncio
async def test_find_open_bot_reservation_sql_is_pending_scoped() -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(
        return_value={"id": "msg-pending", "providerMessageId": "bot-pending-1"}
    )
    repo = ConversationRepository(_pool_with_conn(conn))
    found = await repo.find_open_bot_reservation(
        conversation_id="conv-a",
        instance_name="facilcar-sdr",
        text="Olá, sou a Júlia da FacilCar.",
    )
    assert found == {"id": "msg-pending", "providerMessageId": "bot-pending-1"}
    sql = conn.fetchrow.await_args.args[0]
    assert '"isBotSent" = true' in sql
    assert "LIKE $4" in sql
