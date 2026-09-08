"""Live ownership checks so HUMAN_ACTIVE wins races against the worker.

Canonical source of truth is Conversation.botStatus (re-read from DB), never
a stale worker seed. Already-confirmed outbound (Evolution send +
insert_bot_outbound) stays valid; remaining unsent bubbles are discarded.

Follow-up scheduler is Phase 11. ``cancel_pending_automation`` is the no-op
seam to cancel pending automation after assume — do not create a scheduler here.
"""

from __future__ import annotations

from typing import Any

from sdr.domain.inbound_batch import BatchResult
from sdr.domain.types import LifecycleStatus

SUPPRESSED_REASON_HUMAN_ACTIVE = "human_active"


def ownership_revision_from_row(row: Any) -> int:
    if row is None:
        return 0
    try:
        return int(row["ownershipRevision"] or 0)
    except Exception:
        return 0


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
    return status == LifecycleStatus.HUMAN_ACTIVE.value, revision


async def cancel_pending_automation(_conversation_id: str) -> None:
    """Phase 11 hook: cancel a pending follow-up/automation job after assume.

    No scheduler exists in this phase — this is an explicit no-op contract.
    """
    return None


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
