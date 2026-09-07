"""Store scheduling helpers — suggest concrete visit slots with exact times.

Uses the injectable commercial clock (America/Sao_Paulo). Labels always include
weekday, date and a clock time — never a vague period alone.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sdr.domain.clock import TZ_BRT, now_brt

STORE_HOURS: dict[int, tuple[int, int] | None] = {
    0: (8, 18),
    1: (8, 18),
    2: (8, 18),
    3: (8, 18),
    4: (8, 18),
    5: (8, 16),  # Saturday until 16h
    6: None,
}

_WEEKDAY_PT = [
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sábado", "domingo",
]
_WEEKDAY_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

# Default concrete hours inside opening hours.
_MORNING_HOUR, _MORNING_MINUTE = 9, 30
_AFTERNOON_HOUR, _AFTERNOON_MINUTE = 14, 0


def _weekday_name(dt: datetime, lang: str) -> str:
    return _WEEKDAY_ES[dt.weekday()] if lang == "es" else _WEEKDAY_PT[dt.weekday()]


def _is_open(dt: datetime) -> bool:
    hours = STORE_HOURS.get(dt.weekday())
    if hours is None:
        return False
    open_h, close_h = hours
    minutes = dt.hour * 60 + dt.minute
    return open_h * 60 <= minutes < close_h * 60


def _next_open_day(start: datetime) -> datetime | None:
    for offset in range(14):
        candidate = start + timedelta(days=offset)
        if STORE_HOURS.get(candidate.weekday()) is not None:
            return candidate.replace(hour=0, minute=0, second=0, microsecond=0)
    return None


def format_slot_datetime(dt: datetime, lang: str = "pt") -> str:
    weekday = _weekday_name(dt, lang)
    time_label = f"{dt.hour}h" if dt.minute == 0 else f"{dt.hour}h{dt.minute:02d}"
    if lang == "es":
        return f"{weekday}, {dt.day}/{dt.month:02d}, a las {time_label}"
    return f"{weekday}, {dt.day}/{dt.month:02d} às {time_label}"


def _slot_at(day: datetime, hour: int, minute: int) -> datetime | None:
    hours = STORE_HOURS.get(day.weekday())
    if hours is None:
        return None
    open_h, close_h = hours
    candidate = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate.hour < open_h:
        candidate = day.replace(hour=open_h, minute=0, second=0, microsecond=0)
    if candidate.hour >= close_h:
        return None
    return candidate


def suggest_visit_datetimes(
    now: datetime | None = None,
    tz: str = "America/Sao_Paulo",
    *,
    prefer_saturday: bool = False,
) -> list[datetime]:
    """Return two concrete in-store datetimes."""
    tz_obj = ZoneInfo(tz) if tz else TZ_BRT
    if now is None:
        now = now_brt()
    elif now.tzinfo is None:
        now = now.replace(tzinfo=tz_obj)
    else:
        now = now.astimezone(tz_obj)

    slots: list[datetime] = []

    if prefer_saturday:
        cursor = now
        for _ in range(14):
            if cursor.weekday() == 5:
                morning = _slot_at(cursor, _MORNING_HOUR, _MORNING_MINUTE)
                afternoon = _slot_at(cursor, min(_AFTERNOON_HOUR, 14), 0)
                if morning and morning > now:
                    slots.append(morning)
                elif morning and cursor.date() > now.date():
                    slots.append(morning)
                if afternoon and afternoon > now:
                    slots.append(afternoon)
                break
            cursor = cursor + timedelta(days=1)
            cursor = cursor.replace(hour=0, minute=0, second=0, microsecond=0)
        return slots[:2]

    if now.hour < 12:
        today_afternoon = _slot_at(now, _AFTERNOON_HOUR, _AFTERNOON_MINUTE)
        if today_afternoon and today_afternoon > now:
            slots.append(today_afternoon)
        tomorrow = _next_open_day(now + timedelta(days=1))
        if tomorrow:
            morning = _slot_at(tomorrow, _MORNING_HOUR, _MORNING_MINUTE)
            if morning:
                slots.append(morning)
            if len(slots) < 2:
                afternoon = _slot_at(tomorrow, _AFTERNOON_HOUR, _AFTERNOON_MINUTE)
                if afternoon:
                    slots.append(afternoon)
    else:
        tomorrow = _next_open_day(now + timedelta(days=1))
        if tomorrow:
            morning = _slot_at(tomorrow, _MORNING_HOUR, _MORNING_MINUTE)
            afternoon = _slot_at(tomorrow, _AFTERNOON_HOUR, _AFTERNOON_MINUTE)
            if morning:
                slots.append(morning)
            if afternoon:
                slots.append(afternoon)
            if len(slots) < 2:
                nxt = _next_open_day(tomorrow + timedelta(days=1))
                if nxt:
                    extra = _slot_at(nxt, _MORNING_HOUR, _MORNING_MINUTE)
                    if extra:
                        slots.append(extra)

    seen: set[str] = set()
    unique: list[datetime] = []
    for s in slots:
        key = s.isoformat()
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique[:2]


def suggest_visit_slots(
    now: datetime | None = None,
    tz: str = "America/Sao_Paulo",
    lang: str = "pt",
    *,
    prefer_saturday: bool = False,
) -> list[str]:
    """Return 2 concrete visit slot labels with weekday + exact time."""
    datetimes = suggest_visit_datetimes(now, tz, prefer_saturday=prefer_saturday)
    return [format_slot_datetime(dt, lang) for dt in datetimes]


def format_slot_suggestion(slots: list[str], lang: str = "pt") -> str:
    """Format slot list as a natural language suggestion."""
    if not slots:
        return (
            "Qual dia e horário fica melhor pra você passar na loja?"
            if lang != "es"
            else "¿Qué día y horario te queda mejor para pasar?"
        )
    vendor_note = (
        "O horário fica pendente de confirmação do vendedor."
        if lang != "es"
        else "El horario queda pendiente de confirmación del vendedor."
    )
    if len(slots) == 1:
        lead = f"Que tal {slots[0]}?" if lang != "es" else f"¿Qué tal el {slots[0]}?"
        return f"{lead} {vendor_note}"
    if lang == "es":
        return f"¿Qué tal el {slots[0]}, o el {slots[1]}? {vendor_note}"
    return f"Que tal {slots[0]} ou {slots[1]}? {vendor_note}"


def is_concrete_visit_slot(text: str | None) -> bool:
    """True when the label includes an exact clock time (e.g. 14h, 9h30)."""
    if not text or not str(text).strip():
        return False
    return bool(re.search(r"\d{1,2}\s*h", str(text), re.I))


def resolve_slot_choice(
    text: str,
    offered: list[str],
    *,
    now: datetime | None = None,
) -> str | None:
    """Map a customer reply onto an offered slot or a saturday preference."""
    if not text:
        return None
    low = text.lower()
    if offered:
        if any(p in low for p in ("primeiro", "a primeira", "1º", "opção 1", "opcao 1")):
            return offered[0]
        if any(p in low for p in ("segundo", "a segunda", "2º", "opção 2", "opcao 2")):
            if len(offered) > 1:
                return offered[1]
        for slot in offered:
            slot_low = slot.lower()
            # Match weekday token present in the slot label.
            for day in _WEEKDAY_PT:
                if day in low and day in slot_low:
                    if "manhã" in low or "manha" in low:
                        if "9h" in slot_low or "8h" in slot_low or "10h" in slot_low:
                            return slot
                    if "tarde" in low or "14h" in low:
                        if "14h" in slot_low or "15h" in slot_low:
                            return slot
                    return slot
            if "14h" in low and "14h" in slot_low:
                return slot
            if "9h" in low and "9h" in slot_low:
                return slot
    if "sábado" in low or "sabado" in low:
        sat = suggest_visit_slots(now, prefer_saturday=True)
        if not sat:
            return None
        if "tarde" in low and len(sat) > 1:
            return sat[-1]
        if "manhã" in low or "manha" in low:
            return sat[0]
        # Day-only: do not lock a slot — Decision must offer two Saturday times.
        return None
    return None
