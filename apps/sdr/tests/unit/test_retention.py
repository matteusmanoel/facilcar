from datetime import datetime, timezone

from sdr.domain.retention import compute_expires_at, should_purge


def test_won_is_permanent() -> None:
    assert compute_expires_at(retention_policy="DAYS_180", lead_status="WON") is None
    assert should_purge(
        retention_policy="DAYS_180",
        expires_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
        lead_status="WON",
    ) is False


def test_180_days_expiry() -> None:
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    exp = compute_expires_at(retention_policy="DAYS_180", created_at=created)
    assert exp is not None
    assert exp.day == 30 and exp.month == 6  # 2026-01-01 + 180d ≈ Jun 30
    assert should_purge(
        retention_policy="DAYS_180",
        expires_at=exp,
        lead_status="LOST",
        now=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )
