"""Live ownership checks so HUMAN_ACTIVE wins races against the worker.

Canonical source of truth is Conversation.botStatus + ownershipRevision
(re-read from the persisted column), never canonicalStateJson lifecycle.
JSON may mirror for dumps/observability; it must not authorize outbound.
Already-confirmed outbound (Evolution send + insert_bot_outbound) stays
valid; remaining unsent bubbles are discarded.

Assume cancels pending FollowUpTask rows (HUMAN_ASSUMED). The repository is
injectable; when a pool exists the Postgres adapter is used. Cancel never DELETE.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from sdr.domain.inbound_batch import BatchResult
from sdr.domain.types import LifecycleStatus
from sdr.infrastructure.followup_repository import CANCEL_REASON_HUMAN_ASSUMED

CancelPendingFn = Callable[[str], Awaitable[None]]

_cancel_pending: CancelPendingFn | None = None
_followup_repository: Any = None

SUPPRESSED_REASON_HUMAN_ACTIVE = "human_active"


def ownership_revision_from_row(row: Any) -> int:
    if row is None:
        return 0
    try:
        return int(row["ownershipRevision"] or 0)
    except Exception:
        return 0


def column_authorizes_outbound(bot_status: str | None) -> bool:
    """Send is allowed only when the persisted column is not HUMAN_ACTIVE.

    JSON lifecycle is ignored here on purpose.
    """
    return bot_status != LifecycleStatus.HUMAN_ACTIVE.value


async def read_live_ownership(
    conversations: Any, conversation_id: str
) -> tuple[str | None, int]:
    """Re-read botStatus + ownershipRevision from the live conversation row."""
    get_by_id = getattr(conversations, "get_by_id", None)
    if get_by_id is not None:
        row = await get_by_id(conversation_id)
        if row is not None:
            try:
                status = row["botStatus"]
            except Exception:
                status = None
            return (
                str(status) if status is not None else None,
                ownership_revision_from_row(row),
            )
    load = getattr(conversations, "load_canonical_state", None)
    if load is not None:
        state = await load(conversation_id)
        if state is not None:
            status = getattr(getattr(state, "lifecycle", None), "status", None)
            value = status.value if status is not None else None
            return value, int(getattr(state, "ownership_revision", 0) or 0)
    return None, 0


async def human_assumed_live(
    conversations: Any, conversation_id: str
) -> tuple[bool, int]:
    status, revision = await read_live_ownership(conversations, conversation_id)
    return not column_authorizes_outbound(status), revision


def set_cancel_pending_automation(fn: CancelPendingFn | None) -> None:
    """Inject a cancel callback (tests / Frente C). ``None`` restores default."""
    global _cancel_pending
    _cancel_pending = fn


def set_followup_repository(repo: Any | None) -> None:
    """Inject the FollowUp store used by ``cancel_pending_automation``."""
    global _followup_repository
    _followup_repository = repo


def _resolve_followup_repository() -> Any | None:
    if _followup_repository is not None:
        return _followup_repository
    try:
        from sdr.db import get_pool
        from sdr.infrastructure.followup_repository import FollowUpRepository
    except Exception:
        return None
    pool = get_pool()
    if pool is None:
        return None
    return FollowUpRepository(pool)


async def cancel_pending_automation(conversation_id: str) -> None:
    """Cancel pending follow-up tasks after assume (HUMAN_ASSUMED). Never DELETE."""
    if _cancel_pending is not None:
        await _cancel_pending(conversation_id)
        return None
    repo = _resolve_followup_repository()
    if repo is None:
        return None
    await repo.cancel_pending_for_conversation(
        conversation_id, reason=CANCEL_REASON_HUMAN_ASSUMED
    )


def suppression_batch_result(
    *,
    ownership_revision: int,
    outbound_texts: list[str] | None = None,
    outbound_sent: bool = False,
    outbound_provider_ids: list[Any] | None = None,
    processed_at: str | None = None,
) -> dict[str, Any]:
    payload = BatchResult(
        outbound_texts=list(outbound_texts or []),
        outbound_sent=bool(outbound_sent),
        outbound_provider_ids=list(outbound_provider_ids or []),
        action="no_reply" if not outbound_sent else None,
        reason_code=SUPPRESSED_REASON_HUMAN_ACTIVE,
        processed_at=processed_at,
    ).to_dict()
    payload["suppressed_reason"] = SUPPRESSED_REASON_HUMAN_ACTIVE
    payload["ownership_revision"] = int(ownership_revision or 0)
    return payload
