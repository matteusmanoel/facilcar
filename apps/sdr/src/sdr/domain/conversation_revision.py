"""Conversation context revision — inbound CAS, not a test sentinel.

``Conversation.contextRevision`` increments on customer inbound.
Follow-up tasks capture the live column at create time. ``0`` / ``None``
never authorize compose or send.
"""

from __future__ import annotations

from typing import Any

MIN_CONTEXT_REVISION = 1


def bump_context_revision(state: Any) -> int:
    """Increment after a customer inbound. Returns the new revision (≥ 1)."""
    current = int(getattr(state, "context_revision", 0) or 0)
    state.context_revision = current + 1
    return int(state.context_revision)


def context_revision_is_usable(revision: int | None) -> bool:
    if revision is None:
        return False
    try:
        return int(revision) >= MIN_CONTEXT_REVISION
    except (TypeError, ValueError):
        return False
