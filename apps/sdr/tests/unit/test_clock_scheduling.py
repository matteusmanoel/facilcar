"""Injectable clock and concrete visit slots."""

from __future__ import annotations

from sdr.domain.clock import GOLDEN_CLOCK_ISO, set_clock
from sdr.domain.scheduling import (
    is_concrete_visit_slot,
    resolve_slot_choice,
    suggest_visit_slots,
)


def setup_function() -> None:
    set_clock(GOLDEN_CLOCK_ISO)


def teardown_function() -> None:
    set_clock(None)


def test_weekday_slots_are_exact_hours() -> None:
    slots = suggest_visit_slots()
    assert len(slots) == 2
    assert all(is_concrete_visit_slot(s) for s in slots)
    joined = " ".join(slots).lower()
    assert "14h" in joined
    assert "9h30" in joined
    assert "manhã" not in joined or "9h" in joined


def test_saturday_slots_stay_within_hours() -> None:
    slots = suggest_visit_slots(prefer_saturday=True)
    assert len(slots) == 2
    assert all("sábado" in s.lower() for s in slots)
    assert all(is_concrete_visit_slot(s) for s in slots)
    assert all("17h" not in s and "18h" not in s for s in slots)


def test_resolve_second_option_and_fourteen() -> None:
    slots = suggest_visit_slots()
    assert resolve_slot_choice("prefiro o segundo horário", slots) == slots[1]
    chosen = resolve_slot_choice("pode ser às 14h", slots)
    assert chosen is not None
    assert "14h" in chosen


def test_saturday_day_only_does_not_lock_slot() -> None:
    slots = suggest_visit_slots()
    assert resolve_slot_choice("seria possível no sábado?", slots) is None
    morning = resolve_slot_choice("sábado de manhã", [])
    assert morning is not None
    assert "sábado" in morning.lower()
    assert is_concrete_visit_slot(morning)
