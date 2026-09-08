"""Durable FollowUpTask persistence — claim/CAS, never DELETE on cancel.

Postgres uses ``UPDATE … WHERE id IN (SELECT … FOR UPDATE SKIP LOCKED)``.
``InMemoryFollowUpRepository`` simulates the same CAS / skip-locked contract
for unit tests (no live Postgres).
"""

from __future__ import annotations

import asyncio
import re
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol

from sdr.domain.clock import TZ_BRT
from sdr.infrastructure.conversation_repository import SCHEMA

STATUS_PENDING = "PENDING"
STATUS_CLAIMED = "CLAIMED"
STATUS_PROCESSING = "PROCESSING"
STATUS_SENT = "SENT"
STATUS_CANCELLED = "CANCELLED"
STATUS_FAILED = "FAILED"
STATUS_SUPERSEDED = "SUPERSEDED"

ACTIVE_STATUSES = frozenset({STATUS_PENDING, STATUS_CLAIMED, STATUS_PROCESSING})
CLAIMABLE_HELD = frozenset({STATUS_CLAIMED, STATUS_PROCESSING})
DEFAULT_CLAIM_TTL = timedelta(minutes=5)

CANCEL_REASON_HUMAN_ASSUMED = "HUMAN_ASSUMED"
CANCEL_REASON_CONTEXT_CHANGED = "CONTEXT_CHANGED"

_PII_DIGITS = re.compile(r"\b\d{11,}\b")
_URL = re.compile(r"https?://\S+", re.I)
_SECRET = re.compile(r"(?i)(secret|token|key|password|authorization)=\S+")


def sanitize_followup_error(exc: BaseException | str) -> str:
    """Strip URLs, secrets, and long digit runs (CPF-like). Never store raw PII."""
    text = f"{type(exc).__name__}: {exc}" if isinstance(exc, BaseException) else str(exc)
    text = _URL.sub("<url>", text)
    text = _SECRET.sub(r"\1=<redacted>", text)
    text = _PII_DIGITS.sub("<id>", text)
    return text[:300]


def _new_id() -> str:
    return str(uuid.uuid4())


