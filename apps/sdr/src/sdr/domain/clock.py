"""Injectable commercial clock — timezone America/Sao_Paulo.

Golden scenarios and scheduling must not depend on the wall clock of the
machine running the tests. Call ``set_clock`` to freeze time; ``now_brt``
returns that instant or the real local time.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

TZ_BRT = ZoneInfo("America/Sao_Paulo")

_fixed: datetime | None = None

# Canonical freeze for the 17-scenario LLM round.
GOLDEN_CLOCK_ISO = "2026-09-07T10:00:00-03:00"


def parse_clock(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ_BRT)
    return dt.astimezone(TZ_BRT)


def set_clock(value: str | datetime | None) -> datetime | None:
    """Freeze or clear the commercial clock. Returns the resolved instant."""
    global _fixed
    _fixed = parse_clock(value)
    return _fixed


def now_brt() -> datetime:
    if _fixed is not None:
        return _fixed
    return datetime.now(TZ_BRT)
