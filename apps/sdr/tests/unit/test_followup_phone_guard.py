"""Phase 13A-R1 — follow-up phone block must not destroy recoverable work."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from sdr.application.followup_scheduler import FollowUpScheduler, FollowUpSnapshot
from sdr.config import Settings
from sdr.domain.clock import TZ_BRT
from sdr.domain.types import LifecycleStatus
from sdr.infrastructure.followup_repository import (
    InMemoryFollowUpRepository,
    STATUS_CANCELLED,
    STATUS_PENDING,
    STATUS_SENT,
)

ALLOWED = "5511999000101"
DENIED = "5511999000199"
MONDAY_OPEN = datetime(2026, 9, 7, 10, 0, tzinfo=TZ_BRT)


class _Clock:
    def __init__(self, dt: datetime) -> None:
        self.dt = dt

    def __call__(self) -> datetime:
        return self.dt


def _base_settings(**overrides: object) -> Settings:
    data: dict[str, object] = {
        "database_url": "postgresql://unused:unused@localhost:5432/unused",
        "redis_url": "redis://localhost:6379/15",
        "sdr_webhook_secret": "not-a-placeholder",
        "sdr_environment": "staging",
        "sdr_outbound_policy": "allowlist",
        "sdr_outbound_allowlist": ALLOWED,
        "sdr_documents_bucket": "sdr-documents-test",
        "storage_endpoint": "",
        "storage_access_key": "",
        "storage_secret_key": "",
    }
    data.update(overrides)
    return Settings(**data)


async def _run(*, settings: object, phone: str, key: str):
    repo = InMemoryFollowUpRepository()
    sent: list[str] = []

    async def sender(task, text: str) -> None:
        sent.append(text)
        raise AssertionError("sender must not run")

    async def load(_cid: str) -> FollowUpSnapshot:
        return FollowUpSnapshot(
            conversation_id="conv-phone",
            bot_status=LifecycleStatus.BOT_ACTIVE.value,
            ownership_revision=0,
            context_revision=1,
            revision_loaded=True,
            phone=phone,
        )

    sched = FollowUpScheduler(
        repo,
        worker_id="w1",
        now_brt=_Clock(MONDAY_OPEN),
        sender=sender,
        load_snapshot=load,
        settings=settings,  # type: ignore[arg-type]
    )
    await repo.create_or_supersede(
        conversation_id="conv-phone",
        reason="wait_reply",
        scheduled_at=MONDAY_OPEN,
        idempotency_key=key,
        context_revision=1,
        ownership_revision=0,
    )
    results = await sched.tick()
    return results, repo.all_rows()[0], sent


def _assert_not_sent(task, sent: list[str], phone: str) -> None:
    assert sent == []
    assert task.sent_at is None
    assert task.status != STATUS_SENT
    assert phone not in (task.cancel_reason or "")
    assert phone not in (task.last_error_sanitized or "")


def _assert_recoverable(results, task, sent: list[str], phone: str) -> None:
    _assert_not_sent(task, sent, phone)
    assert results
    assert results[0].sent is False
    assert task.status == STATUS_PENDING
    assert task.cancel_reason is None
    assert task.attempt_number == 0
    assert "PHONE_ACCESS_UNAVAILABLE" in (
        (task.last_error_sanitized or "") + " " + (results[0].reason or "")
    )
    assert task.scheduled_at > MONDAY_OPEN
    assert results[0].action in {"aborted", "rescheduled"}


@pytest.mark.asyncio
async def test_deny_all_does_not_cancel_followup() -> None:
    results, task, sent = await _run(
        settings=_base_settings(sdr_environment="sandbox", sdr_outbound_policy="deny_all"),
        phone=ALLOWED,
        key="fu-deny-all",
    )
    _assert_recoverable(results, task, sent, ALLOWED)


@pytest.mark.asyncio
async def test_invalid_policy_does_not_cancel_followup() -> None:
    settings = SimpleNamespace(
        sdr_environment="staging",
        sdr_outbound_policy="open",
        sdr_outbound_allowlist=ALLOWED,
    )
    results, task, sent = await _run(settings=settings, phone=ALLOWED, key="fu-bad-policy")
    _assert_recoverable(results, task, sent, ALLOWED)


@pytest.mark.asyncio
async def test_invalid_environment_does_not_cancel_followup() -> None:
    settings = SimpleNamespace(
        sdr_environment="prod",
        sdr_outbound_policy="allowlist",
        sdr_outbound_allowlist=ALLOWED,
    )
    results, task, sent = await _run(settings=settings, phone=ALLOWED, key="fu-bad-env")
    _assert_recoverable(results, task, sent, ALLOWED)


@pytest.mark.asyncio
async def test_empty_allowlist_does_not_cancel_followup() -> None:
    results, task, sent = await _run(
        settings=_base_settings(sdr_outbound_allowlist="  ,  "),
        phone=ALLOWED,
        key="fu-empty-allow",
    )
    _assert_recoverable(results, task, sent, ALLOWED)


@pytest.mark.asyncio
async def test_missing_phone_does_not_cancel_followup() -> None:
    results, task, sent = await _run(
        settings=_base_settings(),
        phone="",
        key="fu-missing-phone",
    )
    _assert_recoverable(results, task, sent, ALLOWED)


@pytest.mark.asyncio
async def test_unrestricted_outside_production_does_not_cancel_followup() -> None:
    results, task, sent = await _run(
        settings=_base_settings(sdr_outbound_policy="unrestricted"),
        phone=ALLOWED,
        key="fu-unrestricted-staging",
    )
    _assert_recoverable(results, task, sent, ALLOWED)


@pytest.mark.asyncio
async def test_number_outside_valid_allowlist_is_cancelled() -> None:
    results, task, sent = await _run(
        settings=_base_settings(),
        phone=DENIED,
        key="fu-denied-permanent",
    )
    _assert_not_sent(task, sent, DENIED)
    assert task.status == STATUS_CANCELLED
    assert task.cancel_reason == "PHONE_NOT_ALLOWED"
    assert results[0].action == "cancelled"
    assert results[0].sent is False
