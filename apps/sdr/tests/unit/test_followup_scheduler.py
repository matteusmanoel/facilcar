"""Phase 11 Frente B — durable FollowUpTask claim/CAS scheduler.

No sleep. Clock is injectable. In-memory store simulates SKIP LOCKED / CAS.
No live Postgres required.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from sdr.application.followup_scheduler import (
    CANCEL_CAS_MISS,
    DEFAULT_FOLLOWUP_PLACEHOLDER,
    FollowUpScheduler,
    FollowUpSendConfirmedError,
    FollowUpSnapshot,
)
from sdr.application.outbound_guard import (
    cancel_pending_automation,
    set_cancel_pending_automation,
    set_followup_repository,
)
from sdr.domain.clock import TZ_BRT
from sdr.domain.types import LifecycleStatus
from sdr.infrastructure.followup_repository import (
    CANCEL_REASON_HUMAN_ASSUMED,
    STATUS_CANCELLED,
    STATUS_CLAIMED,
    STATUS_PENDING,
    STATUS_SENT,
    InMemoryFollowUpRepository,
    sanitize_followup_error,
)

APPS = Path(__file__).resolve().parents[3]
SCHEMA_PATH = APPS / "web" / "prisma" / "schema.prisma"
MIGRATION_PATH = (
    APPS / "web" / "prisma" / "migrations" / "20260908200000_sdr_follow_up_task" / "migration.sql"
)
CONTEXT_REVISION_MIGRATION = (
    APPS
    / "web"
    / "prisma"
    / "migrations"
    / "20260908220000_sdr_conversation_context_revision"
    / "migration.sql"
)

MONDAY_OPEN = datetime(2026, 9, 7, 10, 0, tzinfo=TZ_BRT)
SUNDAY_CLOSED = datetime(2026, 9, 6, 10, 0, tzinfo=TZ_BRT)
FRIDAY_AFTERNOON = datetime(2026, 9, 4, 17, 0, tzinfo=TZ_BRT)


class _Clock:
    def __init__(self, dt: datetime) -> None:
        self.dt = dt

    def __call__(self) -> datetime:
        return self.dt


def _snap(
    conversation_id: str = "conv-1",
    *,
    ownership_revision: int = 0,
    context_revision: int = 1,
    bot_status: str = LifecycleStatus.BOT_ACTIVE.value,
    last_inbound_at: datetime | None = None,
    opt_out: bool = False,
    closed: bool = False,
    commercial_ok: bool = True,
    revision_loaded: bool = True,
) -> FollowUpSnapshot:
    return FollowUpSnapshot(
        conversation_id=conversation_id,
        bot_status=bot_status,
        ownership_revision=ownership_revision,
        context_revision=context_revision,
        last_inbound_at=last_inbound_at,
        opt_out=opt_out,
        closed=closed,
        commercial_ok=commercial_ok,
        revision_loaded=revision_loaded,
    )


async def _seed(
    repo: InMemoryFollowUpRepository,
    clock: _Clock,
    *,
    conversation_id: str = "conv-1",
    key: str = "fu-1",
    scheduled_at: datetime | None = None,
    context_revision: int = 1,
    ownership_revision: int = 0,
    maximum_attempts: int = 1,
    reason: str = "callback",
):
    return await repo.create_or_supersede(
        conversation_id=conversation_id,
        reason=reason,
        scheduled_at=scheduled_at or (clock.dt - timedelta(minutes=5)),
        idempotency_key=key,
        original_temporal_text="depois das 10h",
        consent_source="customer_text",
        consent_level="explicit",
        context_revision=context_revision,
        ownership_revision=ownership_revision,
        maximum_attempts=maximum_attempts,
        now=clock.dt,
    )


def _scheduler(
    repo: InMemoryFollowUpRepository,
    clock: _Clock,
    *,
    sender=None,
    composer=None,
    snapshot: FollowUpSnapshot | None = None,
    snapshots: dict[str, FollowUpSnapshot] | None = None,
    worker_id: str = "w1",
    claim_ttl: timedelta | None = None,
):
    store = snapshots if snapshots is not None else {}

    async def load(conversation_id: str) -> FollowUpSnapshot | None:
        if conversation_id in store:
            return store[conversation_id]
        return snapshot or _snap(conversation_id)

    kwargs: dict = {
        "worker_id": worker_id,
        "now_brt": clock,
        "load_snapshot": load,
    }
    if sender is not None:
        kwargs["sender"] = sender
    if composer is not None:
        kwargs["composer"] = composer
    if claim_ttl is not None:
        kwargs["claim_ttl"] = claim_ttl
    return FollowUpScheduler(repo, **kwargs)


@pytest.fixture(autouse=True)
def _reset_outbound_guard_hooks():
    set_cancel_pending_automation(None)
    set_followup_repository(None)
    yield
    set_cancel_pending_automation(None)
    set_followup_repository(None)


def test_prisma_schema_parses_follow_up_task() -> None:
    """Tiny Prisma validation: schema text parses. Does not migrate deploy."""
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    assert "model FollowUpTask" in schema
    assert "enum FollowUpTaskStatus" in schema
    for field in (
        "conversationId",
        "leadId",
        "reason",
        "status",
        "scheduledAt",
        "originalTemporalText",
        "consentSource",
        "consentLevel",
        "attemptNumber",
        "maximumAttempts",
        "contextRevision",
        "ownershipRevision",
        "idempotencyKey",
        "claimedAt",
        "claimedBy",
        "sentAt",
        "cancelledAt",
        "cancelReason",
        "failedAt",
        "lastErrorSanitized",
        "createdAt",
        "updatedAt",
    ):
        assert field in schema
    assert "waitState" in schema
    assert "contextRevision" in schema
    assert re.search(r"botStatus\s+ConversationBotStatus", schema)
    assert "canonicalStateJson" in schema
    assert MIGRATION_PATH.is_file()
    assert CONTEXT_REVISION_MIGRATION.is_file()
    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    assert '"FollowUpTask"' in sql
    context_sql = CONTEXT_REVISION_MIGRATION.read_text(encoding="utf-8")
    assert '"Conversation"' in context_sql
    assert '"contextRevision"' in context_sql
    assert 'ADD COLUMN IF NOT EXISTS "waitState"' in sql
    # Block shape: model parses as a closed Prisma model (no live migrate deploy).
    match = re.search(r"model FollowUpTask \{.*?\n\}", schema, re.S)
    assert match is not None
    assert "@@index([status, scheduledAt])" in match.group(0)
    assert "@unique" in match.group(0)


@pytest.mark.asyncio
async def test_b1_two_workers_one_claim() -> None:
    clock = _Clock(MONDAY_OPEN)
    repo = InMemoryFollowUpRepository()
    await _seed(repo, clock)
    first, second = await asyncio.gather(
        repo.claim_due(clock.dt, "w1"),
        repo.claim_due(clock.dt, "w2"),
    )
    claimed = first + second
    assert len(claimed) == 1
    assert claimed[0].status == STATUS_CLAIMED
    winners = {claimed[0].claimed_by}
    assert winners <= {"w1", "w2"}
    stored = await repo.get_by_id(claimed[0].id)
    assert stored is not None
    assert stored.claimed_by == claimed[0].claimed_by


@pytest.mark.asyncio
async def test_b2_expired_claim_reclaimed() -> None:
    clock = _Clock(MONDAY_OPEN)
    repo = InMemoryFollowUpRepository()
    task = await _seed(repo, clock)
    claimed = await repo.claim_due(clock.dt, "w1")
    assert len(claimed) == 1
    internal = repo._rows[task.id]
    internal.claimed_at = clock.dt - timedelta(minutes=10)
    internal.status = STATUS_CLAIMED
    internal.claimed_by = "w1"
    again = await repo.claim_due(clock.dt, "w2", claim_ttl=timedelta(minutes=5))
    assert len(again) == 1
    assert again[0].claimed_by == "w2"
    assert again[0].id == task.id


@pytest.mark.asyncio
async def test_b3_retry_after_failed_before_send() -> None:
    clock = _Clock(MONDAY_OPEN)
    repo = InMemoryFollowUpRepository()
    await _seed(repo, clock)
    attempts = {"n": 0}

    async def sender(task, text):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("provider timeout before send")
        return None

    sched = _scheduler(repo, clock, sender=sender, snapshot=_snap())
    first = await sched.tick()
    assert first[0].sent is False
    row = repo.all_rows()[0]
    assert row.sent_at is None
    assert row.status == STATUS_PENDING
    second = await sched.tick()
    assert second[0].sent is True
    row = repo.all_rows()[0]
    assert row.status == STATUS_SENT
    assert row.sent_at is not None
    assert attempts["n"] == 2


@pytest.mark.asyncio
async def test_b4_send_confirmed() -> None:
    clock = _Clock(MONDAY_OPEN)
    repo = InMemoryFollowUpRepository()
    await _seed(repo, clock)
    sent: list[str] = []

    async def sender(task, text):
        sent.append(text)

    sched = _scheduler(repo, clock, sender=sender, snapshot=_snap())
    results = await sched.tick()
    assert results[0].sent is True
    row = repo.all_rows()[0]
    assert row.status == STATUS_SENT
    assert row.sent_at is not None
    assert row.attempt_number == 1
    assert row.status != STATUS_PENDING
    assert sent == [DEFAULT_FOLLOWUP_PLACEHOLDER]


@pytest.mark.asyncio
async def test_b5_fail_before_send_retry_allowed_not_sent() -> None:
    clock = _Clock(MONDAY_OPEN)
    repo = InMemoryFollowUpRepository()
    await _seed(repo, clock)

    async def sender(task, text):
        raise RuntimeError("cpf=52998224725 token=abc network")

    sched = _scheduler(repo, clock, sender=sender, snapshot=_snap())
    results = await sched.tick()
    assert results[0].sent is False
    row = repo.all_rows()[0]
    assert row.sent_at is None
    assert row.status == STATUS_PENDING
    assert row.attempt_number == 0
    assert row.last_error_sanitized
    assert "52998224725" not in (row.last_error_sanitized or "")
    due = await repo.list_due(clock.dt)
    assert len(due) == 1


@pytest.mark.asyncio
async def test_b6_fail_after_send_reconciles_no_duplicate() -> None:
    clock = _Clock(MONDAY_OPEN)
    repo = InMemoryFollowUpRepository()
    await _seed(repo, clock)
    sent: list[str] = []

    async def sender(task, text):
        sent.append(text)
        raise FollowUpSendConfirmedError("crash after provider ack")

    sched = _scheduler(repo, clock, sender=sender, snapshot=_snap())
    first = await sched.tick()
    assert first[0].sent is True
    row = repo.all_rows()[0]
    assert row.status == STATUS_SENT
    assert row.sent_at is not None
    await sched.tick()
    assert len(sent) == 1
    assert len([t for t in repo.all_rows() if t.status == STATUS_SENT]) == 1


@pytest.mark.asyncio
async def test_b7_idempotency_key() -> None:
    clock = _Clock(MONDAY_OPEN)
    repo = InMemoryFollowUpRepository()
    first = await _seed(repo, clock, key="same-key")
    second = await _seed(repo, clock, key="same-key")
    assert first.id == second.id
    assert len(repo.all_rows()) == 1
    sent: list[str] = []

    async def sender(task, text):
        sent.append(text)

    sched = _scheduler(repo, clock, sender=sender, snapshot=_snap())
    await sched.tick()
    await sched.tick()
    assert len(sent) == 1
    by_key = await repo.get_by_idempotency_key("same-key")
    assert by_key is not None
    assert by_key.status == STATUS_SENT


@pytest.mark.asyncio
async def test_b8_due_task_claimed() -> None:
    clock = _Clock(MONDAY_OPEN)
    repo = InMemoryFollowUpRepository()
    task = await _seed(repo, clock)
    due = await repo.list_due(clock.dt)
    assert len(due) == 1
    assert due[0].id == task.id
    claimed = await repo.claim_due(clock.dt, "worker-a")
    assert len(claimed) == 1
    assert claimed[0].status == STATUS_CLAIMED
    assert claimed[0].claimed_by == "worker-a"
    assert claimed[0].claimed_at is not None
    assert await repo.list_due(clock.dt) == []


@pytest.mark.asyncio
async def test_b9_overdue_outside_hours_rescheduled_not_blasted() -> None:
    clock = _Clock(SUNDAY_CLOSED)
    repo = InMemoryFollowUpRepository()
    await _seed(repo, clock, scheduled_at=FRIDAY_AFTERNOON)
    sent: list[str] = []

    async def sender(task, text):
        sent.append(text)

    sched = _scheduler(repo, clock, sender=sender, snapshot=_snap())
    results = await sched.tick()
    assert sent == []
    assert all(r.sent is False for r in results)
    row = repo.all_rows()[0]
    assert row.status == STATUS_PENDING
    assert row.sent_at is None
    scheduled = row.scheduled_at
    if scheduled.tzinfo is None:
        scheduled = scheduled.replace(tzinfo=TZ_BRT)
    assert scheduled.weekday() == 0  # Monday
    assert scheduled.hour == 8


@pytest.mark.asyncio
async def test_b10_restart_does_not_mass_send() -> None:
    clock = _Clock(SUNDAY_CLOSED)
    repo = InMemoryFollowUpRepository()
    for i in range(5):
        await _seed(
            repo,
            clock,
            conversation_id=f"conv-{i}",
            key=f"fu-{i}",
            scheduled_at=FRIDAY_AFTERNOON,
        )
    sent: list[str] = []

    async def sender(task, text):
        sent.append(text)

    sched = _scheduler(repo, clock, sender=sender, snapshot=_snap())
    await sched.on_startup()
    assert sent == []
    rows = repo.all_rows()
    assert len(rows) == 5
    assert all(r.sent_at is None for r in rows)
    assert all(r.status == STATUS_PENDING for r in rows)


@pytest.mark.asyncio
async def test_b11_cas_miss_aborts_send() -> None:
    clock = _Clock(MONDAY_OPEN)
    repo = InMemoryFollowUpRepository()
    await _seed(repo, clock, ownership_revision=0)
    live = _snap(ownership_revision=0)
    sent: list[str] = []

    async def sender(task, text):
        sent.append(text)

    async def compose(task, snapshot):
        live.ownership_revision = 7
        return "should-not-send"

    sched = _scheduler(repo, clock, sender=sender, composer=compose, snapshot=live)
    results = await sched.tick()
    assert sent == []
    assert results[0].sent is False
    assert results[0].reason == CANCEL_CAS_MISS
    row = repo.all_rows()[0]
    assert row.sent_at is None
    assert row.status != STATUS_SENT


@pytest.mark.asyncio
async def test_b12_cancel_cleanup_does_not_delete_audit_row() -> None:
    clock = _Clock(MONDAY_OPEN)
    repo = InMemoryFollowUpRepository()
    task = await _seed(repo, clock)
    set_followup_repository(repo)
    await cancel_pending_automation("conv-1")
    still = await repo.get_by_id(task.id)
    assert still is not None
    assert still.status == STATUS_CANCELLED
    assert still.cancel_reason == CANCEL_REASON_HUMAN_ASSUMED
    assert still.cancelled_at is not None
    assert len(repo.all_rows()) == 1
    again = await repo.cancel(task.id, CANCEL_REASON_HUMAN_ASSUMED, now=clock.dt)
    assert again is not None
    assert again.status == STATUS_CANCELLED
    assert len(repo.all_rows()) == 1


def test_sanitize_followup_error_strips_pii() -> None:
    cleaned = sanitize_followup_error("boom https://x.test/a token=supersecret 12345678901")
    assert "https://" not in cleaned
    assert "supersecret" not in cleaned
    assert "12345678901" not in cleaned
    assert "<url>" in cleaned
    assert "<id>" in cleaned
