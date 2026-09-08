"""Column botStatus + ownershipRevision is the ownership source of truth.

JSON may lag or lie; overlay reconciles on load. Outbound is authorized only
from the persisted column (re-read), never from canonicalStateJson lifecycle.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sdr.application.outbound_guard import (
    column_authorizes_outbound,
    human_assumed_live,
    read_live_ownership,
)
from sdr.application.process_turn import process_turn
from sdr.debounce import QuietWindowResult
from sdr.domain.handoff import is_ai_silenced
from sdr.domain.inbound_batch import BATCH_JSON_KEY
from sdr.domain.ownership import resume_ai
from sdr.domain.types import (
    Action,
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
    pg_update_applied,
    state_from_conversation_row,
)
from sdr.orchestrator import StubEvolutionSender
from tests.unit.test_ownership_suppression import (
    CONV_ID,
    MSG_ID,
    PHONE,
    LiveStore,
    _assert_suppressed,
    _message_result,
    _orchestrator,
)


T0 = datetime(2026, 9, 8, 18, 0, 0)
THREAD = "conv-sot"
PHONE_SOT = "5511999000001"


@pytest.fixture
def patch_quiet():
    async def _immediate(*args, **kwargs):
        return QuietWindowResult(close_reason="quiet", window_ms=0, waited_ms=0, extensions=0)

    with patch("sdr.orchestrator.wait_until_quiet", side_effect=_immediate):
        yield


def _json_state(
    *,
    status: str,
    ownership_revision: int = 0,
    assumed_by_user_id: str | None = None,
    extra_facts: dict | None = None,
) -> ConversationCanonicalState:
    return ConversationCanonicalState(
        thread_id=THREAD,
        customer=CustomerState(phone=PHONE_SOT, name="Ana"),
        lifecycle=LifecycleState(status=LifecycleStatus(status)),
        ownership_revision=ownership_revision,
        assumed_by_user_id=assumed_by_user_id,
        facts=dict(extra_facts or {"desired_model": "Civic"}),
    )


def _row(
    *,
    bot_status: str,
    json_status: str,
    ownership_revision: int = 0,
    json_revision: int | None = None,
    assumed_by_user_id: str | None = None,
    json_assumed_by: str | None = None,
    resumed_by_user_id: str | None = None,
) -> dict:
    payload = _json_state(
        status=json_status,
        ownership_revision=json_revision if json_revision is not None else 99,
        assumed_by_user_id=json_assumed_by or "json-attacker",
        extra_facts={"keep": True, "owner": "json"},
    )
    return {
        "id": THREAD,
        "phone": PHONE_SOT,
        "botStatus": bot_status,
        "activeLeadIds": [],
        "canonicalStateJson": canonical_state_to_json(payload),
        "ownershipRevision": ownership_revision,
        "assumedByUserId": assumed_by_user_id,
        "assumedAt": T0 if assumed_by_user_id else None,
        "resumedByUserId": resumed_by_user_id,
        "resumedAt": T0 if resumed_by_user_id else None,
        "resumeReason": "authorized" if resumed_by_user_id else None,
        "handoffAt": T0,
    }


class DivergentStore(LiveStore):
    """Live column differs from canonicalStateJson.lifecycle (web assume lag)."""

    def __init__(self, *, bot_status: str, json_status: str, ownership_revision: int = 0) -> None:
        super().__init__(bot_status=bot_status)
        self.json_status = json_status
        self.ownership_revision = ownership_revision

    def conv_row(self) -> dict:
        row = super().conv_row()
        stale = ConversationCanonicalState(
            thread_id=CONV_ID,
            customer=CustomerState(phone=PHONE, name="Ana"),
            lifecycle=LifecycleState(status=LifecycleStatus(self.json_status)),
            ownership_revision=0,
        )
        row["canonicalStateJson"] = canonical_state_to_json(stale)
        row["botStatus"] = self.bot_status
        row["ownershipRevision"] = self.ownership_revision
        return row


def test_b1_column_human_active_stale_json_ai_silences_on_load() -> None:
    for json_status in (
        LifecycleStatus.BOT_ACTIVE.value,
        LifecycleStatus.HANDOFF_SENT.value,
        LifecycleStatus.AI_RESUMED.value,
    ):
        loaded = state_from_conversation_row(
            _row(
                bot_status=LifecycleStatus.HUMAN_ACTIVE.value,
                json_status=json_status,
                ownership_revision=4,
                assumed_by_user_id="user-alice",
            )
        )
        assert loaded.lifecycle.status == LifecycleStatus.HUMAN_ACTIVE
        assert loaded.ownership_revision == 4
        assert is_ai_silenced(loaded) is True
        assert column_authorizes_outbound(LifecycleStatus.HUMAN_ACTIVE.value) is False


@pytest.mark.asyncio
async def test_b1_process_turn_and_outbound_guard_silence() -> None:
    loaded = state_from_conversation_row(
        _row(
            bot_status=LifecycleStatus.HUMAN_ACTIVE.value,
            json_status=LifecycleStatus.BOT_ACTIVE.value,
            ownership_revision=2,
            assumed_by_user_id="user-alice",
        )
    )

    async def understand(text, state):
        raise AssertionError("understand must not run while column is HUMAN_ACTIVE")

    result = await process_turn(state=loaded, inbound_text="quero financiar", understand=understand)
    assert result.outbound_texts == []
    assert result.action_plan.action == Action.NO_REPLY

    conv = MagicMock()
    conv.get_by_id = AsyncMock(
        return_value=_row(
            bot_status=LifecycleStatus.HUMAN_ACTIVE.value,
            json_status=LifecycleStatus.HANDOFF_SENT.value,
            ownership_revision=2,
            assumed_by_user_id="user-alice",
        )
    )
    assumed, revision = await human_assumed_live(conv, THREAD)
    assert assumed is True
    assert revision == 2


@pytest.mark.asyncio
async def test_b1_orchestrator_stale_json_does_not_send(patch_quiet) -> None:
    store = DivergentStore(
        bot_status=LifecycleStatus.HUMAN_ACTIVE.value,
        json_status=LifecycleStatus.HANDOFF_SENT.value,
        ownership_revision=3,
    )
    evolution = StubEvolutionSender()
    orch = _orchestrator(store, evolution=evolution)

    await orch.process_batch_seed(store.seed(stale_bot_status=LifecycleStatus.BOT_ACTIVE.value))

    _assert_suppressed(store, evolution)


@pytest.mark.parametrize(
    "column_status",
    [LifecycleStatus.HANDOFF_SENT.value, LifecycleStatus.AI_RESUMED.value],
)
def test_b2_column_ai_stale_json_human_column_wins(column_status: str) -> None:
    loaded = state_from_conversation_row(
        _row(
            bot_status=column_status,
            json_status=LifecycleStatus.HUMAN_ACTIVE.value,
            ownership_revision=5,
            json_revision=1,
            json_assumed_by="stale-human",
        )
    )
    assert loaded.lifecycle.status == LifecycleStatus(column_status)
    assert loaded.ownership_revision == 5
    assert is_ai_silenced(loaded) is False
    assert column_authorizes_outbound(column_status) is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "column_status",
    [LifecycleStatus.HANDOFF_SENT.value, LifecycleStatus.AI_RESUMED.value],
)
async def test_b2_process_turn_may_talk_when_column_is_ai(column_status: str) -> None:
    loaded = state_from_conversation_row(
        _row(
            bot_status=column_status,
            json_status=LifecycleStatus.HUMAN_ACTIVE.value,
            ownership_revision=5,
        )
    )

    async def understand(text, state):
        return TurnFacts(intent=state.intent, language="pt-BR")

    with patch(
        "sdr.understanding.response_composer.compose_response",
        new=AsyncMock(return_value=["podemos seguir"]),
    ):
        result = await process_turn(state=loaded, inbound_text="oi", understand=understand)
    assert result.action_plan.reason_code != "ai_silenced"
    assert is_ai_silenced(result.state) is False


@pytest.mark.asyncio
async def test_b2_orchestrator_column_ai_allows_send(patch_quiet) -> None:
    store = DivergentStore(
        bot_status=LifecycleStatus.AI_RESUMED.value,
        json_status=LifecycleStatus.HUMAN_ACTIVE.value,
        ownership_revision=2,
    )
    evolution = StubEvolutionSender()
    orch = _orchestrator(store, evolution=evolution)

    async def fake_process_turn(**kwargs):
        return _message_result()

    with patch("sdr.orchestrator.process_turn", side_effect=fake_process_turn):
        await orch.process_batch_seed(store.seed(stale_bot_status=LifecycleStatus.HUMAN_ACTIVE.value))

    assert evolution.sent, "column AI_RESUMED must authorize send despite stale JSON HUMAN_ACTIVE"
    assert store.finalizes
    result = store.last_batch_result()
    assert result.get("suppressed_reason") != "human_active"


@pytest.mark.asyncio
async def test_b3_save_concurrent_cannot_reduce_revision() -> None:
    conn = AsyncMock()
    captured: dict = {}

    async def execute(sql, *args):
        captured["sql"] = sql
        captured["args"] = args
        live_revision = 7
        snapshot_revision = args[6]
        if snapshot_revision != live_revision:
            return "UPDATE 0"
        return "UPDATE 1"

    conn.execute = AsyncMock(side_effect=execute)
    pool = MagicMock()
    pool.acquire = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=conn), __aexit__=AsyncMock())
    )
    repo = ConversationRepository(pool)
    stale = _json_state(status=LifecycleStatus.HANDOFF_SENT.value, ownership_revision=3)
    applied = await repo.save_canonical_state(THREAD, stale)
    assert applied is False
    assert pg_update_applied("UPDATE 0") is False
    where = captured["sql"].split("WHERE", 1)[1]
    assert '"ownershipRevision" = $7' in where
    assert "HUMAN_ACTIVE" in where
    set_clause = captured["sql"].split("WHERE", 1)[0]
    assert '"ownershipRevision" = $7' in set_clause
    assert captured["args"][6] == 3


def test_b4_overlay_reads_same_columns_web_claim_updates() -> None:
    """claimLeadAction CAS-updates Conversation.botStatus + ownershipRevision.

    Worker load overlays those same columns over JSON — one SoT, not Lead.status.
    """
    loaded = state_from_conversation_row(
        _row(
            bot_status=LifecycleStatus.HUMAN_ACTIVE.value,
            json_status=LifecycleStatus.HANDOFF_SENT.value,
            ownership_revision=1,
            assumed_by_user_id="user-alice",
        )
    )
    assert loaded.lifecycle.status.value == "HUMAN_ACTIVE"
    assert loaded.ownership_revision == 1
    assert loaded.assumed_by_user_id == "user-alice"
    assert loaded.facts.get("keep") is True


def test_b5_reload_preserves_ownership_from_columns() -> None:
    first = state_from_conversation_row(
        _row(
            bot_status=LifecycleStatus.HUMAN_ACTIVE.value,
            json_status=LifecycleStatus.BOT_ACTIVE.value,
            ownership_revision=6,
            assumed_by_user_id="user-alice",
        )
    )
    dumped = canonical_state_to_json(first)
    reloaded = canonical_state_from_json(
        dumped,
        thread_id=THREAD,
        phone=PHONE_SOT,
        bot_status=LifecycleStatus.HUMAN_ACTIVE.value,
        ownership_revision=6,
        assumed_by_user_id="user-alice",
        assumed_at=T0,
    )
    assert reloaded.lifecycle.status == LifecycleStatus.HUMAN_ACTIVE
    assert reloaded.ownership_revision == 6
    assert reloaded.assumed_by_user_id == "user-alice"


@pytest.mark.asyncio
async def test_b6_resume_bumps_revision_atomically() -> None:
    assumed = _json_state(
        status=LifecycleStatus.HUMAN_ACTIVE.value,
        ownership_revision=4,
        assumed_by_user_id="user-alice",
    )
    resumed = resume_ai(
        assumed,
        actor_user_id="user-alice",
        reason="devolver para a júlia",
        expected_revision=4,
    )
    assert resumed.ownership_revision == 5
    assert resumed.lifecycle.status == LifecycleStatus.AI_RESUMED

    sqls: list[str] = []
    current = _row(
        bot_status=LifecycleStatus.HUMAN_ACTIVE.value,
        json_status=LifecycleStatus.HUMAN_ACTIVE.value,
        ownership_revision=4,
        json_revision=4,
        assumed_by_user_id="user-alice",
    )
    conn = AsyncMock()

    async def fetchrow(sql, *args):
        sqls.append(sql)
        if "UPDATE" in sql and "AI_RESUMED" in sql:
            assert '"ownershipRevision" = "ownershipRevision" + 1' in sql
            assert '"ownershipRevision" = $6' in sql.split("WHERE", 1)[1]
            current["botStatus"] = LifecycleStatus.AI_RESUMED.value
            current["ownershipRevision"] = int(current["ownershipRevision"]) + 1
            current["resumedByUserId"] = "user-alice"
            current["canonicalStateJson"] = args[1]
        return dict(current)

    conn.fetchrow = AsyncMock(side_effect=fetchrow)
    pool = MagicMock()
    pool.acquire = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=conn), __aexit__=AsyncMock())
    )
    repo = ConversationRepository(pool)
    out = await repo.resume_ai(
        THREAD,
        actor_user_id="user-alice",
        reason="devolver para a júlia",
        expected_revision=4,
    )
    assert out.ownership_revision == 5
    assert out.lifecycle.status == LifecycleStatus.AI_RESUMED
    joined = "\n".join(sqls)
    assert '"ownershipRevision" = "ownershipRevision" + 1' in joined
    assert '"Lead"' not in joined


def test_b7_arbitrary_json_payload_cannot_flip_owner_or_status() -> None:
    loaded = state_from_conversation_row(
        _row(
            bot_status=LifecycleStatus.BOT_ACTIVE.value,
            json_status=LifecycleStatus.HUMAN_ACTIVE.value,
            ownership_revision=0,
            json_revision=42,
            json_assumed_by="payload-attacker",
            assumed_by_user_id=None,
        )
    )
    assert loaded.lifecycle.status == LifecycleStatus.BOT_ACTIVE
    assert loaded.ownership_revision == 0
    assert loaded.assumed_by_user_id is None
    assert is_ai_silenced(loaded) is False


@pytest.mark.asyncio
async def test_b8_retry_with_stale_json_does_not_send(patch_quiet) -> None:
    store = DivergentStore(
        bot_status=LifecycleStatus.HUMAN_ACTIVE.value,
        json_status=LifecycleStatus.BOT_ACTIVE.value,
        ownership_revision=8,
    )
    store.messages[MSG_ID]["processingStatus"] = "ERROR"
    store.messages[MSG_ID]["turnFactsJson"] = {
        BATCH_JSON_KEY: {
            "batch_id": "batch-retry-stale-json",
            "message_ids": [MSG_ID],
            "cutoff": "2026-09-08T18:00:00Z",
            "status": "ERROR",
            "result": {"outbound_sent": False},
        }
    }
    evolution = StubEvolutionSender()
    understand = AsyncMock(return_value=TurnFacts(language="pt-BR"))
    orch = _orchestrator(store, understand=understand, evolution=evolution)

    seed = store.seed(stale_bot_status=LifecycleStatus.BOT_ACTIVE.value)
    seed["processingStatus"] = "ERROR"
    seed["turnFactsJson"] = store.messages[MSG_ID]["turnFactsJson"]

    await orch.process_batch_seed(seed)

    understand.assert_not_called()
    _assert_suppressed(store, evolution)


@pytest.mark.asyncio
async def test_b8_outbound_guard_ignores_stale_json_lifecycle() -> None:
    conv = MagicMock()
    conv.get_by_id = AsyncMock(
        return_value=_row(
            bot_status=LifecycleStatus.HUMAN_ACTIVE.value,
            json_status=LifecycleStatus.BOT_ACTIVE.value,
            ownership_revision=8,
            assumed_by_user_id="user-alice",
        )
    )
    status, revision = await read_live_ownership(conv, THREAD)
    assert status == LifecycleStatus.HUMAN_ACTIVE.value
    assert revision == 8
    assert column_authorizes_outbound(status) is False
