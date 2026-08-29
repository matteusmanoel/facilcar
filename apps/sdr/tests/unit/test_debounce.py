"""Dynamic quiet window is protocol, not product-term heuristics."""

from sdr.debounce import dynamic_debounce_ms


def test_first_contact_is_shorter_than_later_turns() -> None:
    first = dynamic_debounce_ms(0, base_ms=1500)
    later = dynamic_debounce_ms(3, base_ms=1500)
    assert first <= 1200
    assert later > first
    assert later <= 4500


def test_window_is_capped() -> None:
    assert dynamic_debounce_ms(99, base_ms=1500) <= 4500
