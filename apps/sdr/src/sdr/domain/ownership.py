"""Conversation ownership — human assume / AI resume.

Handoff is an idempotent commercial event, not automation shutdown.
Canonical source of truth: Conversation.botStatus + ownershipRevision
(Postgres columns). canonicalStateJson.lifecycle may mirror for
observability; it must never authorize outbound or flip owner/status
on load (column overlay in conversation_repository).
Lead.status is never mutated here.
"""

from __future__ import annotations

from sdr.domain.clock import now_brt
from sdr.domain.types import ConversationCanonicalState, LifecycleStatus

_HANDOFF_SENT_STATUSES = frozenset({
    LifecycleStatus.HANDOFF_SENT,
    LifecycleStatus.HUMAN_ACTIVE,
    LifecycleStatus.AI_RESUMED,
})


class StaleOwnershipRevision(Exception):
    """CAS failed — caller held an outdated ownershipRevision."""


class OwnershipConflict(Exception):
    """A different human already owns HUMAN_ACTIVE on this conversation."""


def _stamp() -> str:
    return now_brt().isoformat()


def handoff_sent(state: ConversationCanonicalState, *, handoff_at: str | None = None) -> bool:
    """Vendor has been notified (status or persisted handoffAt)."""
    if state.lifecycle.status in _HANDOFF_SENT_STATUSES:
        return True
    return bool(handoff_at or state.handoff_at)


def automation_enabled(state: ConversationCanonicalState) -> bool:
    return state.lifecycle.status != LifecycleStatus.HUMAN_ACTIVE


def human_active(state: ConversationCanonicalState) -> bool:
    return state.lifecycle.status == LifecycleStatus.HUMAN_ACTIVE


def vendor_already_notified(state: ConversationCanonicalState) -> bool:
    """True after the handoff event — do not send HANDOFF_VENDOR again."""
    return state.lifecycle.status in (
        LifecycleStatus.HANDOFF_SENT,
        LifecycleStatus.AI_RESUMED,
    )


def assume_human(
    state: ConversationCanonicalState,
    *,
    actor_user_id: str,
    expected_revision: int,
) -> ConversationCanonicalState:
    """HANDOFF_SENT (or any non-human status) → HUMAN_ACTIVE with CAS revision."""
    if expected_revision != state.ownership_revision:
        raise StaleOwnershipRevision(
            f"expected ownershipRevision={expected_revision}, "
            f"current={state.ownership_revision}"
        )
    if state.lifecycle.status == LifecycleStatus.HUMAN_ACTIVE:
        if state.assumed_by_user_id == actor_user_id:
            return state
        raise OwnershipConflict(
            f"conversation already assumed by {state.assumed_by_user_id}"
        )
    state.lifecycle.status = LifecycleStatus.HUMAN_ACTIVE
    state.ownership_revision = state.ownership_revision + 1
    state.assumed_by_user_id = actor_user_id
    state.assumed_at = _stamp()
    return state


def resume_ai(
    state: ConversationCanonicalState,
    *,
    actor_user_id: str,
    reason: str,
    expected_revision: int,
) -> ConversationCanonicalState:
    """HUMAN_ACTIVE → AI_RESUMED. Does not clear assignment, summary, or QUALIFIED."""
    if expected_revision != state.ownership_revision:
        raise StaleOwnershipRevision(
            f"expected ownershipRevision={expected_revision}, "
            f"current={state.ownership_revision}"
        )
    if state.lifecycle.status == LifecycleStatus.AI_RESUMED:
        if state.resumed_by_user_id == actor_user_id:
            return state
        raise OwnershipConflict(
            f"conversation already resumed by {state.resumed_by_user_id}"
        )
    if state.lifecycle.status != LifecycleStatus.HUMAN_ACTIVE:
        raise OwnershipConflict(
            f"resume requires HUMAN_ACTIVE, current={state.lifecycle.status.value}"
        )
    state.lifecycle.status = LifecycleStatus.AI_RESUMED
    state.ownership_revision = state.ownership_revision + 1
    state.resumed_by_user_id = actor_user_id
    state.resumed_at = _stamp()
    state.resume_reason = reason
    return state