def naive_wall(dt: datetime | None) -> datetime | None:
    """Persist BRT wall clock without converting to UTC (matches Conversation timestamps)."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(TZ_BRT).replace(tzinfo=None)
    return dt


def _copy_task(task: FollowUpTask) -> FollowUpTask:
    return deepcopy(task)


@dataclass(slots=True)
class FollowUpTask:
    id: str
    conversation_id: str
    reason: str
    scheduled_at: datetime
    idempotency_key: str
    status: str = STATUS_PENDING
    lead_id: str | None = None
    original_temporal_text: str | None = None
    consent_source: str | None = None
    consent_level: str | None = None
    attempt_number: int = 0
    maximum_attempts: int = 1
    context_revision: int = 0
    ownership_revision: int = 0
    claimed_at: datetime | None = None
    claimed_by: str | None = None
    sent_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancel_reason: str | None = None
    failed_at: datetime | None = None
    last_error_sanitized: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(TZ_BRT))
    updated_at: datetime = field(default_factory=lambda: datetime.now(TZ_BRT))

    @classmethod
    def from_row(cls, row: Any) -> FollowUpTask:
        return cls(
            id=row["id"],
            conversation_id=row["conversationId"],
            lead_id=row["leadId"],
            reason=row["reason"],
            status=str(row["status"]),
            scheduled_at=row["scheduledAt"],
            original_temporal_text=row["originalTemporalText"],
            consent_source=row["consentSource"],
            consent_level=row["consentLevel"],
            attempt_number=int(row["attemptNumber"] or 0),
            maximum_attempts=int(row["maximumAttempts"] or 1),
            context_revision=int(row["contextRevision"] or 0),
            ownership_revision=int(row["ownershipRevision"] or 0),
            idempotency_key=row["idempotencyKey"],
            claimed_at=row["claimedAt"],
            claimed_by=row["claimedBy"],
            sent_at=row["sentAt"],
            cancelled_at=row["cancelledAt"],
            cancel_reason=row["cancelReason"],
            failed_at=row["failedAt"],
            last_error_sanitized=row["lastErrorSanitized"],
            created_at=row["createdAt"],
            updated_at=row["updatedAt"],
        )


class FollowUpStore(Protocol):
    async def create_or_supersede(self, **kwargs: Any) -> FollowUpTask: ...
    async def claim_due(
        self,
        now: datetime,
        worker_id: str,
        *,
        limit: int = 1,
        claim_ttl: timedelta = DEFAULT_CLAIM_TTL,
    ) -> list[FollowUpTask]: ...
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
    async def cancel(
        self,
        task_id: str,
        reason: str,
        *,
        now: datetime | None = None,
    ) -> FollowUpTask | None: ...
    async def cancel_pending_for_conversation(
        self,
        conversation_id: str,
        reason: str = CANCEL_REASON_HUMAN_ASSUMED,
        *,
        now: datetime | None = None,
    ) -> list[FollowUpTask]: ...
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


def _is_due_pending(task: FollowUpTask, now: datetime) -> bool:
    if task.status != STATUS_PENDING or task.sent_at is not None:
        return False
    return naive_wall(task.scheduled_at) <= naive_wall(now)  # type: ignore[operator]


def _claim_expired(task: FollowUpTask, now: datetime, ttl: timedelta) -> bool:
    if task.status not in CLAIMABLE_HELD or task.sent_at is not None:
        return False
    if task.claimed_at is None:
        return True
    claimed = naive_wall(task.claimed_at)
    cutoff = naive_wall(now - ttl)
    return claimed is not None and cutoff is not None and claimed <= cutoff


def _failed_retryable(task: FollowUpTask, now: datetime) -> bool:
    if task.status != STATUS_FAILED or task.sent_at is not None:
        return False
    if task.attempt_number >= task.maximum_attempts:
        return False
    return naive_wall(task.scheduled_at) <= naive_wall(now)  # type: ignore[operator]


class InMemoryFollowUpRepository:
    """Process-local store that simulates SKIP LOCKED + compare-and-set."""

    def __init__(self) -> None:
        self._rows: dict[str, FollowUpTask] = {}
        self._mutex = asyncio.Lock()
        # Ids held by an in-flight claim transaction — skipped, never waited on.
        self._skip_locked: set[str] = set()

    def hold_skip_lock(self, task_id: str) -> None:
        self._skip_locked.add(task_id)

    def release_skip_lock(self, task_id: str) -> None:
        self._skip_locked.discard(task_id)

    def all_rows(self) -> list[FollowUpTask]:
        return [_copy_task(t) for t in self._rows.values()]

    async def create_or_supersede(
        self,
        *,
        conversation_id: str,
        reason: str,
        scheduled_at: datetime,
        idempotency_key: str,
        lead_id: str | None = None,
        original_temporal_text: str | None = None,
        consent_source: str | None = None,
        consent_level: str | None = None,
        maximum_attempts: int = 1,
        context_revision: int = 0,
        ownership_revision: int = 0,
        now: datetime | None = None,
    ) -> FollowUpTask:
        stamp = now or datetime.now(TZ_BRT)
        async with self._mutex:
            existing = self._by_key(idempotency_key)
            if existing is not None:
                return _copy_task(existing)
            for task in list(self._rows.values()):
                if (
                    task.conversation_id == conversation_id
                    and task.status in ACTIVE_STATUSES
                    and task.sent_at is None
                    and task.context_revision != context_revision
                ):
                    task.status = STATUS_SUPERSEDED
                    task.cancelled_at = stamp
                    task.cancel_reason = CANCEL_REASON_CONTEXT_CHANGED
                    task.updated_at = stamp
            created = FollowUpTask(
                id=_new_id(),
                conversation_id=conversation_id,
                lead_id=lead_id,
                reason=reason,
                scheduled_at=scheduled_at,
                idempotency_key=idempotency_key,
                original_temporal_text=original_temporal_text,
                consent_source=consent_source,
                consent_level=consent_level,
                maximum_attempts=maximum_attempts,
                context_revision=context_revision,
                ownership_revision=ownership_revision,
                created_at=stamp,
                updated_at=stamp,
            )
            self._rows[created.id] = created
            return _copy_task(created)

    async def claim_due(
        self,
        now: datetime,
        worker_id: str,
        *,
        limit: int = 1,
        claim_ttl: timedelta = DEFAULT_CLAIM_TTL,
    ) -> list[FollowUpTask]:
        claimed: list[FollowUpTask] = []
        async with self._mutex:
            candidates = [
                t
                for t in self._sorted()
                if t.id not in self._skip_locked
                and (
                    _is_due_pending(t, now)
                    or _claim_expired(t, now, claim_ttl)
                    or _failed_retryable(t, now)
                )
            ]
            for task in candidates:
                if len(claimed) >= limit:
                    break
                # SKIP LOCKED: if another worker holds the row, skip — do not wait.
                if task.id in self._skip_locked:
                    continue
                self._skip_locked.add(task.id)
                try:
                    if not (
                        _is_due_pending(task, now)
                        or _claim_expired(task, now, claim_ttl)
                        or _failed_retryable(task, now)
                    ):
                        continue
                    if task.sent_at is not None:
                        continue
                    task.status = STATUS_CLAIMED
                    task.claimed_at = now
                    task.claimed_by = worker_id
                    task.updated_at = now
                    claimed.append(_copy_task(task))
                finally:
                    self._skip_locked.discard(task.id)
        return claimed

    async def mark_processing(
        self, task_id: str, *, now: datetime | None = None
    ) -> FollowUpTask | None:
        stamp = now or datetime.now(TZ_BRT)
        async with self._mutex:
            task = self._rows.get(task_id)
            if task is None or task.status not in CLAIMABLE_HELD:
                return None
            if task.sent_at is not None:
                return _copy_task(task)
            task.status = STATUS_PROCESSING
            task.updated_at = stamp
            return _copy_task(task)

    async def mark_sent(
        self, task_id: str, *, now: datetime | None = None
    ) -> FollowUpTask | None:
        stamp = now or datetime.now(TZ_BRT)
        async with self._mutex:
            task = self._rows.get(task_id)
            if task is None:
                return None
            if task.sent_at is not None or task.status == STATUS_SENT:
                return _copy_task(task)
            if task.status not in CLAIMABLE_HELD:
                return None
            task.status = STATUS_SENT
            task.sent_at = stamp
            task.attempt_number = int(task.attempt_number) + 1
            task.updated_at = stamp
            return _copy_task(task)

    async def mark_failed(
        self,
        task_id: str,
        error: str,
        *,
        send_confirmed: bool = False,
        now: datetime | None = None,
    ) -> FollowUpTask | None:
        stamp = now or datetime.now(TZ_BRT)
        if send_confirmed:
            return await self.mark_sent(task_id, now=stamp)
        async with self._mutex:
            task = self._rows.get(task_id)
            if task is None:
                return None
            if task.sent_at is not None or task.status == STATUS_SENT:
                return _copy_task(task)
            sanitized = sanitize_followup_error(error)
            task.last_error_sanitized = sanitized
            task.failed_at = stamp
            task.updated_at = stamp
            # Fail-before-send stays retryable: PENDING, not a deleted row.
            task.status = STATUS_PENDING
            task.claimed_at = None
            task.claimed_by = None
            return _copy_task(task)

    async def cancel(
        self,
        task_id: str,
        reason: str,
        *,
        now: datetime | None = None,
    ) -> FollowUpTask | None:
        stamp = now or datetime.now(TZ_BRT)
        async with self._mutex:
            task = self._rows.get(task_id)
            if task is None:
                return None
            if task.status == STATUS_CANCELLED:
                return _copy_task(task)
            if task.status == STATUS_SENT or task.sent_at is not None:
                return _copy_task(task)
            task.status = STATUS_CANCELLED
            task.cancelled_at = stamp
            task.cancel_reason = reason
            task.claimed_at = None
            task.claimed_by = None
            task.updated_at = stamp
            return _copy_task(task)

    async def cancel_pending_for_conversation(
        self,
        conversation_id: str,
        reason: str = CANCEL_REASON_HUMAN_ASSUMED,
        *,
        now: datetime | None = None,
    ) -> list[FollowUpTask]:
        stamp = now or datetime.now(TZ_BRT)
        cancelled: list[FollowUpTask] = []
        async with self._mutex:
            for task in self._rows.values():
                if task.conversation_id != conversation_id:
                    continue
                if task.status not in ACTIVE_STATUSES and task.status != STATUS_FAILED:
                    continue
                if task.sent_at is not None:
                    continue
                task.status = STATUS_CANCELLED
                task.cancelled_at = stamp
                task.cancel_reason = reason
                task.claimed_at = None
                task.claimed_by = None
                task.updated_at = stamp
                cancelled.append(_copy_task(task))
        return cancelled

    async def cancel_for_conversation(self, conversation_id: str, reason: str) -> int:
        rows = await self.cancel_pending_for_conversation(conversation_id, reason)
        return len(rows)

    async def list_due(self, now: datetime) -> list[FollowUpTask]:
        async with self._mutex:
            return [
                _copy_task(t)
                for t in self._sorted()
                if _is_due_pending(t, now)
            ]

    async def get_by_idempotency_key(self, key: str) -> FollowUpTask | None:
        async with self._mutex:
            found = self._by_key(key)
            return _copy_task(found) if found is not None else None

    async def get_by_id(self, task_id: str) -> FollowUpTask | None:
        async with self._mutex:
            task = self._rows.get(task_id)
            return _copy_task(task) if task is not None else None

    async def reschedule(
        self,
        task_id: str,
        scheduled_at: datetime,
        *,
        now: datetime | None = None,
    ) -> FollowUpTask | None:
        stamp = now or datetime.now(TZ_BRT)
        async with self._mutex:
            task = self._rows.get(task_id)
            if task is None or task.sent_at is not None:
                return None
            if task.status in {STATUS_SENT, STATUS_CANCELLED, STATUS_SUPERSEDED}:
                return _copy_task(task)
            task.scheduled_at = scheduled_at
            task.status = STATUS_PENDING
            task.claimed_at = None
            task.claimed_by = None
            task.updated_at = stamp
            return _copy_task(task)

    def _by_key(self, key: str) -> FollowUpTask | None:
        for task in self._rows.values():
            if task.idempotency_key == key:
                return task
        return None

    def _sorted(self) -> list[FollowUpTask]:
        return sorted(
            self._rows.values(),
            key=lambda t: (naive_wall(t.scheduled_at) or datetime.min, t.id),
        )


class FollowUpRepository:
    """asyncpg adapter — Prisma column names, SKIP LOCKED claim."""

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def create_or_supersede(
        self,
        *,
        conversation_id: str,
        reason: str,
        scheduled_at: datetime,
        idempotency_key: str,
        lead_id: str | None = None,
        original_temporal_text: str | None = None,
        consent_source: str | None = None,
        consent_level: str | None = None,
        maximum_attempts: int = 1,
        context_revision: int = 0,
        ownership_revision: int = 0,
        now: datetime | None = None,
    ) -> FollowUpTask:
        stamp = naive_wall(now or datetime.now(TZ_BRT))
        sched = naive_wall(scheduled_at)
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                existing = await conn.fetchrow(
                    f'''
                    SELECT * FROM "{SCHEMA}"."FollowUpTask"
                    WHERE "idempotencyKey" = $1
                    ''',
                    idempotency_key,
                )
                if existing is not None:
                    return FollowUpTask.from_row(existing)
                await conn.execute(
                    f'''
                    UPDATE "{SCHEMA}"."FollowUpTask"
                    SET "status" = 'SUPERSEDED'::{SCHEMA}."FollowUpTaskStatus",
                        "cancelledAt" = $3,
                        "cancelReason" = $4,
                        "claimedAt" = NULL,
                        "claimedBy" = NULL,
                        "updatedAt" = $3
                    WHERE "conversationId" = $1
                      AND "status" IN (
                        'PENDING'::{SCHEMA}."FollowUpTaskStatus",
                        'CLAIMED'::{SCHEMA}."FollowUpTaskStatus",
                        'PROCESSING'::{SCHEMA}."FollowUpTaskStatus"
                      )
                      AND "sentAt" IS NULL
                      AND "contextRevision" <> $2
                    ''',
                    conversation_id,
                    context_revision,
                    stamp,
                    CANCEL_REASON_CONTEXT_CHANGED,
                )
                row = await conn.fetchrow(
                    f'''
                    INSERT INTO "{SCHEMA}"."FollowUpTask" (
                      "id", "conversationId", "leadId", "reason", "status",
                      "scheduledAt", "originalTemporalText", "consentSource",
                      "consentLevel", "attemptNumber", "maximumAttempts",
                      "contextRevision", "ownershipRevision", "idempotencyKey",
                      "createdAt", "updatedAt"
                    ) VALUES (
                      $1, $2, $3, $4,
                      'PENDING'::{SCHEMA}."FollowUpTaskStatus",
                      $5, $6, $7, $8, 0, $9, $10, $11, $12, $13, $13
                    )
                    RETURNING *
                    ''',
                    _new_id(),
                    conversation_id,
                    lead_id,
                    reason,
                    sched,
                    original_temporal_text,
                    consent_source,
                    consent_level,
                    maximum_attempts,
                    context_revision,
                    ownership_revision,
                    idempotency_key,
                    stamp,
                )
        return FollowUpTask.from_row(row)

    async def claim_due(
        self,
        now: datetime,
        worker_id: str,
        *,
        limit: int = 1,
        claim_ttl: timedelta = DEFAULT_CLAIM_TTL,
    ) -> list[FollowUpTask]:
        stamp = naive_wall(now)
        expired_before = naive_wall(now - claim_ttl)
        sql = f'''
            UPDATE "{SCHEMA}"."FollowUpTask" AS t
            SET "status" = 'CLAIMED'::{SCHEMA}."FollowUpTaskStatus",
                "claimedAt" = $1,
                "claimedBy" = $3,
                "updatedAt" = $1
            WHERE t."id" IN (
              SELECT "id" FROM "{SCHEMA}"."FollowUpTask"
              WHERE (
                  ("status" = 'PENDING'::{SCHEMA}."FollowUpTaskStatus"
                   AND "scheduledAt" <= $1)
                  OR (
                    "status" IN (
                      'CLAIMED'::{SCHEMA}."FollowUpTaskStatus",
                      'PROCESSING'::{SCHEMA}."FollowUpTaskStatus"
                    )
                    AND "sentAt" IS NULL
                    AND "claimedAt" IS NOT NULL
                    AND "claimedAt" <= $2
                  )
                  OR (
                    "status" = 'FAILED'::{SCHEMA}."FollowUpTaskStatus"
                    AND "sentAt" IS NULL
                    AND "attemptNumber" < "maximumAttempts"
                    AND "scheduledAt" <= $1
                  )
              )
              ORDER BY "scheduledAt" ASC
              LIMIT $4
              FOR UPDATE SKIP LOCKED
            )
            RETURNING t.*
        '''
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, stamp, expired_before, worker_id, limit)
        return [FollowUpTask.from_row(r) for r in rows]

    async def mark_processing(
        self, task_id: str, *, now: datetime | None = None
    ) -> FollowUpTask | None:
        stamp = naive_wall(now or datetime.now(TZ_BRT))
        sql = f'''
            UPDATE "{SCHEMA}"."FollowUpTask"
            SET "status" = 'PROCESSING'::{SCHEMA}."FollowUpTaskStatus",
                "updatedAt" = $2
            WHERE "id" = $1
              AND "status" IN (
                'CLAIMED'::{SCHEMA}."FollowUpTaskStatus",
                'PROCESSING'::{SCHEMA}."FollowUpTaskStatus"
              )
              AND "sentAt" IS NULL
            RETURNING *
        '''
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(sql, task_id, stamp)
        return FollowUpTask.from_row(row) if row else None

    async def mark_sent(
        self, task_id: str, *, now: datetime | None = None
    ) -> FollowUpTask | None:
        stamp = naive_wall(now or datetime.now(TZ_BRT))
        sql = f'''
            UPDATE "{SCHEMA}"."FollowUpTask"
            SET "status" = 'SENT'::{SCHEMA}."FollowUpTaskStatus",
                "sentAt" = COALESCE("sentAt", $2),
                "attemptNumber" = CASE
                    WHEN "sentAt" IS NULL THEN "attemptNumber" + 1
                    ELSE "attemptNumber"
                END,
                "updatedAt" = $2
            WHERE "id" = $1
              AND (
                "sentAt" IS NOT NULL
                OR "status" IN (
                  'CLAIMED'::{SCHEMA}."FollowUpTaskStatus",
                  'PROCESSING'::{SCHEMA}."FollowUpTaskStatus",
                  'SENT'::{SCHEMA}."FollowUpTaskStatus"
                )
              )
            RETURNING *
        '''
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(sql, task_id, stamp)
        return FollowUpTask.from_row(row) if row else None

    async def mark_failed(
        self,
        task_id: str,
        error: str,
        *,
        send_confirmed: bool = False,
        now: datetime | None = None,
    ) -> FollowUpTask | None:
        stamp = naive_wall(now or datetime.now(TZ_BRT))
        if send_confirmed:
            return await self.mark_sent(task_id, now=now)
        sanitized = sanitize_followup_error(error)
        sql = f'''
            UPDATE "{SCHEMA}"."FollowUpTask"
            SET "status" = CASE
                    WHEN "sentAt" IS NOT NULL THEN 'SENT'::{SCHEMA}."FollowUpTaskStatus"
                    ELSE 'PENDING'::{SCHEMA}."FollowUpTaskStatus"
                END,
                "lastErrorSanitized" = $3,
                "failedAt" = $2,
                "claimedAt" = CASE WHEN "sentAt" IS NULL THEN NULL ELSE "claimedAt" END,
                "claimedBy" = CASE WHEN "sentAt" IS NULL THEN NULL ELSE "claimedBy" END,
                "updatedAt" = $2
            WHERE "id" = $1
            RETURNING *
        '''
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(sql, task_id, stamp, sanitized)
        return FollowUpTask.from_row(row) if row else None

    async def cancel(
        self,
        task_id: str,
        reason: str,
        *,
        now: datetime | None = None,
    ) -> FollowUpTask | None:
        stamp = naive_wall(now or datetime.now(TZ_BRT))
        sql = f'''
            UPDATE "{SCHEMA}"."FollowUpTask"
            SET "status" = CASE
                    WHEN "status" = 'SENT'::{SCHEMA}."FollowUpTaskStatus"
                      OR "sentAt" IS NOT NULL
                    THEN "status"
                    ELSE 'CANCELLED'::{SCHEMA}."FollowUpTaskStatus"
                END,
                "cancelledAt" = CASE
                    WHEN "status" = 'SENT'::{SCHEMA}."FollowUpTaskStatus"
                      OR "sentAt" IS NOT NULL
                    THEN "cancelledAt"
                    ELSE COALESCE("cancelledAt", $3)
                END,
                "cancelReason" = CASE
                    WHEN "status" = 'SENT'::{SCHEMA}."FollowUpTaskStatus"
                      OR "sentAt" IS NOT NULL
                    THEN "cancelReason"
                    ELSE COALESCE("cancelReason", $2)
                END,
                "claimedAt" = CASE
                    WHEN "status" IN (
                      'SENT'::{SCHEMA}."FollowUpTaskStatus",
                      'CANCELLED'::{SCHEMA}."FollowUpTaskStatus"
                    ) OR "sentAt" IS NOT NULL THEN "claimedAt"
                    ELSE NULL
                END,
                "claimedBy" = CASE
                    WHEN "status" IN (
                      'SENT'::{SCHEMA}."FollowUpTaskStatus",
                      'CANCELLED'::{SCHEMA}."FollowUpTaskStatus"
                    ) OR "sentAt" IS NOT NULL THEN "claimedBy"
                    ELSE NULL
                END,
                "updatedAt" = $3
            WHERE "id" = $1
            RETURNING *
        '''
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(sql, task_id, reason, stamp)
        return FollowUpTask.from_row(row) if row else None

    async def cancel_pending_for_conversation(
        self,
        conversation_id: str,
        reason: str = CANCEL_REASON_HUMAN_ASSUMED,
        *,
        now: datetime | None = None,
    ) -> list[FollowUpTask]:
        stamp = naive_wall(now or datetime.now(TZ_BRT))
        sql = f'''
            UPDATE "{SCHEMA}"."FollowUpTask"
            SET "status" = 'CANCELLED'::{SCHEMA}."FollowUpTaskStatus",
                "cancelledAt" = COALESCE("cancelledAt", $3),
                "cancelReason" = COALESCE("cancelReason", $2),
                "claimedAt" = NULL,
                "claimedBy" = NULL,
                "updatedAt" = $3
            WHERE "conversationId" = $1
              AND "sentAt" IS NULL
              AND "status" IN (
                'PENDING'::{SCHEMA}."FollowUpTaskStatus",
                'CLAIMED'::{SCHEMA}."FollowUpTaskStatus",
                'PROCESSING'::{SCHEMA}."FollowUpTaskStatus",
                'FAILED'::{SCHEMA}."FollowUpTaskStatus"
              )
            RETURNING *
        '''
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, conversation_id, reason, stamp)
        return [FollowUpTask.from_row(r) for r in rows]

    async def cancel_for_conversation(self, conversation_id: str, reason: str) -> int:
        rows = await self.cancel_pending_for_conversation(conversation_id, reason)
        return len(rows)

    async def list_due(self, now: datetime) -> list[FollowUpTask]:
        stamp = naive_wall(now)
        sql = f'''
            SELECT * FROM "{SCHEMA}"."FollowUpTask"
            WHERE "status" = 'PENDING'::{SCHEMA}."FollowUpTaskStatus"
              AND "scheduledAt" <= $1
              AND "sentAt" IS NULL
            ORDER BY "scheduledAt" ASC
        '''
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, stamp)
        return [FollowUpTask.from_row(r) for r in rows]

    async def get_by_idempotency_key(self, key: str) -> FollowUpTask | None:
        sql = f'''
            SELECT * FROM "{SCHEMA}"."FollowUpTask"
            WHERE "idempotencyKey" = $1
        '''
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(sql, key)
        return FollowUpTask.from_row(row) if row else None

    async def get_by_id(self, task_id: str) -> FollowUpTask | None:
        sql = f'''SELECT * FROM "{SCHEMA}"."FollowUpTask" WHERE "id" = $1'''
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(sql, task_id)
        return FollowUpTask.from_row(row) if row else None

    async def reschedule(
        self,
        task_id: str,
        scheduled_at: datetime,
        *,
        now: datetime | None = None,
    ) -> FollowUpTask | None:
        stamp = naive_wall(now or datetime.now(TZ_BRT))
        sched = naive_wall(scheduled_at)
        sql = f'''
            UPDATE "{SCHEMA}"."FollowUpTask"
            SET "scheduledAt" = $2,
                "status" = 'PENDING'::{SCHEMA}."FollowUpTaskStatus",
                "claimedAt" = NULL,
                "claimedBy" = NULL,
                "updatedAt" = $3
            WHERE "id" = $1
              AND "sentAt" IS NULL
              AND "status" NOT IN (
                'SENT'::{SCHEMA}."FollowUpTaskStatus",
                'CANCELLED'::{SCHEMA}."FollowUpTaskStatus",
                'SUPERSEDED'::{SCHEMA}."FollowUpTaskStatus"
              )
            RETURNING *
        '''
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(sql, task_id, sched, stamp)
        return FollowUpTask.from_row(row) if row else None


__all__ = [
    "ACTIVE_STATUSES",
    "CANCEL_REASON_CONTEXT_CHANGED",
    "CANCEL_REASON_HUMAN_ASSUMED",
    "DEFAULT_CLAIM_TTL",
    "FollowUpRepository",
    "FollowUpStore",
    "FollowUpTask",
    "InMemoryFollowUpRepository",
    "STATUS_CANCELLED",
    "STATUS_CLAIMED",
    "STATUS_FAILED",
    "STATUS_PENDING",
    "STATUS_PROCESSING",
    "STATUS_SENT",
    "STATUS_SUPERSEDED",
    "naive_wall",
    "sanitize_followup_error",
]
