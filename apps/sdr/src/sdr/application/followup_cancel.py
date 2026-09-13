"""Cancel pending follow-up and guard stub send against cancel/HUMAN_ACTIVE races.

Frente B owns durable persistence + scheduler claim. This module is the
application contract those workers must call immediately before send:
cancel and HUMAN_ACTIVE win; SENT never returns to PENDING.

``FollowUpCanceller`` is injectable. Default is a no-op so Orchestrator
still constructs when no store is wired.
"""

from __future__ import annotations

from typing import Any, Protocol

from sdr.application.outbound_guard import (
    column_authorizes_outbound,
    read_live_ownership,
)
from sdr.domain.followup_cancel import (
    FollowUpCancelReason,
    FollowUpCanceller,
    FollowUpTaskStatus,
    cancel_reason_for_lead_close,
    followup_send_blocked,
    normalize_cancel_reason,
    task_status_value,
)
from sdr.domain.types import LifecycleStatus


class NoOpFollowUpCanceller:
    """Default canceller — zero tasks, never fails."""

    async def cancel_for_conversation(self, conversation_id: str, reason: str) -> int:
        return 0


class FollowUpSendStore(FollowUpCanceller, Protocol):
    """Canceller plus the claim/send CAS Frente B will persist."""

    async def claim(self, task_id: str) -> Any | None:
        """PENDING → CLAIMED. None if missing, cancelled, or already sent."""
        ...

    async def get(self, task_id: str) -> Any | None: ...

    async def mark_sent(self, task_id: str) -> bool:
        """CLAIMED → SENT. False when cancel won (status is CANCELLED)."""
        ...


async def cancel_pending_followups(
    canceller: FollowUpCanceller | None,
    conversation_id: str,
    reason: str | FollowUpCancelReason,
) -> int:
    if canceller is None:
        return 0
    return await canceller.cancel_for_conversation(
        conversation_id, normalize_cancel_reason(reason)
    )


async def cancel_for_lead_close(
    canceller: FollowUpCanceller | None,
    conversation_id: str,
    lead_status: str | None,
) -> int:
    """Cancel only on unequivocal WON/LOST/SPAM. Never treats Lead.status as owner."""
    mapped = cancel_reason_for_lead_close(lead_status)
    if mapped is None:
        return 0
    return await cancel_pending_followups(canceller, conversation_id, mapped)


async def send_followup_if_allowed(
    *,
    store: FollowUpSendStore,
    conversations: Any,
    evolution: Any,
    task_id: str,
    phone: str,
    instance: str,
    text: str,
    compose_hook: Any | None = None,
    before_send_hook: Any | None = None,
) -> bool:
    """Claim → compose hook → live ownership + status → send.

    Race hooks are ``async () -> None`` callables (tests use asyncio.Event).
    Returns True only when Evolution send ran and mark_sent succeeded.
    """
    claimed = await store.claim(task_id)
    if claimed is None:
        return False

    if compose_hook is not None:
        await compose_hook()

    if await _abort_send(store, conversations, task_id, claimed):
        return False

    if before_send_hook is not None:
        await before_send_hook()

    if await _abort_send(store, conversations, task_id, claimed):
        return False

    send = getattr(evolution, "send_text", None)
    if send is None:
        return False
    await send(phone, text, instance=instance)

    marked = await store.mark_sent(task_id)
    if not marked:
        # Cancel won the CAS after the stub send started — treat as not sent
        # for ownership: caller must not restore PENDING.
        return False
    return True


async def _abort_send(
    store: FollowUpSendStore,
    conversations: Any,
    task_id: str,
    claimed: Any,
) -> bool:
    conversation_id = str(
        getattr(claimed, "conversation_id", None)
        or (claimed.get("conversation_id") if isinstance(claimed, dict) else "")
        or ""
    )
    live = await store.get(task_id)
    status = _status_of(live if live is not None else claimed)
    bot_status, _rev = await read_live_ownership(conversations, conversation_id)
    if followup_send_blocked(task_status=status, bot_status=bot_status):
        if bot_status == LifecycleStatus.HUMAN_ACTIVE.value and status != (
            FollowUpTaskStatus.CANCELLED.value
        ):
            await store.cancel_for_conversation(
                conversation_id, FollowUpCancelReason.HUMAN_ASSUMED.value
            )
        return True
    if not column_authorizes_outbound(bot_status):
        await store.cancel_for_conversation(
            conversation_id, FollowUpCancelReason.HUMAN_ASSUMED.value
        )
        return True
    return False


def _status_of(task: Any) -> str:
    if task is None:
        return FollowUpTaskStatus.CANCELLED.value
    if isinstance(task, dict):
        return task_status_value(task.get("status"))
    return task_status_value(getattr(task, "status", None))
