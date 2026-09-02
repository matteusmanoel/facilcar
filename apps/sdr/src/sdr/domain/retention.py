"""Retention helpers for SdrDocument — dry-run safe, no auto-delete scheduler in MVP."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def compute_expires_at(
    *,
    retention_policy: str,
    created_at: datetime | None = None,
    lead_status: str | None = None,
) -> datetime | None:
    """Return expiry timestamp or None for permanent retention.

    WON leads → permanent (None).
    DAYS_180 / non-WON → created_at + 180 days.
    """
    if lead_status == "WON" or retention_policy == "PERMANENT":
        return None
    base = created_at or datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return base + timedelta(days=180)


def should_purge(
    *,
    retention_policy: str,
    expires_at: datetime | None,
    lead_status: str | None,
    now: datetime | None = None,
) -> bool:
    if lead_status == "WON" or retention_policy == "PERMANENT":
        return False
    if expires_at is None:
        return False
    current = now or datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current >= expires_at
