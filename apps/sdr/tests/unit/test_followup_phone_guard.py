"""Phase 13A — follow-up send is blocked before the sender is invoked."""

from __future__ import annotations

from datetime import datetime

import pytest

from sdr.application.followup_scheduler import FollowUpScheduler, FollowUpSnapshot
from sdr.config import Settings
from sdr.domain.clock import TZ_BRT
from sdr.domain.phone_access import OutboundDeniedError
from sdr.domain.types import LifecycleStatus
from sdr.infrastructure.followup_repository import InMemoryFollowUpRepository

ALLOWED = "5511999000101"
DENIED = "5511999000199"
MONDAY_OPEN = datetime(2026, 9, 7, 10, 0, tzinfo=TZ_BRT)


class _Clock:
    def __init__(self, dt: datetime) -> None:
        self.dt = dt

    def __call__(self) -> datetime:
        return self.dt


@pytest.mark.asyncio
async def test_followup_denied_phone_does_not_call_sender() -> None:
    repo = InMemoryFollowUpRepository()
    sent: list[str] = []

    async def sender(task, text: str) -> None:
        sent.append(text)
        raise AssertionError("sender must not run for a denied phone")

    async def load(_cid: str) -> FollowUpSnapshot:
        return FollowUpSnapshot(
            conversation_id="conv-denied",
            bot_status=LifecycleStatus.BOT_ACTIVE.value,
            ownership_revision=0,
            context_revision=1,
            revision_loaded=True,
            phone=DENIED,
        )

    settings = Settings(
        database_url="postgresql://unused:unused@localhost:5432/unused",
        redis_url="redis://localhost:6379/15",
        sdr_webhook_secret="test-secret",
        sdr_environment="staging",
        sdr_outbound_policy="allowlist",
        sdr_outbound_allowlist=ALLOWED,
        sdr_documents_bucket="sdr-documents-test",
    )
    sched = FollowUpScheduler(
        repo,
        worker_id="w1",
        now_brt=_Clock(MONDAY_OPEN),
        sender=sender,
        load_snapshot=load,
        settings=settings,
    )
    await repo.create_or_supersede(
        conversation_id="conv-denied",
        reason="wait_reply",
        scheduled_at=MONDAY_OPEN,
        idempotency_key="fu-denied-1",
        context_revision=1,
        ownership_revision=0,
    )
    results = await sched.tick()
    assert sent == []
    assert results
    assert results[0].sent is False
    assert results[0].action in {"cancelled", "aborted"}
    assert "PHONE" in (results[0].reason or "").upper() or "allowlist" in (results[0].reason or "")
    assert DENIED not in (results[0].reason or "")
    assert not isinstance(results[0], OutboundDeniedError)
