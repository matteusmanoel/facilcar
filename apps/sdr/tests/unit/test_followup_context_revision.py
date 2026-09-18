"""Follow-up CAS uses live Conversation.contextRevision — never sentinel 0."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from sdr.application.followup_runtime import FollowUpRuntime
from sdr.application.followup_scheduler import (
    CANCEL_REVISION_UNAVAILABLE,
    FollowUpScheduler,
    FollowUpSnapshot,
    load_followup_snapshot_from_conversation,
)
from sdr.domain.clock import TZ_BRT, set_clock
from sdr.domain.conversation_revision import bump_context_revision
from sdr.domain.types import (
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    LifecycleState,
    LifecycleStatus,
)
from sdr.infrastructure.followup_repository import (
    InvalidFollowUpContextRevision,
    InMemoryFollowUpRepository,
    STATUS_CANCELLED,
    STATUS_PENDING,
    STATUS_SENT,
)
from sdr.replay.runner import run_scenario_detailed

MONDAY = datetime(2026, 9, 7, 10, 0, tzinfo=TZ_BRT)


def setup_function() -> None:
    set_clock(MONDAY.isoformat())


def teardown_function() -> None:
    set_clock(None)


def _state(**kwargs) -> ConversationCanonicalState:
    state = ConversationCanonicalState(
        thread_id="t-rev",
        customer=CustomerState(phone="5511999000100"),
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts={"desired_model": "Strada"},
        context_revision=0,
        ownership_revision=0,
    )
    for key, value in kwargs.items():
        setattr(state, key, value)
    return state


def _make_due(runtime: FollowUpRuntime) -> None:
    rows = runtime.repo.all_rows()
    assert rows
    due = rows[-1].scheduled_at
    set_clock(due.isoformat() if hasattr(due, "isoformat") else str(due))


@pytest.mark.asyncio
async def test_task_captures_nonzero_live_revision() -> None:
    runtime = FollowUpRuntime(conversation_id="t-rev")
    state = _state()
    bump_context_revision(state)
    assert state.context_revision == 1
    runtime.apply_policy(state, "Pode me chamar amanhã às 14h.")
    await runtime.sync_task(state, "Pode me chamar amanhã às 14h.")
    rows = runtime.repo.all_rows()
    assert len(rows) == 1
    assert rows[0].context_revision == 1
    assert rows[0].ownership_revision == 0
    assert runtime.evidence.context_revision_nonzero is True
    assert runtime.evidence.context_revision == 1


@pytest.mark.asyncio
async def test_new_inbound_increments_and_stale_task_skips_composer() -> None:
    runtime = FollowUpRuntime(conversation_id="t-rev")
    state = _state()
    bump_context_revision(state)
    runtime.apply_policy(state, "Pode me chamar amanhã às 14h.")
    await runtime.sync_task(state, "Pode me chamar amanhã às 14h.")
    task_rev = runtime.repo.all_rows()[0].context_revision
    bump_context_revision(state)
    runtime.context_revision = state.context_revision
    runtime.last_state = state
    assert state.context_revision == task_rev + 1
    _make_due(runtime)
    await runtime.tick()
    assert runtime.sends == []
    assert runtime.composer_calls == 0
    cancelled = [t for t in runtime.repo.all_rows() if t.status == STATUS_CANCELLED]
    assert cancelled
    assert cancelled[0].cancel_reason == "CONTEXT_CHANGED"


@pytest.mark.asyncio
async def test_revision_change_after_compose_blocks_send() -> None:
    runtime = FollowUpRuntime(conversation_id="t-rev")
    state = _state()
    bump_context_revision(state)
    runtime.apply_policy(state, "Pode me chamar amanhã às 14h.")
    await runtime.sync_task(state, "Pode me chamar amanhã às 14h.")
    original = runtime.compose_task

    async def compose_then_bump(task, snapshot):
        text = await original(task, snapshot)
        runtime.context_revision = int(runtime.context_revision) + 1
        return text

    runtime.compose_task = compose_then_bump  # type: ignore[method-assign]
    _make_due(runtime)
    await runtime.tick()
    assert runtime.composer_calls == 1
    assert runtime.sends == []


@pytest.mark.asyncio
async def test_ownership_change_wins_race() -> None:
    runtime = FollowUpRuntime(conversation_id="t-rev")
    state = _state()
    bump_context_revision(state)
    runtime.apply_policy(state, "Pode me chamar amanhã às 14h.")
    await runtime.sync_task(state, "Pode me chamar amanhã às 14h.")
    state.lifecycle = LifecycleState(status=LifecycleStatus.HUMAN_ACTIVE)
    state.ownership_revision = 3
    runtime.on_admin("assume", state)
    _make_due(runtime)
    await runtime.tick()
    assert runtime.sends == []
    assert runtime.composer_calls == 0


@pytest.mark.asyncio
async def test_new_task_after_reply_uses_new_revision() -> None:
    runtime = FollowUpRuntime(conversation_id="t-rev")
    state = _state()
    bump_context_revision(state)
    runtime.apply_policy(state, "Pode me chamar amanhã às 14h.")
    await runtime.sync_task(state, "Pode me chamar amanhã às 14h.")
    first = runtime.repo.all_rows()[0].context_revision
    await runtime.cancel("CUSTOMER_REPLIED")
    bump_context_revision(state)
    runtime.apply_policy(state, "Pode me chamar amanhã às 16h.")
    await runtime.sync_task(state, "Pode me chamar amanhã às 16h.")
    pending = [t for t in runtime.repo.all_rows() if t.status == STATUS_PENDING]
    assert pending
    assert pending[-1].context_revision == first + 1


@pytest.mark.asyncio
async def test_restart_preserves_captured_revision() -> None:
    repo = InMemoryFollowUpRepository()
    first = FollowUpRuntime(conversation_id="t-rev", repo=repo)
    state = _state()
    bump_context_revision(state)
    first.apply_policy(state, "Pode me chamar amanhã às 14h.")
    await first.sync_task(state, "Pode me chamar amanhã às 14h.")
    captured = repo.all_rows()[0].context_revision
    restarted = FollowUpRuntime(conversation_id="t-rev", repo=repo)
    restarted.context_revision = captured
    restarted.ownership_revision = 0
    restarted.phone = first.phone
    _make_due(restarted)
    await restarted.tick()
    assert repo.all_rows()[0].context_revision == captured
    assert restarted.sends


@pytest.mark.asyncio
async def test_two_workers_same_snapshot_send_once() -> None:
    runtime = FollowUpRuntime(conversation_id="t-rev")
    state = _state()
    bump_context_revision(state)
    runtime.apply_policy(state, "Pode me chamar amanhã às 14h.")
    await runtime.sync_task(state, "Pode me chamar amanhã às 14h.")
    _make_due(runtime)
    await runtime.tick(workers=["w1", "w2"])
    assert len(runtime.sends) == 1
    sent = [t for t in runtime.repo.all_rows() if t.status == STATUS_SENT]
    assert len(sent) == 1


@pytest.mark.asyncio
async def test_missing_column_fails_safe_no_send() -> None:
    repo = InMemoryFollowUpRepository()
    clock = lambda: MONDAY  # noqa: E731

    class _Conversations:
        async def get_by_id(self, _cid: str):
            raise RuntimeError('column "contextRevision" does not exist SQLSTATE 42703')

    await repo.create_or_supersede(
        conversation_id="t-rev",
        reason="CUSTOMER_WILL_RETURN",
        scheduled_at=MONDAY - timedelta(minutes=1),
        idempotency_key="k-missing",
        context_revision=1,
        now=MONDAY,
    )

    async def load(cid: str) -> FollowUpSnapshot:
        return await load_followup_snapshot_from_conversation(_Conversations(), cid)

    composed = []

    async def compose(task, snapshot):
        composed.append(1)
        return "hi"

    sent = []

    async def sender(task, text):
        sent.append(text)

    sched = FollowUpScheduler(
        repo,
        worker_id="w1",
        now_brt=clock,
        composer=compose,
        sender=sender,
        load_snapshot=load,
    )
    results = await sched.tick()
    assert results[0].sent is False
    assert results[0].reason == CANCEL_REVISION_UNAVAILABLE
    assert composed == []
    assert sent == []
    assert repo.all_rows()[0].status == STATUS_PENDING


@pytest.mark.asyncio
async def test_create_rejects_zero_revision() -> None:
    repo = InMemoryFollowUpRepository()
    with pytest.raises(InvalidFollowUpContextRevision):
        await repo.create_or_supersede(
            conversation_id="t-rev",
            reason="x",
            scheduled_at=MONDAY,
            idempotency_key="zero",
            context_revision=0,
            now=MONDAY,
        )


@pytest.mark.asyncio
async def test_loader_without_column_key_is_unavailable() -> None:
    class _Row(dict):
        def keys(self):
            return ["id", "botStatus", "ownershipRevision"]

    class _Conversations:
        async def get_by_id(self, _cid: str):
            return _Row(id="c1", botStatus="BOT_ACTIVE", ownershipRevision=0)

    snap = await load_followup_snapshot_from_conversation(_Conversations(), "c1")
    assert snap.revision_loaded is False
    assert snap.context_revision is None


@pytest.mark.asyncio
async def test_zero_revision_column_is_unavailable() -> None:
    class _Row(dict):
        def keys(self):
            return ["id", "botStatus", "ownershipRevision", "contextRevision"]

    class _Conversations:
        async def get_by_id(self, _cid: str):
            return _Row(
                id="c1",
                botStatus="BOT_ACTIVE",
                ownershipRevision=0,
                contextRevision=0,
            )

    snap = await load_followup_snapshot_from_conversation(_Conversations(), "c1")
    assert snap.revision_loaded is False
    assert snap.context_revision is None


@pytest.mark.asyncio
async def test_missing_loader_fails_safe_no_send() -> None:
    repo = InMemoryFollowUpRepository()
    clock = lambda: MONDAY  # noqa: E731
    await repo.create_or_supersede(
        conversation_id="t-rev",
        reason="CUSTOMER_WILL_RETURN",
        scheduled_at=MONDAY - timedelta(minutes=1),
        idempotency_key="k-noloader",
        context_revision=1,
        now=MONDAY,
    )
    composed: list[int] = []

    async def compose(task, snapshot):
        composed.append(1)
        return "hi"

    sent: list[str] = []

    async def sender(task, text):
        sent.append(text)

    sched = FollowUpScheduler(
        repo,
        worker_id="w1",
        now_brt=clock,
        composer=compose,
        sender=sender,
    )
    results = await sched.tick()
    assert results[0].sent is False
    assert results[0].reason == CANCEL_REVISION_UNAVAILABLE
    assert composed == []
    assert sent == []


@pytest.mark.asyncio
async def test_replay_uses_worker_revision_semantics() -> None:
    from pathlib import Path
    import json

    payload = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "golden"
            / "phase11"
            / "g1_documents_tomorrow_14h.json"
        ).read_text(encoding="utf-8")
    )
    run = await run_scenario_detailed(payload)
    assert run.ok, "\n".join(run.errors)
    evidence = run.followup_evidence or {}
    assert evidence.get("context_revision_loaded") is True
    assert evidence.get("context_revision_nonzero") is True
    assert evidence.get("context_revision_checked_before_compose") is True
    assert evidence.get("context_revision_checked_before_send") is True
    revs = [int(t.get("contextRevision") or 0) for t in run.followup_tasks]
    assert revs
    assert min(revs) >= 1
    assert int(evidence.get("context_revision") or 0) >= 1
