"""HUMAN_ACTIVE must win races against the worker (Phase 10 Frente B).

No real sleeps — races use asyncio.Event. Conversation.botStatus is re-read
from the live store, never from a stale seed snapshot.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sdr.application.process_turn import ProcessTurnResult
from sdr.config import Settings
from sdr.debounce import QuietWindowResult
from sdr.domain.inbound_batch import BATCH_JSON_KEY
from sdr.domain.types import (
    Action,
    ActionPlan,
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    LifecycleState,
    LifecycleStatus,
    TurnFacts,
)
from sdr.infrastructure.conversation_repository import canonical_state_to_json
from sdr.orchestrator import Orchestrator, StubEvolutionSender

CONV_ID = "conv-suppression"
PHONE = "5511999000001"
INSTANCE = "facilcar-sdr"
MSG_ID = "msg-in-1"
T0 = datetime(2026, 9, 8, 18, 0, 0)


def _settings() -> Settings:
    return Settings.model_construct(
        julia_enabled=True,
        sdr_debounce_ms=0,
        sdr_debounce_max_ms=0,
        sdr_environment="sandbox",
        openai_api_key="",
    )


def _quiet() -> QuietWindowResult:
    return QuietWindowResult(close_reason="quiet", window_ms=0, waited_ms=0, extensions=0)


class LiveStore:
    """In-memory conversation + messages; botStatus is the live DB column."""

    def __init__(self, *, bot_status: str = LifecycleStatus.BOT_ACTIVE.value) -> None:
        self.bot_status = bot_status
        self.ownership_revision = 0
        self.assumed_by: str | None = None
        self.assumed_at: datetime | None = None
        self.messages: dict[str, dict[str, Any]] = {}
        self.outbound: list[dict[str, Any]] = []
        self.finalizes: list[dict[str, Any]] = []
        self.deleted_ids: list[str] = []
        self.ingest(
            MSG_ID,
            text="Oi, quero um Civic",
            processing_status="PENDING",
        )

    def ingest(
        self,
        message_id: str,
        *,
        text: str,
        processing_status: str = "PENDING",
        turn_facts: dict | None = None,
    ) -> dict[str, Any]:
        row = {
            "id": message_id,
            "conversationId": CONV_ID,
            "contentType": "TEXT",
            "text": text,
            "transcription": None,
            "providerMessageId": f"prov-{message_id}",
            "mediaMimeType": None,
            "createdAt": T0,
            "turnFactsJson": turn_facts,
            "processingStatus": processing_status,
            "direction": "INBOUND",
            "fromMe": False,
            "instanceName": INSTANCE,
        }
        self.messages[message_id] = row
        return row

    def assume(self, *, actor: str = "user-alice") -> None:
        self.bot_status = LifecycleStatus.HUMAN_ACTIVE.value
        self.ownership_revision += 1
        self.assumed_by = actor
        self.assumed_at = T0

    def canonical_state(self) -> ConversationCanonicalState:
        return ConversationCanonicalState(
            thread_id=CONV_ID,
            customer=CustomerState(phone=PHONE, name="Ana"),
            lifecycle=LifecycleState(status=LifecycleStatus(self.bot_status)),
            ownership_revision=self.ownership_revision,
            assumed_by_user_id=self.assumed_by,
            assumed_at=self.assumed_at.isoformat() if self.assumed_at else None,
        )

    def conv_row(self) -> dict[str, Any]:
        return {
            "id": CONV_ID,
            "phone": PHONE,
            "botStatus": self.bot_status,
            "activeLeadIds": [],
            "canonicalStateJson": canonical_state_to_json(self.canonical_state()),
            "ownershipRevision": self.ownership_revision,
            "assumedByUserId": self.assumed_by,
            "assumedAt": self.assumed_at,
            "resumedByUserId": None,
            "resumedAt": None,
            "resumeReason": None,
            "handoffAt": None,
        }

    def seed(self, *, stale_bot_status: str | None = None, **extra: Any) -> dict[str, Any]:
        row = dict(self.messages[MSG_ID])
        row["conversationId"] = CONV_ID
        row["conversationPhone"] = PHONE
        row["conversationInstance"] = INSTANCE
        row["instanceName"] = INSTANCE
        row["conversationBotStatus"] = (
            stale_bot_status if stale_bot_status is not None else self.bot_status
        )
        row.update(extra)
        return row

    def last_batch_result(self) -> dict[str, Any]:
        assert self.finalizes, "expected finalize_batch_messages"
        patch = self.finalizes[-1]["batch_patch"] or {}
        result = patch.get("result") or {}
        assert isinstance(result, dict)
        return result


def _message_result(outbound_texts: list[str] | None = None) -> ProcessTurnResult:
    texts = outbound_texts if outbound_texts is not None else ["Oi Ana, sou a Júlia da FacilCar."]
    return ProcessTurnResult(
        action_plan=ActionPlan(action=Action.SMALLTALK, reason_code="greeting_or_chitchat"),
        state=ConversationCanonicalState(
            thread_id=CONV_ID,
            customer=CustomerState(phone=PHONE, name="Ana"),
            intent=BusinessIntent.SMALLTALK,
        ),
        outbound_texts=list(texts),
        turn_facts=TurnFacts(intent=BusinessIntent.SMALLTALK, language="pt-BR"),
        tool_results=[],
    )


def _wire_repos(orch: Orchestrator, store: LiveStore) -> None:
    conv = MagicMock()

    async def get_by_id(_cid: str):
        return store.conv_row()

    async def load_canonical_state(_cid: str):
        return store.canonical_state()

    async def list_pending_inbound_up_to(_cid: str, *, cutoff=None):
        return [
            dict(m)
            for m in store.messages.values()
            if m["processingStatus"] == "PENDING" and m["direction"] == "INBOUND"
        ]

    async def claim_inbound_batch(**kwargs):
        ids = list(kwargs.get("message_ids") or store.messages.keys())
        claimed = []
        for mid in ids:
            row = store.messages.get(mid)
            if row is None or row["processingStatus"] != "PENDING":
                continue
            row["processingStatus"] = "PROCESSING"
            claimed.append(dict(row))
        return claimed

    async def reclaim_error_batch(*, message_ids, batch_meta):
        return [dict(store.messages[mid]) for mid in message_ids if mid in store.messages]

    async def finalize_batch_messages(message_ids, *, status, batch_patch):
        store.finalizes.append(
            {"message_ids": list(message_ids), "status": status, "batch_patch": batch_patch}
        )
        for mid in message_ids:
            if mid in store.messages:
                store.messages[mid]["processingStatus"] = status

    async def mark_message_skipped(message_id, *, reason):
        if message_id in store.messages:
            store.messages[message_id]["processingStatus"] = f"SKIPPED:{reason}"[:64]

    async def insert_bot_outbound(**kwargs):
        store.outbound.append(dict(kwargs))
        return f"out-{len(store.outbound)}"

    async def save_canonical_state(_cid: str, state: ConversationCanonicalState) -> bool:
        expected = int(getattr(state, "ownership_revision", 0) or 0)
        if store.bot_status == LifecycleStatus.HUMAN_ACTIVE.value:
            return False
        if int(store.ownership_revision) != expected:
            return False
        status = getattr(getattr(state, "lifecycle", None), "status", None)
        if status is not None:
            store.bot_status = status.value if hasattr(status, "value") else str(status)
        store.ownership_revision = expected
        return True

    async def delete_message(message_id, *args, **kwargs):
        store.deleted_ids.append(str(message_id))
        store.messages.pop(str(message_id), None)

    conv.get_by_id = AsyncMock(side_effect=get_by_id)
    conv.load_canonical_state = AsyncMock(side_effect=load_canonical_state)
    conv.list_pending_inbound_up_to = AsyncMock(side_effect=list_pending_inbound_up_to)
    conv.claim_inbound_batch = AsyncMock(side_effect=claim_inbound_batch)
    conv.reclaim_error_batch = AsyncMock(side_effect=reclaim_error_batch)
    conv.finalize_batch_messages = AsyncMock(side_effect=finalize_batch_messages)
    conv.mark_message_skipped = AsyncMock(side_effect=mark_message_skipped)
    conv.insert_bot_outbound = AsyncMock(side_effect=insert_bot_outbound)
    conv.save_canonical_state = AsyncMock(side_effect=save_canonical_state)
    conv.list_recent_turns = AsyncMock(return_value=[])
    conv.merge_message_turn_facts = AsyncMock()
    conv.fetch_first_customer_text = AsyncMock(return_value="Oi, quero um Civic")
    conv.find_bot_message_text_by_provider_id = AsyncMock(return_value=None)
    conv.delete = AsyncMock(side_effect=delete_message)
    conv.delete_messages = AsyncMock(side_effect=lambda ids, *a, **k: [delete_message(i) for i in ids])
    orch.conversations = conv

    orch.customers = MagicMock()
    orch.customers.find_by_phone = AsyncMock(return_value=None)
    orch.customers.upsert_by_phone = AsyncMock(return_value={"id": "cust-1", "name": "Ana"})

    orch.leads = MagicMock()
    orch.leads.list_linked_vehicle_titles = AsyncMock(return_value=[])
    orch.leads.sync_names_for_customer = AsyncMock()
    orch.leads.create_from_state = AsyncMock(return_value=None)
    orch.leads.sync_from_state = AsyncMock()
    orch.leads.mark_qualified_for_handoff = AsyncMock()

    orch.documents = MagicMock()
    orch.documents.attach_orphans_to_lead = AsyncMock()


def _orchestrator(store: LiveStore, *, understand=None, evolution=None) -> Orchestrator:
    async def _understand(text, state):
        return TurnFacts(intent=BusinessIntent.SMALLTALK, language="pt-BR")

    orch = Orchestrator(
        MagicMock(),
        redis_client=None,
        settings=_settings(),
        understand=understand or _understand,
        evolution=evolution or StubEvolutionSender(),
    )
    _wire_repos(orch, store)
    return orch


async def _assume_when(started: asyncio.Event, release: asyncio.Event, store: LiveStore) -> None:
    await started.wait()
    store.assume()
    release.set()


def _assert_suppressed(store: LiveStore, evolution: StubEvolutionSender) -> dict[str, Any]:
    assert evolution.sent == []
    assert evolution.sent_media == []
    assert evolution.sent_locations == []
    result = store.last_batch_result()
    reason = result.get("suppressed_reason") or result.get("reason_code")
    assert reason == "human_active"
    assert result.get("outbound_sent") is False
    assert MSG_ID in store.messages
    assert store.deleted_ids == []
    return result


@pytest.fixture
def patch_quiet():
    async def _immediate(*args, **kwargs):
        return _quiet()

    with patch("sdr.orchestrator.wait_until_quiet", side_effect=_immediate):
        yield


@pytest.mark.asyncio
async def test_b1_assume_before_claim_skips_and_preserves_inbound(patch_quiet) -> None:
    store = LiveStore()
    store.assume()
    evolution = StubEvolutionSender()
    understand = AsyncMock(return_value=TurnFacts(intent=BusinessIntent.SMALLTALK, language="pt-BR"))
    orch = _orchestrator(store, understand=understand, evolution=evolution)

    await orch.process_batch_seed(store.seed(stale_bot_status=LifecycleStatus.BOT_ACTIVE.value))

    understand.assert_not_called()
    _assert_suppressed(store, evolution)
    status = store.messages[MSG_ID]["processingStatus"]
    assert "SKIPPED" in status
    assert "HUMAN_ACTIVE" in status.upper() or "human_active" in status.lower()


@pytest.mark.asyncio
async def test_b2_assume_during_quiet_window_no_llm_no_send() -> None:
    store = LiveStore()
    started = asyncio.Event()
    release = asyncio.Event()
    evolution = StubEvolutionSender()
    understand = AsyncMock(return_value=TurnFacts(intent=BusinessIntent.SMALLTALK))

    async def quiet_then_assume(*args, **kwargs):
        started.set()
        await release.wait()
        return _quiet()

    orch = _orchestrator(store, understand=understand, evolution=evolution)
    with patch("sdr.orchestrator.wait_until_quiet", side_effect=quiet_then_assume):
        await asyncio.gather(
            orch.process_batch_seed(store.seed()),
            _assume_when(started, release, store),
        )

    understand.assert_not_called()
    _assert_suppressed(store, evolution)


@pytest.mark.asyncio
async def test_b3_assume_during_understanding_does_not_send(patch_quiet) -> None:
    store = LiveStore()
    started = asyncio.Event()
    release = asyncio.Event()
    evolution = StubEvolutionSender()

    async def understand(text, state):
        started.set()
        await release.wait()
        return TurnFacts(intent=BusinessIntent.SMALLTALK, language="pt-BR")

    orch = _orchestrator(store, understand=understand, evolution=evolution)
    with patch(
        "sdr.understanding.response_composer.compose_response",
        new=AsyncMock(return_value=["Oi, sou a Júlia"]),
    ):
        await asyncio.gather(
            orch.process_batch_seed(store.seed()),
            _assume_when(started, release, store),
        )

    _assert_suppressed(store, evolution)


@pytest.mark.asyncio
async def test_b4_assume_during_composer_does_not_send(patch_quiet) -> None:
    store = LiveStore()
    started = asyncio.Event()
    release = asyncio.Event()
    evolution = StubEvolutionSender()

    async def compose(state, action_plan, tool_context=None, **kwargs):
        started.set()
        await release.wait()
        return ["Bolha composta após assume"]

    orch = _orchestrator(store, evolution=evolution)
    with patch("sdr.understanding.response_composer.compose_response", side_effect=compose):
        await asyncio.gather(
            orch.process_batch_seed(store.seed()),
            _assume_when(started, release, store),
        )

    _assert_suppressed(store, evolution)


@pytest.mark.asyncio
async def test_b5_assume_immediately_before_send_suppresses(patch_quiet) -> None:
    store = LiveStore()
    started = asyncio.Event()
    release = asyncio.Event()
    evolution = StubEvolutionSender()
    orch = _orchestrator(store, evolution=evolution)

    async def fake_process_turn(**kwargs):
        started.set()
        await release.wait()
        return _message_result()

    with patch("sdr.orchestrator.process_turn", side_effect=fake_process_turn):
        await asyncio.gather(
            orch.process_batch_seed(store.seed()),
            _assume_when(started, release, store),
        )

    _assert_suppressed(store, evolution)
    assert orch.conversations.get_by_id.await_count >= 1


@pytest.mark.asyncio
async def test_b6_send_succeeded_then_assume_keeps_outbound(patch_quiet) -> None:
    store = LiveStore()
    evolution = StubEvolutionSender()
    orch = _orchestrator(store, evolution=evolution)

    original_insert = orch.conversations.insert_bot_outbound

    async def insert_then_assume(**kwargs):
        result = await original_insert(**kwargs)
        if store.bot_status != LifecycleStatus.HUMAN_ACTIVE.value:
            store.assume()
        return result

    orch.conversations.insert_bot_outbound = AsyncMock(side_effect=insert_then_assume)

    async def fake_process_turn(**kwargs):
        return _message_result(["primeira bolha", "segunda bolha"])

    with patch("sdr.orchestrator.process_turn", side_effect=fake_process_turn):
        await orch.process_batch_seed(store.seed())

    assert len(evolution.sent) == 1
    assert evolution.sent[0][1] == "primeira bolha"
    assert len(store.outbound) == 1
    assert store.outbound[0]["text"] == "primeira bolha"
    assert store.deleted_ids == []
    assert MSG_ID in store.messages
    result = store.last_batch_result()
    assert (result.get("suppressed_reason") or result.get("reason_code")) == "human_active"


@pytest.mark.asyncio
async def test_b7_retry_after_human_active_no_send_no_llm(patch_quiet) -> None:
    store = LiveStore()
    store.assume()
    store.messages[MSG_ID]["processingStatus"] = "ERROR"
    store.messages[MSG_ID]["turnFactsJson"] = {
        BATCH_JSON_KEY: {
            "batch_id": "batch-retry",
            "message_ids": [MSG_ID],
            "cutoff": "2026-09-08T18:00:00Z",
            "status": "ERROR",
            "result": {"outbound_sent": False},
        }
    }
    evolution = StubEvolutionSender()
    understand = AsyncMock(return_value=TurnFacts(intent=BusinessIntent.SMALLTALK))
    orch = _orchestrator(store, understand=understand, evolution=evolution)

    seed = store.seed(stale_bot_status=LifecycleStatus.BOT_ACTIVE.value)
    seed["processingStatus"] = "ERROR"
    seed["turnFactsJson"] = store.messages[MSG_ID]["turnFactsJson"]

    await orch.process_batch_seed(seed)

    understand.assert_not_called()
    _assert_suppressed(store, evolution)


@pytest.mark.asyncio
async def test_b8_inbound_rows_remain_when_suppressed(patch_quiet) -> None:
    store = LiveStore()
    store.ingest("msg-in-2", text="ainda quero o Civic")
    store.assume()
    evolution = StubEvolutionSender()
    orch = _orchestrator(store, evolution=evolution)

    await orch.process_batch_seed(store.seed(stale_bot_status=LifecycleStatus.BOT_ACTIVE.value))

    assert "msg-in-1" in store.messages or MSG_ID in store.messages
    assert "msg-in-2" in store.messages
    assert store.deleted_ids == []
    _assert_suppressed(store, evolution)


@pytest.mark.asyncio
async def test_b9_human_active_at_start_skips_understand_and_compose(patch_quiet) -> None:
    store = LiveStore()
    store.assume()
    evolution = StubEvolutionSender()
    understand = AsyncMock(return_value=TurnFacts(intent=BusinessIntent.SMALLTALK))
    compose = AsyncMock(return_value=["não deveria enviar"])
    orch = _orchestrator(store, understand=understand, evolution=evolution)

    with patch("sdr.understanding.response_composer.compose_response", compose):
        await orch.process_batch_seed(store.seed())

    assert understand.call_count == 0
    assert compose.call_count == 0
    _assert_suppressed(store, evolution)


@pytest.mark.asyncio
async def test_b10_records_suppressed_reason_human_active(patch_quiet) -> None:
    store = LiveStore()
    store.assume()
    evolution = StubEvolutionSender()
    orch = _orchestrator(store, evolution=evolution)

    await orch.process_batch_seed(store.seed(stale_bot_status=LifecycleStatus.BOT_ACTIVE.value))

    result = _assert_suppressed(store, evolution)
    assert result.get("suppressed_reason") == "human_active" or result.get("reason_code") == "human_active"
    assert result.get("ownership_revision") == store.ownership_revision


@pytest.mark.asyncio
async def test_b11_assume_during_canonical_save_does_not_restore_outbound(patch_quiet) -> None:
    """CAS: assume between the live check and save must not clobber HUMAN_ACTIVE then send."""
    store = LiveStore()
    evolution = StubEvolutionSender()
    orch = _orchestrator(store, evolution=evolution)
    inner = orch.conversations.save_canonical_state

    async def assume_then_save(cid: str, state: ConversationCanonicalState) -> bool:
        if store.bot_status != LifecycleStatus.HUMAN_ACTIVE.value:
            store.assume()
        return await inner(cid, state)

    orch.conversations.save_canonical_state = AsyncMock(side_effect=assume_then_save)

    async def fake_process_turn(**kwargs):
        return _message_result()

    with patch("sdr.orchestrator.process_turn", side_effect=fake_process_turn):
        await orch.process_batch_seed(store.seed())

    _assert_suppressed(store, evolution)
    assert store.bot_status == LifecycleStatus.HUMAN_ACTIVE.value
    assert store.ownership_revision == 1
