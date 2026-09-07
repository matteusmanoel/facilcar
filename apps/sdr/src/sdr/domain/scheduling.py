"""Store scheduling helpers — suggest concrete visit slots.

Computes human-readable time proposals based on store hours and the
current moment, eliminating "Qual dia funciona para você?" back-and-forth.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Store opening hours by ISO weekday (Monday=0 … Sunday=6).
# Value is (open_hour, close_hour) in 24h, or None if closed.
STORE_HOURS: dict[int, tuple[int, int] | None] = {
    0: (8, 18),   # Monday
    1: (8, 18),   # Tuesday
    2: (8, 18),   # Wednesday
    3: (8, 18),   # Thursday
    4: (8, 18),   # Friday
    5: (8, 16),   # Saturday
    6: None,      # Sunday — closed
}

_WEEKDAY_PT = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
_WEEKDAY_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

_PERIOD_MORNING_PT = "de manhã"
_PERIOD_AFTERNOON_PT = "à tarde"
_PERIOD_MORNING_ES = "por la mañana"
_PERIOD_AFTERNOON_ES = "por la tarde"


def _is_morning(hour: int) -> bool:
    return hour < 12


def _next_open_day(start: datetime) -> datetime | None:
    """Return the next open day starting from `start` (inclusive), or None if >14 days away."""
    for offset in range(14):
        candidate = start + timedelta(days=offset)
        if STORE_HOURS.get(candidate.weekday()) is not None:
            return candidate
    return None


def _slot_label(dt: datetime, period: str, lang: str) -> str:
    weekday = _WEEKDAY_PT[dt.weekday()] if lang != "es" else _WEEKDAY_ES[dt.weekday()]
    day = dt.day
    month = dt.month
    return f"{weekday}, {day}/{month:02d}, {period}"


def suggest_visit_slots(
    now: datetime | None = None,
    tz: str = "America/Sao_Paulo",
    lang: str = "pt",
) -> list[str]:
    """Return 2 concrete visit slot labels (human-readable).

    Logic:
    - If now is morning (before 12h): suggest today afternoon + tomorrow morning.
    - If now is afternoon/evening: suggest tomorrow morning + tomorrow afternoon.
    - Skip closed days (Sunday). Roll forward to the next open day.
    - Saturday closes at 16h, so afternoon slot uses "pela manhã" on Saturday.
    """
    tz_obj = ZoneInfo(tz)
    if now is None:
        now = datetime.now(tz_obj)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=tz_obj)

    is_es = lang == "es"
    morning_label = _PERIOD_MORNING_ES if is_es else _PERIOD_MORNING_PT
    afternoon_label = _PERIOD_AFTERNOON_ES if is_es else _PERIOD_AFTERNOON_PT

    slots: list[str] = []

    if _is_morning(now.hour):
        # Slot 1: today afternoon (if store closes after 14h)
        today_hours = STORE_HOURS.get(now.weekday())
        if today_hours and today_hours[1] > 14:
            slots.append(_slot_label(now, afternoon_label, lang))
        # Slot 2: tomorrow morning
        tomorrow = _next_open_day(now + timedelta(days=1))
        if tomorrow:
            slots.append(_slot_label(tomorrow, morning_label, lang))
    else:
        # Slot 1: next open day morning
        tomorrow = _next_open_day(now + timedelta(days=1))
        if tomorrow:
            slots.append(_slot_label(tomorrow, morning_label, lang))
        # Slot 2: same day afternoon if still open, else day after morning
        if tomorrow:
            tomorrow_hours = STORE_HOURS.get(tomorrow.weekday())
            if tomorrow_hours and tomorrow_hours[1] > 14:
                slots.append(_slot_label(tomorrow, afternoon_label, lang))
            else:
                day_after = _next_open_day(tomorrow + timedelta(days=1))
                if day_after:
                    slots.append(_slot_label(day_after, morning_label, lang))

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for s in slots:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique[:2]


def format_slot_suggestion(slots: list[str], lang: str = "pt") -> str:
    """Format slot list as a natural language suggestion."""
    if not slots:
        return "Qual dia e horário fica melhor pra você passar na loja?" if lang != "es" else "¿Qué día y horario te queda mejor para pasar?"
    if len(slots) == 1:
        return (
            f"Que tal {slots[0]}?"
            if lang != "es"
            else f"¿Qué tal el {slots[0]}?"
        )
    if lang == "es":
        return f"¿Qué tal el {slots[0]}, o el {slots[1]}?"
    return f"Que tal {slots[0]} ou {slots[1]}?"
