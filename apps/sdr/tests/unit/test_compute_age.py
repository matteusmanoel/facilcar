"""Phase 5 — derived age from birth date using the commercial BRT clock."""

from __future__ import annotations

from datetime import date

from sdr.domain.age import compute_age
from sdr.domain.clock import set_clock


def setup_function() -> None:
    set_clock(None)


def teardown_function() -> None:
    set_clock(None)


def test_birthday_today_counts() -> None:
    set_clock("2026-09-08T10:00:00-03:00")
    assert compute_age("08/09/1994") == 32
    assert compute_age("1994-09-08") == 32


def test_eve_of_birthday() -> None:
    set_clock("2026-09-07T10:00:00-03:00")
    assert compute_age("08/09/1994") == 31


def test_leap_day_non_leap_year() -> None:
    set_clock("2025-02-28T12:00:00-03:00")
    assert compute_age("2000-02-29") == 24
    set_clock("2025-03-01T12:00:00-03:00")
    assert compute_age("29/02/2000") == 25


def test_leap_day_on_leap_birthday() -> None:
    set_clock("2024-02-29T12:00:00-03:00")
    assert compute_age("2000-02-29") == 24


def test_invalid_and_missing() -> None:
    set_clock("2026-09-08T10:00:00-03:00")
    assert compute_age(None) is None
    assert compute_age("") is None
    assert compute_age("31/02/1990") is None
    assert compute_age("not-a-date") is None
    assert compute_age("2026-13-40") is None
    assert compute_age("29/02/2023") is None


def test_explicit_today_overrides_clock() -> None:
    set_clock("2026-01-01T00:00:00-03:00")
    assert compute_age("1994-09-08", today=date(2026, 9, 8)) == 32
