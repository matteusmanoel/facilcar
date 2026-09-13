"""Quiet window is protocol timing, not product-term heuristics.

First contact uses the same window as later turns so a 6s burst is one batch.
"""

from sdr.debounce import dynamic_debounce_ms, quiet_window_ms
from sdr.config import Settings


def test_quiet_window_does_not_shorten_first_contact() -> None:
    settings = Settings(sdr_debounce_ms=8000, sdr_debounce_max_ms=20000)
    first = dynamic_debounce_ms(0, settings=settings)
    later = dynamic_debounce_ms(3, settings=settings)
    assert first == later == 8000
    assert quiet_window_ms(settings=settings) == 8000


def test_window_follows_configured_base() -> None:
    settings = Settings(sdr_debounce_ms=8000, sdr_debounce_max_ms=20000)
    assert dynamic_debounce_ms(99, base_ms=8000, settings=settings) == 8000
    assert dynamic_debounce_ms(0, base_ms=5000, settings=settings) == 5000
