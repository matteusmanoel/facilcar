"""Follow-up cancel + ownership races (Phase 11 Frente C).

Pending automation never outruns HUMAN_ACTIVE or a later customer turn.
Races use asyncio.Event — no sleep.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from sdr.application.followup_cancel import (
    cancel_for_lead_close,
    send_followup_if_allowed,
)
from sdr.application.process_turn import ProcessTurnResult
from sdr.config import Settings
from sdr.debounce import QuietWindowResult
from sdr.domain.followup_cancel import (
    FollowUpCancelReason,
    FollowUpTaskStatus,
    cancel_reason_for_lead_close,
    followup_send_blocked,
    inbound_cancel_reason,
    is_opt_out_signal,
)
from sdr.domain.ownership import resume_ai
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

CONV_ID = "conv-followup-cancel"
PHONE = "5511999000001"
INSTANCE = "facilcar-sdr"
MSG_ID = "msg-in-1"
T0 = datetime(2026, 9, 8, 18, 0, 0)
FOLLOWUP_TEXT = "Ainda está procurando o Civic?"
NEW_REPLY = "Certo, vamos seguir no Civic."


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


@dataclass
class FakeFollowUpTask:
    conversation_id: str
    id: str = field(default_factory=lambda: str(uuid4()))
    status: str = FollowUpTaskStatus.PENDING.value
    cancel_reason: str | None = None
    context_revision: int = 0
    context_key: str | None = None
    text: str = FOLLOWUP_TEXT
    attempt_number: int = 1


class FakeFollowUpStore:
    """Pending/sent rows, idempotent cancel, claim CAS, race hooks."""

    def __init__(self) -> None:
        self.tasks: dict[str, FakeFollowUpTask] = {}
        self._lock = asyncio.Lock()
        self.cancel_calls: list[tuple[str, str]] = []
        self.compose_started = asyncio.Event()
        self.compose_release = asyncio.Event()
        self.compose_release.set()
        self.before_send_started = asyncio.Event()
        self.before_send_release = asyncio.Event()
        self.before_send_release.set()
        self.claim_started = asyncio.Event()
        self.claim_release = asyncio.Event()
        self.claim_release.set()
        self.force_context_changed = False

    def pending(
        self,
        conversation_id: str = CONV_ID,
        *,
        context_key: str | None = "civic",
        context_revision: int = 1,
        text: str = FOLLOWUP_TEXT,
        status: str = FollowUpTaskStatus.PENDING.value,
    ) -> FakeFollowUpTask:
        task = FakeFollowUpTask(
            conversation_id=conversation_id,
            status=status,
            context_key=context_key,
            context_revision=context_revision,
            text=text,
        )
        self.tasks[task.id] = task
        return task

    def sent_row(self, conversation_id: str = CONV_ID) -> FakeFollowUpTask:
        return self.pending(
            conversation_id, status=FollowUpTaskStatus.SENT.value, context_key=None
        )

    def tasks_for(self, conversation_id: str) -> list[FakeFollowUpTask]:
        return [t for t in self.tasks.values() if t.conversation_id == conversation_id]

    def cancellable(self, conversation_id: str = CONV_ID) -> list[FakeFollowUpTask]:
        return [
            t
            for t in self.tasks_for(conversation_id)
            if t.status
            in (FollowUpTaskStatus.PENDING.value, FollowUpTaskStatus.CLAIMED.value)
        ]

    async def cancel_for_conversation(self, conversation_id: str, reason: str) -> int:
        async with self._lock:
            self.cancel_calls.append((conversation_id, str(reason)))
            newly = 0
            for task in self.tasks_for(conversation_id):
                if task.status == FollowUpTaskStatus.SENT.value:
                    continue
                if task.status == FollowUpTaskStatus.CANCELLED.value:
                    continue
                if task.status in (
                    FollowUpTaskStatus.PENDING.value,
                    FollowUpTaskStatus.CLAIMED.value,
                ):
                    task.status = FollowUpTaskStatus.CANCELLED.value
                    task.cancel_reason = str(reason)
                    newly += 1
            return newly

    async def claim(self, task_id: str) -> FakeFollowUpTask | None:
        self.claim_started.set()
        await self.claim_release.wait()
        async with self._lock:
            task = self.tasks.get(task_id)
            if task is None or task.status != FollowUpTaskStatus.PENDING.value:
                return None
            task.status = FollowUpTaskStatus.CLAIMED.value
            return task

    async def get(self, task_id: str) -> FakeFollowUpTask | None:
        return self.tasks.get(task_id)

    async def mark_sent(self, task_id: str) -> bool:
        async with self._lock:
            task = self.tasks.get(task_id)
            if task is None or task.status != FollowUpTaskStatus.CLAIMED.value:
                return False
            task.status = FollowUpTaskStatus.SENT.value
            return True

    async def enqueue(self, conversation_id: str = CONV_ID, **kwargs: Any) -> FakeFollowUpTask:
        """A newer task supersedes still-pending ones for the same conversation."""
        await self.cancel_for_conversation(
            conversation_id, FollowUpCancelReason.SUPERSEDED.value
        )
        return self.pending(conversation_id, **kwargs)

    def context_changed_for_inbound(self, conversation_id: str, text: str) -> bool:
        if self.force_context_changed:
            return True
        folded = (text or "").casefold()
        for task in self.cancellable(conversation_id):
            key = (task.context_key or "").casefold()
            if key and key not in folded:
                return True
        return False


class LiveStore:
    """In-memory conversation + messages; botStatus is the live DB column."""

    def __init__(self, *, bot_status: str = LifecycleStatus.BOT_ACTIVE.value) -> None:
        self.bot_status = bot_status
        self.ownership_revision = 0
        self.assumed_by: str | None = None
        self.assumed_at: datetime | None = None
        self.resumed_by: str | None = None
        self.resumed_at: datetime | None = None
        self.resume_reason: str | None = None
        self.messages: dict[str, dict[str, Any]] = {}
        self.outbound: list[dict[str, Any]] = []
        self.finalizes: list[dict[str, Any]] = []
        self.deleted_ids: list[str] = []
        self.reset_calls: list[str] = []
        self.ingest(MSG_ID, text="Oi, quero um Civic", processing_status="PENDING")

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

    def resume(self, *, actor: str = "user-alice", reason: str = "vendor_returned") -> None:
        state = resume_ai(
            self.canonical_state(),
            actor_user_id=actor,
            reason=reason,
            expected_revision=self.ownership_revision,
        )
        self.bot_status = state.lifecycle.status.value
        self.ownership_revision = state.ownership_revision
        self.resumed_by = state.resumed_by_user_id
        self.resumed_at = T0
        self.resume_reason = state.resume_reason

    def canonical_state(self) -> ConversationCanonicalState:
        status = LifecycleStatus(self.bot_status)
        return ConversationCanonicalState(
            thread_id=CONV_ID,
            customer=CustomerState(phone=PHONE, name="Ana"),
            lifecycle=LifecycleState(status=status),
            ownership_revision=self.ownership_revision,
            assumed_by_user_id=self.assumed_by,
            assumed_at=self.assumed_at.isoformat() if self.assumed_at else None,
            resumed_by_user_id=self.resumed_by,
            resumed_at=self.resumed_at.isoformat() if self.resumed_at else None,
            resume_reason=self.resume_reason,
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
            "resumedByUserId": self.resumed_by,
            "resumedAt": self.resumed_at,
            "resumeReason": self.resume_reason,
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
    texts = outbound_texts if outbound_texts is not None else [NEW_REPLY]
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

    async def reset_conversation_memory(conversation_id: str, *, phone: str):
        store.reset_calls.append(conversation_id)
        store.bot_status = LifecycleStatus.BOT_ACTIVE.value
        store.ownership_revision = 0
        store.assumed_by = None
        store.assumed_at = None
        return ConversationCanonicalState(
            thread_id=conversation_id,
            customer=CustomerState(phone=phone),
        )

    conv.get_by_id = AsyncMock(side_effect=get_by_id)
    conv.load_canonical_state = AsyncMock(side_effect=load_canonical_state)
    conv.list_pending_inbound_up_to = AsyncMock(side_effect=list_pending_inbound_up_to)
    conv.claim_inbound_batch = AsyncMock(side_effect=claim_inbound_batch)
    conv.reclaim_error_batch = AsyncMock(side_effect=reclaim_error_batch)
    conv.finalize_batch_messages = AsyncMock(side_effect=finalize_batch_messages)
    conv.mark_message_skipped = AsyncMock(side_effect=mark_message_skipped)
    conv.insert_bot_outbound = AsyncMock(side_effect=insert_bot_outbound)
    conv.save_canonical_state = AsyncMock(side_effect=save_canonical_state)
    conv.reset_conversation_memory = AsyncMock(side_effect=reset_conversation_memory)
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


def _orchestrator(
    live: LiveStore,
    followups: FakeFollowUpStore,
    *,
    understand=None,
    evolution=None,
) -> Orchestrator:
    async def _understand(text, state):
        return TurnFacts(intent=BusinessIntent.SMALLTALK, language="pt-BR")

    orch = Orchestrator(
        MagicMock(),
        redis_client=None,
        settings=_settings(),
        understand=understand or _understand,
        evolution=evolution or StubEvolutionSender(),
        followup_canceller=followups,
    )
    _wire_repos(orch, live)
    return orch


def _followup_texts(evolution: StubEvolutionSender) -> list[str]:
    return [payload[1] for payload in evolution.sent if payload[1] == FOLLOWUP_TEXT]


async def _fire(
    followups: FakeFollowUpStore,
    live: LiveStore,
    evolution: StubEvolutionSender,
    task: FakeFollowUpTask,
    *,
    compose_hook=None,
    before_send_hook=None,
) -> bool:
    return await send_followup_if_allowed(
        store=followups,
        conversations=_ConversationsAdapter(live),
        evolution=evolution,
        task_id=task.id,
        phone=PHONE,
        instance=INSTANCE,
        text=task.text,
        compose_hook=compose_hook,
        before_send_hook=before_send_hook,
    )


class _ConversationsAdapter:
    def __init__(self, live: LiveStore) -> None:
        self._live = live

    async def get_by_id(self, _cid: str):
        return self._live.conv_row()


@pytest.fixture
def patch_quiet():
    async def _immediate(*args, **kwargs):
        return _quiet()

    with patch("sdr.orchestrator.wait_until_quiet", side_effect=_immediate):
        yield


def test_opt_out_and_lead_close_policy() -> None:
    assert is_opt_out_signal("Não quero mais contato")
    assert is_opt_out_signal("oi", TurnFacts(facts={"opt_out": True}))
    assert not is_opt_out_signal("quero um Civic")
    assert inbound_cancel_reason("oi") is FollowUpCancelReason.CUSTOMER_REPLIED
    assert inbound_cancel_reason("pare de me enviar mensagens") is FollowUpCancelReason.OPT_OUT
    assert cancel_reason_for_lead_close("WON") is FollowUpCancelReason.LEAD_WON
    assert cancel_reason_for_lead_close("QUALIFIED") is None
    assert followup_send_blocked(
        task_status=FollowUpTaskStatus.CLAIMED,
        bot_status=LifecycleStatus.HUMAN_ACTIVE.value,
    )
    assert followup_send_blocked(
        task_status=FollowUpTaskStatus.CANCELLED,
        bot_status=LifecycleStatus.BOT_ACTIVE.value,
    )
    assert not followup_send_blocked(
        task_status=FollowUpTaskStatus.CLAIMED,
        bot_status=LifecycleStatus.BOT_ACTIVE.value,
    )


@pytest.mark.asyncio
async def test_c1_reply_before_fire_cancels_and_processes_inbound(patch_quiet) -> None:
    live = LiveStore()
    followups = FakeFollowUpStore()
    task = followups.pending()
    evolution = StubEvolutionSender()
    orch = _orchestrator(live, followups, evolution=evolution)

    with patch(
        "sdr.orchestrator.process_turn",
        new=AsyncMock(return_value=_message_result([NEW_REPLY])),
    ) as process:
        result = await orch.process_batch_seed(live.seed())

    assert followups.cancel_calls
    assert followups.cancel_calls[0][1] == FollowUpCancelReason.CUSTOMER_REPLIED.value
    assert task.status == FollowUpTaskStatus.CANCELLED.value
    assert task.cancel_reason == FollowUpCancelReason.CUSTOMER_REPLIED.value
    process.assert_awaited()
    assert result is not None
    assert NEW_REPLY in (result.outbound_texts or [])
    fired = await _fire(followups, live, evolution, task)
    assert fired is False
    assert _followup_texts(evolution) == []
    assert MSG_ID in live.messages
    assert live.deleted_ids == []


@pytest.mark.asyncio
async def test_c2_reply_during_compose_cancel_wins_no_followup_send(patch_quiet) -> None:
    live = LiveStore()
    followups = FakeFollowUpStore()
    task = followups.pending()
    evolution = StubEvolutionSender()
    orch = _orchestrator(live, followups, evolution=evolution)
    followups.compose_release.clear()

    async def compose_hook():
        followups.compose_started.set()
        await followups.compose_release.wait()

    async def inbound_reply():
        await followups.compose_started.wait()
        with patch(
            "sdr.orchestrator.process_turn",
            new=AsyncMock(return_value=_message_result([NEW_REPLY])),
        ):
            await orch.process_batch_seed(live.seed())
        followups.compose_release.set()

    sent, _ = await asyncio.gather(
        _fire(followups, live, evolution, task, compose_hook=compose_hook),
        inbound_reply(),
    )

    assert sent is False
    assert task.status == FollowUpTaskStatus.CANCELLED.value
    assert _followup_texts(evolution) == []
    assert MSG_ID in live.messages


@pytest.mark.asyncio
async def test_c3_human_assume_cancels_zero_llm_zero_outbound(patch_quiet) -> None:
    live = LiveStore()
    followups = FakeFollowUpStore()
    task = followups.pending()
    live.assume()
    evolution = StubEvolutionSender()
    understand = AsyncMock(
        return_value=TurnFacts(intent=BusinessIntent.SMALLTALK, language="pt-BR")
    )
    orch = _orchestrator(live, followups, understand=understand, evolution=evolution)

    await orch.process_batch_seed(live.seed(stale_bot_status=LifecycleStatus.BOT_ACTIVE.value))

    understand.assert_not_called()
    assert evolution.sent == []
    assert task.status == FollowUpTaskStatus.CANCELLED.value
    assert task.cancel_reason == FollowUpCancelReason.HUMAN_ASSUMED.value
    assert MSG_ID in live.messages
    assert live.deleted_ids == []


@pytest.mark.asyncio
async def test_c4_human_assume_immediately_before_send_aborts(patch_quiet) -> None:
    live = LiveStore()
    followups = FakeFollowUpStore()
    task = followups.pending()
    evolution = StubEvolutionSender()
    followups.before_send_release.clear()

    async def before_send_hook():
        followups.before_send_started.set()
        await followups.before_send_release.wait()

    async def assume_then_release():
        await followups.before_send_started.wait()
        live.assume()
        followups.before_send_release.set()

    sent, _ = await asyncio.gather(
        _fire(followups, live, evolution, task, before_send_hook=before_send_hook),
        assume_then_release(),
    )

    assert sent is False
    assert evolution.sent == []
    assert task.status == FollowUpTaskStatus.CANCELLED.value
    assert task.cancel_reason == FollowUpCancelReason.HUMAN_ASSUMED.value


@pytest.mark.asyncio
async def test_c5_opt_out_cancels_and_blocks_commercial_outbound(patch_quiet) -> None:
    live = LiveStore()
    live.messages[MSG_ID]["text"] = "Não quero mais contato"
    followups = FakeFollowUpStore()
    task = followups.pending()
    evolution = StubEvolutionSender()
    understand = AsyncMock(
        return_value=TurnFacts(intent=BusinessIntent.SMALLTALK, language="pt-BR")
    )
    orch = _orchestrator(live, followups, understand=understand, evolution=evolution)

    result = await orch.process_batch_seed(live.seed())

    understand.assert_not_called()
    assert evolution.sent == []
    assert result is not None
    assert result.action_plan.reason_code == "opt_out"
    assert result.outbound_texts == []
    assert task.status == FollowUpTaskStatus.CANCELLED.value
    assert task.cancel_reason == FollowUpCancelReason.OPT_OUT.value
    assert MSG_ID in live.messages
    assert live.last_batch_result().get("reason_code") == "opt_out"


@pytest.mark.asyncio
async def test_c6_deletar_cancels_with_conversation_reset(patch_quiet) -> None:
    live = LiveStore()
    live.messages[MSG_ID]["text"] = "/deletar"
    followups = FakeFollowUpStore()
    task = followups.pending()
    evolution = StubEvolutionSender()
    orch = _orchestrator(live, followups, evolution=evolution)

    result = await orch.process_batch_seed(live.seed())

    assert live.reset_calls == [CONV_ID]
    assert task.status == FollowUpTaskStatus.CANCELLED.value
    assert task.cancel_reason == FollowUpCancelReason.CONVERSATION_RESET.value
    assert result is not None
    assert result.action_plan.reason_code == "command_deletar"
    assert _followup_texts(evolution) == []
    fired = await _fire(followups, live, evolution, task)
    assert fired is False


@pytest.mark.asyncio
async def test_c7_won_lost_spam_cancel_qualified_does_not() -> None:
    followups = FakeFollowUpStore()
    won = followups.pending()
    n = await cancel_for_lead_close(followups, CONV_ID, "WON")
    assert n == 1
    assert won.status == FollowUpTaskStatus.CANCELLED.value
    assert won.cancel_reason == FollowUpCancelReason.LEAD_WON.value

    lost = followups.pending()
    assert await cancel_for_lead_close(followups, CONV_ID, "LOST") == 1
    assert lost.cancel_reason == FollowUpCancelReason.LEAD_LOST.value

    spam = followups.pending()
    assert await cancel_for_lead_close(followups, CONV_ID, "SPAM") == 1
    assert spam.cancel_reason == FollowUpCancelReason.SPAM.value

    still = followups.pending()
    assert await cancel_for_lead_close(followups, CONV_ID, "QUALIFIED") == 0
    assert await cancel_for_lead_close(followups, CONV_ID, "CONTACTED") == 0
    assert still.status == FollowUpTaskStatus.PENDING.value


@pytest.mark.asyncio
async def test_c8_resume_does_not_restore_cancelled_tasks() -> None:
    live = LiveStore()
    live.assume()
    followups = FakeFollowUpStore()
    task = followups.pending()
    await followups.cancel_for_conversation(
        CONV_ID, FollowUpCancelReason.HUMAN_ASSUMED.value
    )
    live.resume()
    assert live.bot_status == LifecycleStatus.AI_RESUMED.value
    assert task.status == FollowUpTaskStatus.CANCELLED.value

    evolution = StubEvolutionSender()
    fired = await _fire(followups, live, evolution, task)
    assert fired is False
    assert task.status == FollowUpTaskStatus.CANCELLED.value
    assert task.status != FollowUpTaskStatus.PENDING.value
    assert evolution.sent == []


@pytest.mark.asyncio
async def test_c9_context_change_supersedes(patch_quiet) -> None:
    live = LiveStore()
    live.messages[MSG_ID]["text"] = "Na verdade quero uma Strada"
    followups = FakeFollowUpStore()
    civic = followups.pending(context_key="civic")
    evolution = StubEvolutionSender()
    orch = _orchestrator(live, followups, evolution=evolution)

    with patch(
        "sdr.orchestrator.process_turn",
        new=AsyncMock(return_value=_message_result(["Vou buscar a Strada."])),
    ):
        await orch.process_batch_seed(live.seed())

    assert civic.status == FollowUpTaskStatus.CANCELLED.value
    assert civic.cancel_reason == FollowUpCancelReason.CONTEXT_CHANGED.value

    replacement = await followups.enqueue(CONV_ID, context_key="strada")
    assert civic.cancel_reason in {
        FollowUpCancelReason.CONTEXT_CHANGED.value,
        FollowUpCancelReason.SUPERSEDED.value,
    }
    assert replacement.status == FollowUpTaskStatus.PENDING.value
    older = followups.pending(context_key="old")
    newer = await followups.enqueue(CONV_ID, context_key="new")
    assert older.status == FollowUpTaskStatus.CANCELLED.value
    assert older.cancel_reason == FollowUpCancelReason.SUPERSEDED.value
    assert newer.status == FollowUpTaskStatus.PENDING.value


@pytest.mark.asyncio
async def test_c10_duplicate_cancel_idempotent_sent_stays_sent() -> None:
    followups = FakeFollowUpStore()
    pending = followups.pending()
    sent = followups.sent_row()

    first = await followups.cancel_for_conversation(
        CONV_ID, FollowUpCancelReason.MANUAL_CANCEL.value
    )
    second = await followups.cancel_for_conversation(
        CONV_ID, FollowUpCancelReason.MANUAL_CANCEL.value
    )
    assert first == 1
    assert second == 0
    assert pending.status == FollowUpTaskStatus.CANCELLED.value
    assert pending.cancel_reason == FollowUpCancelReason.MANUAL_CANCEL.value
    assert sent.status == FollowUpTaskStatus.SENT.value
    assert sent.status != FollowUpTaskStatus.PENDING.value


@pytest.mark.asyncio
async def test_c11_cancel_vs_claim_cancel_wins() -> None:
    followups = FakeFollowUpStore()
    task = followups.pending()
    followups.claim_release.clear()

    async def claim():
        return await followups.claim(task.id)

    async def cancel_during_claim():
        await followups.claim_started.wait()
        n = await followups.cancel_for_conversation(
            CONV_ID, FollowUpCancelReason.CUSTOMER_REPLIED.value
        )
        followups.claim_release.set()
        return n

    claimed, cancelled = await asyncio.gather(claim(), cancel_during_claim())
    assert cancelled == 1
    assert claimed is None
    assert task.status == FollowUpTaskStatus.CANCELLED.value

    live = LiveStore()
    evolution = StubEvolutionSender()
    assert await _fire(followups, live, evolution, task) is False
    assert evolution.sent == []


@pytest.mark.asyncio
async def test_c12_inbound_preserved_when_cancelling(patch_quiet) -> None:
    live = LiveStore()
    live.ingest("msg-in-2", text="ainda quero o Civic")
    followups = FakeFollowUpStore()
    followups.pending()
    evolution = StubEvolutionSender()
    orch = _orchestrator(live, followups, evolution=evolution)

    with patch(
        "sdr.orchestrator.process_turn",
        new=AsyncMock(return_value=_message_result([NEW_REPLY])),
    ):
        await orch.process_batch_seed(live.seed())

    assert MSG_ID in live.messages
    assert "msg-in-2" in live.messages
    assert live.deleted_ids == []
    assert live.messages[MSG_ID]["text"] == "Oi, quero um Civic"
