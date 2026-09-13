"""Durable follow-up worker — claim due work, never sleep.

Pipeline (one tick, injectable clock ``now_brt``):

1. locate due
2. claim (SKIP LOCKED / CAS)
3. re-read ownership
4. check new inbound
5. cancel reasons
6. commercial state
7. revalidate hours (STORE_HOURS)
8. revalidate context
9. compose seam (injectable; default deterministic placeholder)
10. re-check immediately before send
11. record sent
12. prevent dup (idempotency key + sentAt)

Overdue at startup is re-evaluated against the store window and is never
mass-sent. Outside hours: status stays PENDING, scheduledAt moves to the
next valid window.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Protocol

from sdr.domain.conversation_revision import context_revision_is_usable
from sdr.domain.clock import now_brt as live_now_brt
from sdr.domain.scheduling import is_within_store_hours, next_open_datetime
from sdr.domain.types import LifecycleStatus
from sdr.infrastructure.followup_repository import (
    CANCEL_REASON_CONTEXT_CHANGED,
    CANCEL_REASON_HUMAN_ASSUMED,
    CANCEL_REASON_REVISION_UNAVAILABLE,
    DEFAULT_CLAIM_TTL,
    FollowUpTask,
    STATUS_CLAIMED,
    STATUS_PROCESSING,
    STATUS_SENT,
    sanitize_followup_error,
)

DEFAULT_FOLLOWUP_PLACEHOLDER = "FOLLOWUP_PLACEHOLDER"

CANCEL_NEW_INBOUND = "NEW_INBOUND"
CANCEL_OPT_OUT = "OPT_OUT"
CANCEL_CLOSED = "CLOSED"
CANCEL_COMMERCIAL = "COMMERCIAL_INVALID"
CANCEL_CAS_MISS = "CAS_MISS"
CANCEL_ATTEMPTS_EXHAUSTED = "ATTEMPTS_EXHAUSTED"
CANCEL_REVISION_UNAVAILABLE = CANCEL_REASON_REVISION_UNAVAILABLE

NowFn = Callable[[], datetime]
ComposerFn = Callable[[FollowUpTask, "FollowUpSnapshot"], Awaitable[str]]
SenderFn = Callable[[FollowUpTask, str], Awaitable[Any]]
SnapshotFn = Callable[[str], Awaitable["FollowUpSnapshot | None"]]


class FollowUpSendConfirmedError(Exception):
    """Outbound was accepted by the provider; persist must reconcile as SENT."""


@dataclass(slots=True)
class FollowUpSnapshot:
    """Live conversation facts needed at send time — not stored on the task."""

    conversation_id: str
    bot_status: str = LifecycleStatus.BOT_ACTIVE.value
    ownership_revision: int = 0
    context_revision: int | None = None
    last_inbound_at: datetime | None = None
    opt_out: bool = False
    closed: bool = False
    commercial_ok: bool = True
    revision_loaded: bool = False


@dataclass(slots=True)
class FollowUpTickResult:
    task_id: str
    action: str
    reason: str | None = None
    sent: bool = False


class _Repo(Protocol):
    async def create_or_supersede(self, **kwargs: Any) -> FollowUpTask: ...
    async def claim_due(self, now: datetime, worker_id: str, **kwargs: Any) -> list[FollowUpTask]: ...
    async def mark_processing(self, task_id: str, *, now: datetime | None = None) -> FollowUpTask | None: ...
    async def mark_sent(self, task_id: str, *, now: datetime | None = None) -> FollowUpTask | None: ...
    async def mark_failed(
        self,
        task_id: str,
        error: str,
        *,
        send_confirmed: bool = False,
        now: datetime | None = None,
    ) -> FollowUpTask | None: ...
    async def cancel(self, task_id: str, reason: str, *, now: datetime | None = None) -> FollowUpTask | None: ...
    async def cancel_pending_for_conversation(self, conversation_id: str, reason: str = "", **kwargs: Any) -> Any: ...
    async def list_due(self, now: datetime) -> list[FollowUpTask]: ...
    async def get_by_idempotency_key(self, key: str) -> FollowUpTask | None: ...
    async def get_by_id(self, task_id: str) -> FollowUpTask | None: ...
    async def reschedule(
        self,
        task_id: str,
        scheduled_at: datetime,
        *,
        now: datetime | None = None,
    ) -> FollowUpTask | None: ...


async def default_compose_followup(
    task: FollowUpTask, snapshot: FollowUpSnapshot
) -> str:
    """Frente D replaces this seam. Deterministic placeholder — no LLM."""
    _ = (task, snapshot)
    return DEFAULT_FOLLOWUP_PLACEHOLDER


async def default_send_followup(task: FollowUpTask, text: str) -> None:
    """No-op confirmed send. Frente D wires Evolution here."""
    _ = (task, text)
    return None


async def load_followup_snapshot_from_conversation(
    conversations: Any, conversation_id: str
) -> FollowUpSnapshot:
    """Worker snapshot from live Conversation columns. Missing column → no send."""
    get = getattr(conversations, "get_by_id", None)
    if get is None:
        return _unavailable_snapshot(conversation_id)
    try:
        row = await get(conversation_id)
    except Exception as exc:
        name = type(exc).__name__.lower()
        text = str(exc).lower()
        if "undefinedcolumn" in name or "contextrevision" in text or "42703" in text:
            return _unavailable_snapshot(conversation_id)
        raise
    if row is None:
        return _unavailable_snapshot(conversation_id)
    try:
        keys = set(row.keys())
    except Exception:
        keys = set()
    if "contextRevision" not in keys:
        return _unavailable_snapshot(conversation_id)
    raw = row["contextRevision"]
    if raw is None:
        return _unavailable_snapshot(conversation_id)
    revision = int(raw)
    if not context_revision_is_usable(revision):
        return _unavailable_snapshot(conversation_id)
    opted = row["sdrOptedOutAt"] if "sdrOptedOutAt" in keys else None
    bot = str(row["botStatus"] if "botStatus" in keys else LifecycleStatus.BOT_ACTIVE.value)
    own = int(row["ownershipRevision"] or 0) if "ownershipRevision" in keys else 0
    return FollowUpSnapshot(
        conversation_id=conversation_id,
        bot_status=bot,
        ownership_revision=own,
        context_revision=revision,
        opt_out=opted is not None,
        closed=bot == LifecycleStatus.HUMAN_CLOSED.value,
        commercial_ok=opted is None,
        revision_loaded=True,
    )


def _unavailable_snapshot(conversation_id: str) -> FollowUpSnapshot:
    """No live Conversation.contextRevision — fail-safe, never send."""
    return FollowUpSnapshot(
        conversation_id=conversation_id,
        revision_loaded=False,
        context_revision=None,
    )


def _default_snapshot(task: FollowUpTask) -> FollowUpSnapshot:
    # Copying the task's own revision would make CAS a no-op. Missing loader
    # is fail-safe: do not send.
    return _unavailable_snapshot(task.conversation_id)


class FollowUpScheduler:
    def __init__(
        self,
        repository: _Repo,
        *,
        worker_id: str = "sdr-followup",
        now_brt: NowFn | None = None,
        composer: ComposerFn | None = None,
        sender: SenderFn | None = None,
        load_snapshot: SnapshotFn | None = None,
        claim_ttl: timedelta = DEFAULT_CLAIM_TTL,
        claim_limit: int = 1,
    ) -> None:
        self.repository = repository
        self.worker_id = worker_id
        self._now = now_brt or live_now_brt
        self._compose = composer or default_compose_followup
        self._send = sender or default_send_followup
        self._load_snapshot = load_snapshot
        self.claim_ttl = claim_ttl
        self.claim_limit = claim_limit
        # In-process delivery log so a crash after send reconciles without dup.
        self._delivered_keys: set[str] = set()
        self.context_checked_before_compose = False
        self.context_checked_before_send = False

    def _stamp(self) -> datetime:
        return self._now()

    async def on_startup(self) -> list[FollowUpTickResult]:
        """Re-evaluate overdue window. Never mass-sends."""
        return await self.reschedule_overdue_outside_hours()

    async def reschedule_overdue_outside_hours(self) -> list[FollowUpTickResult]:
        now = self._stamp()
        results: list[FollowUpTickResult] = []
        if is_within_store_hours(now):
            return results
        nxt = next_open_datetime(now)
        due = await self.repository.list_due(now)
        for task in due:
            updated = await self.repository.reschedule(task.id, nxt, now=now)
            if updated is None:
                continue
            results.append(
                FollowUpTickResult(
                    task_id=task.id,
                    action="rescheduled",
                    reason="outside_hours",
                )
            )
        return results

    async def tick(self) -> list[FollowUpTickResult]:
        """One worker cycle: locate → claim → validate → compose → send → record."""
        now = self._stamp()
        # 7 (startup / overdue): never blast outside hours.
        await self.reschedule_overdue_outside_hours()
        # 1 locate due
        due = await self.repository.list_due(now)
        _ = due
        # 2 claim
        claimed = await self.repository.claim_due(
            now,
            self.worker_id,
            limit=self.claim_limit,
            claim_ttl=self.claim_ttl,
        )
        results: list[FollowUpTickResult] = []
        for task in claimed:
            results.append(await self._process_claimed(task))
        return results

    async def _load(self, task: FollowUpTask) -> FollowUpSnapshot:
        if self._load_snapshot is None:
            return _default_snapshot(task)
        loaded = await self._load_snapshot(task.conversation_id)
        return loaded if loaded is not None else _default_snapshot(task)

    async def _reload_task(self, task_id: str) -> FollowUpTask | None:
        return await self.repository.get_by_id(task_id)

    def _pre_send_blockers(
        self,
        task: FollowUpTask,
        snapshot: FollowUpSnapshot,
        now: datetime,
    ) -> str | None:
        """Return a cancel/abort reason, ``outside_hours``, or None if send is allowed."""
        if not snapshot.revision_loaded or not context_revision_is_usable(
            snapshot.context_revision
        ):
            return CANCEL_REVISION_UNAVAILABLE
        if not context_revision_is_usable(task.context_revision):
            return CANCEL_REVISION_UNAVAILABLE
        if snapshot.context_revision != task.context_revision:
            return CANCEL_REASON_CONTEXT_CHANGED
        if task.sent_at is not None or task.status == STATUS_SENT:
            return "already_sent"
        if task.status not in {STATUS_CLAIMED, STATUS_PROCESSING}:
            return CANCEL_CAS_MISS
        if task.claimed_by is not None and task.claimed_by != self.worker_id:
            return CANCEL_CAS_MISS
        keyed = task.idempotency_key
        if keyed in self._delivered_keys and task.sent_at is None:
            # Delivery happened; caller reconciles as sent.
            return "reconcile_sent"
        if snapshot.ownership_revision != task.ownership_revision:
            return CANCEL_CAS_MISS
        if snapshot.bot_status == LifecycleStatus.HUMAN_ACTIVE.value:
            return CANCEL_REASON_HUMAN_ASSUMED
        if (
            snapshot.closed
            or snapshot.bot_status == LifecycleStatus.HUMAN_CLOSED.value
        ):
            return CANCEL_CLOSED
        if snapshot.opt_out:
            return CANCEL_OPT_OUT
        if not snapshot.commercial_ok:
            return CANCEL_COMMERCIAL
        if snapshot.context_revision != task.context_revision:
            return CANCEL_REASON_CONTEXT_CHANGED
        if snapshot.last_inbound_at is not None and task.created_at is not None:
            inbound = snapshot.last_inbound_at
            created = task.created_at
            if inbound.tzinfo is None and created.tzinfo is not None:
                inbound = inbound.replace(tzinfo=created.tzinfo)
            elif inbound.tzinfo is not None and created.tzinfo is None:
                created = created.replace(tzinfo=inbound.tzinfo)
            if inbound > created:
                return CANCEL_NEW_INBOUND
        if task.attempt_number >= task.maximum_attempts:
            return CANCEL_ATTEMPTS_EXHAUSTED
        if not is_within_store_hours(now):
            return "outside_hours"
        return None

    async def _apply_blocker(
        self, task: FollowUpTask, reason: str, now: datetime
    ) -> FollowUpTickResult:
        if reason == "already_sent":
            await self.repository.mark_sent(task.id, now=now)
            return FollowUpTickResult(task.id, "already_sent", sent=True)
        if reason == "reconcile_sent":
            await self.repository.mark_sent(task.id, now=now)
            return FollowUpTickResult(task.id, "reconciled", sent=True)
        if reason == "outside_hours":
            nxt = next_open_datetime(now)
            await self.repository.reschedule(task.id, nxt, now=now)
            return FollowUpTickResult(task.id, "rescheduled", reason=reason)
        if reason == CANCEL_CAS_MISS:
            await self.repository.reschedule(task.id, task.scheduled_at, now=now)
            return FollowUpTickResult(task.id, "aborted", reason=reason)
        if reason == CANCEL_REVISION_UNAVAILABLE:
            # Missing column or unloadable revision: do not send; return to
            # PENDING so a later deploy with the column can resume. Never 0.
            await self.repository.reschedule(task.id, task.scheduled_at, now=now)
            return FollowUpTickResult(task.id, "aborted", reason=reason)
        await self.repository.cancel(task.id, reason, now=now)
        return FollowUpTickResult(task.id, "cancelled", reason=reason)

    async def _process_claimed(self, task: FollowUpTask) -> FollowUpTickResult:
        now = self._stamp()
        processing = await self.repository.mark_processing(task.id, now=now)
        if processing is None:
            fresh = await self._reload_task(task.id)
            if fresh is not None and (fresh.sent_at is not None or fresh.status == STATUS_SENT):
                return FollowUpTickResult(task.id, "already_sent", sent=True)
            return FollowUpTickResult(task.id, "aborted", reason=CANCEL_CAS_MISS)
        task = processing

        # 3 re-read ownership  4 inbound  5 cancel  6 commercial  7 hours  8 context
        snapshot = await self._load(task)
        self.context_checked_before_compose = True
        blocker = self._pre_send_blockers(task, snapshot, now)
        if blocker is not None:
            return await self._apply_blocker(task, blocker, now)

        # 9 compose seam
        text = await self._compose(task, snapshot)
        if not str(text or "").strip():
            return FollowUpTickResult(task.id, "aborted", reason="empty_or_unsafe")

        # 10 re-check immediately before send
        task = await self._reload_task(task.id) or task
        snapshot = await self._load(task)
        now = self._stamp()
        self.context_checked_before_send = True
        blocker = self._pre_send_blockers(task, snapshot, now)
        if blocker is not None:
            return await self._apply_blocker(task, blocker, now)

        # 12 prevent dup — already delivered under this idempotency key
        existing = await self.repository.get_by_idempotency_key(task.idempotency_key)
        if existing is not None and (
            existing.sent_at is not None or existing.status == STATUS_SENT
        ):
            await self.repository.mark_sent(task.id, now=now)
            return FollowUpTickResult(task.id, "already_sent", sent=True)
        if task.idempotency_key in self._delivered_keys:
            await self.repository.mark_sent(task.id, now=now)
            return FollowUpTickResult(task.id, "reconciled", sent=True)

        send_confirmed = False
        try:
            await self._send(task, text)
            send_confirmed = True
            self._delivered_keys.add(task.idempotency_key)
            # 11 record sent
            recorded = await self.repository.mark_sent(task.id, now=now)
            if recorded is None:
                # CAS miss after send: still reconcile as sent, never duplicate.
                recorded = await self.repository.mark_sent(task.id, now=now)
            if recorded is None or recorded.sent_at is None:
                await self.repository.mark_failed(
                    task.id,
                    "cas_miss_after_send",
                    send_confirmed=True,
                    now=now,
                )
            return FollowUpTickResult(task.id, "sent", sent=True)
        except FollowUpSendConfirmedError:
            send_confirmed = True
            self._delivered_keys.add(task.idempotency_key)
            await self.repository.mark_failed(
                task.id,
                "send_confirmed_then_failed",
                send_confirmed=True,
                now=now,
            )
            return FollowUpTickResult(task.id, "reconciled", sent=True)
        except Exception as exc:
            if send_confirmed:
                self._delivered_keys.add(task.idempotency_key)
                await self.repository.mark_failed(
                    task.id,
                    sanitize_followup_error(exc),
                    send_confirmed=True,
                    now=now,
                )
                return FollowUpTickResult(task.id, "reconciled", sent=True)
            await self.repository.mark_failed(
                task.id,
                sanitize_followup_error(exc),
                send_confirmed=False,
                now=now,
            )
            return FollowUpTickResult(
                task.id,
                "failed",
                reason=sanitize_followup_error(exc),
                sent=False,
            )


async def cancel_pending_for_conversation(
    repository: _Repo | None,
    conversation_id: str,
    *,
    reason: str = CANCEL_REASON_HUMAN_ASSUMED,
) -> None:
    if repository is None:
        return None
    await repository.cancel_pending_for_conversation(conversation_id, reason)


__all__ = [
    "CANCEL_CAS_MISS",
    "CANCEL_CLOSED",
    "CANCEL_COMMERCIAL",
    "CANCEL_NEW_INBOUND",
    "CANCEL_OPT_OUT",
    "DEFAULT_FOLLOWUP_PLACEHOLDER",
    "FollowUpScheduler",
    "FollowUpSendConfirmedError",
    "FollowUpSnapshot",
    "FollowUpTickResult",
    "CANCEL_REVISION_UNAVAILABLE",
    "cancel_pending_for_conversation",
    "default_compose_followup",
    "default_send_followup",
    "load_followup_snapshot_from_conversation",
]
