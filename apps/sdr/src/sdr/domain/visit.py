"""Visit preference — commercial opportunity, not a calendar booking.

Structured separately from handoff. Exact clock time is never required to
close. Customer copy must not expose vendor-confirmation process.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from sdr.domain.clock import TZ_BRT, now_brt
from sdr.domain.display_name import display_first_name
from sdr.domain.scheduling import (
    STORE_HOURS,
    format_slot_datetime,
    resolve_slot_choice,
)

PERIOD_MORNING = "morning"
PERIOD_AFTERNOON = "afternoon"
PERIOD_EVENING = "evening"

_WEEKDAY_PT = [
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
]

_COURTESY = re.compile(
    r"\b(?:obrigad[oa]|valeu|agrade[cç]o|por\s+nada|qualquer\s+coisa\s+eu\s+aviso)\b",
    re.I,
)
_DECLINE = re.compile(
    r"\b(?:n[aã]o\s+consigo(?:\s+ir)?|agora\s+n[aã]o|n[aã]o\s+posso\s+ir|"
    r"n[aã]o\s+vou\s+(?:conseguir|poder)|essa\s+semana\s+n[aã]o|"
    r"n[aã]o\s+d[aá]\s+(?:pra|para)\s+ir|sem\s+tempo)\b",
    re.I,
)
_INTEREST = re.compile(
    r"\b(?:quero\s+ir|vou\s+(?:a[ií]|na\s+loja|conhecer|ver)|"
    r"visita|passar\s+(?:a[ií]|na\s+loja)|conhecer\s+o\s+(?:carro|ve[ií]culo))\b",
    re.I,
)
_TODAY = re.compile(r"\bhoje\b", re.I)
_TOMORROW = re.compile(r"\bamanh[ãa]\b", re.I)
_DAY_AFTER = re.compile(r"\bdepois\s+de\s+amanh[ãa]\b", re.I)
_NUMERIC_DATE = re.compile(
    r"\b(\d{1,2})[\/\-](\d{1,2})(?:[\/\-](\d{2,4}))?\b",
)
_TIME = re.compile(
    r"\b(?:[aà]s\s+)?(\d{1,2})\s*(?:h|:)\s*(\d{2})?\b",
    re.I,
)
_PERIOD_MORNING = re.compile(
    r"\b(?:manh[ãa]|cedinho|de\s+manh[ãa]|in[ií]cio\s+do\s+dia)\b",
    re.I,
)
_PERIOD_AFTERNOON = re.compile(
    r"\b(?:tarde|depois\s+do\s+almo[cç]o|fim\s+do\s+dia|final\s+do\s+dia)\b",
    re.I,
)
_PERIOD_EVENING = re.compile(r"\b(?:noite|fim\s+de\s+tarde)\b", re.I)
_ORDINAL_FIRST = re.compile(
    r"\b(?:primeiro|a\s+primeira|1[oº°]|op[cç][aã]o\s*1|primeiro\s+hor[aá]rio)\b",
    re.I,
)
_ORDINAL_SECOND = re.compile(
    r"\b(?:segundo|a\s+segunda|2[oº°]|op[cç][aã]o\s*2|segundo\s+hor[aá]rio)\b",
    re.I,
)
_WEEKDAY = re.compile(
    r"\b(segunda|ter[cç]a|quarta|quinta|sexta|s[áa]bado|domingo)(?:[\s-]feira)?\b",
    re.I,
)
FORBIDDEN_CUSTOMER_PHRASES = (
    "confirmação do vendedor",
    "confirmacao do vendedor",
    "aguardando vendedor",
    "handoff",
    "triagem",
    "agenda do vendedor",
)
_WEEKDAY_INDEX = {
    "segunda": 0,
    "terca": 1,
    "terça": 1,
    "quarta": 2,
    "quinta": 3,
    "sexta": 4,
    "sabado": 5,
    "sábado": 5,
    "domingo": 6,
}


@dataclass(frozen=True, slots=True)
class VisitUtterance:
    """One inbound interpreted against offered slots and the commercial clock."""

    courtesy: bool = False
    declined: bool = False
    interest: bool = False
    accepted_offered: bool = False
    offered_index: int | None = None
    date: date | None = None
    period: str | None = None
    time: time | None = None
    raw: str = ""
    display: str | None = None
    within_store_hours: bool | None = None


def is_open_datetime(dt: datetime) -> bool:
    hours = STORE_HOURS.get(dt.weekday())
    if hours is None:
        return False
    open_h, close_h = hours
    minutes = dt.hour * 60 + dt.minute
    return open_h * 60 <= minutes < close_h * 60


def is_open_date(day: date) -> bool:
    return STORE_HOURS.get(day.weekday()) is not None


def _fold(text: str) -> str:
    return (text or "").strip()


def _weekday_index(token: str) -> int | None:
    key = token.lower().replace("ç", "c")
    key = key.split("-")[0].split()[0]
    return _WEEKDAY_INDEX.get(key) or _WEEKDAY_INDEX.get(token.lower())


def _next_weekday(now: datetime, weekday: int) -> date:
    delta = (weekday - now.weekday()) % 7
    if delta == 0:
        delta = 7
    return (now + timedelta(days=delta)).date()


def _parse_time(text: str) -> time | None:
    match = _TIME.search(text)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    if hour > 23 or minute > 59:
        return None
    return time(hour, minute)


def _parse_date(text: str, now: datetime) -> date | None:
    if _DAY_AFTER.search(text):
        return (now + timedelta(days=2)).date()
    if _TOMORROW.search(text):
        return (now + timedelta(days=1)).date()
    if _TODAY.search(text):
        return now.date()
    numeric = _NUMERIC_DATE.search(text)
    if numeric:
        day = int(numeric.group(1))
        month = int(numeric.group(2))
        year_raw = numeric.group(3)
        year = now.year if not year_raw else int(year_raw)
        if year < 100:
            year += 2000
        try:
            return date(year, month, day)
        except ValueError:
            return None
    weekday_m = _WEEKDAY.search(text)
    if weekday_m:
        idx = _weekday_index(weekday_m.group(1))
        if idx is not None:
            if idx == now.weekday() and _TODAY.search(text):
                return now.date()
            return _next_weekday(now, idx)
    return None


def _parse_period(text: str) -> str | None:
    if _PERIOD_EVENING.search(text):
        return PERIOD_EVENING
    if _PERIOD_AFTERNOON.search(text):
        return PERIOD_AFTERNOON
    if _PERIOD_MORNING.search(text):
        return PERIOD_MORNING
    return None


def _within_hours(day: date | None, clock: time | None, period: str | None) -> bool | None:
    if day is None:
        if clock is None:
            return None
        return None
    if clock is not None:
        dt = datetime(
            day.year, day.month, day.day, clock.hour, clock.minute, tzinfo=TZ_BRT
        )
        return is_open_datetime(dt)
    if not is_open_date(day):
        return False
    if period == PERIOD_EVENING:
        hours = STORE_HOURS.get(day.weekday())
        if hours is None:
            return False
        return hours[1] > 17
    return True


def _display(
    *,
    now: datetime,
    day: date | None,
    clock: time | None,
    period: str | None,
    offered_label: str | None,
) -> str | None:
    if offered_label:
        return offered_label
    if day is None and clock is None and period is None:
        return None
    rel = None
    if day is not None:
        if day == now.date():
            rel = "hoje"
        elif day == (now + timedelta(days=1)).date():
            rel = "amanhã"
        else:
            rel = f"{_WEEKDAY_PT[day.weekday()]}, {day.day}/{day.month:02d}"
            if clock is not None:
                dt = datetime(
                    day.year, day.month, day.day, clock.hour, clock.minute, tzinfo=TZ_BRT
                )
                return format_slot_datetime(dt, "pt")
    bits: list[str] = []
    if rel:
        bits.append(rel)
    if clock is not None:
        label = f"{clock.hour}h" if clock.minute == 0 else f"{clock.hour}h{clock.minute:02d}"
        bits.append(f"às {label}")
    elif period == PERIOD_MORNING:
        bits.append("de manhã")
    elif period == PERIOD_AFTERNOON:
        bits.append("à tarde")
    elif period == PERIOD_EVENING:
        bits.append("à noite")
    return " ".join(bits).strip() or None


def parse_visit_utterance(
    text: str,
    offered: list[str] | None = None,
    *,
    now: datetime | None = None,
) -> VisitUtterance:
    raw = _fold(text)
    if not raw:
        return VisitUtterance()
    instant = now or now_brt()
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=TZ_BRT)
    else:
        instant = instant.astimezone(TZ_BRT)

    courtesy = bool(_COURTESY.search(raw))
    declined = bool(_DECLINE.search(raw))
    interest = bool(_INTEREST.search(raw)) or bool(_TOMORROW.search(raw)) or bool(
        _TODAY.search(raw)
    )

    slots = [s for s in (offered or []) if str(s).strip()]
    offered_index: int | None = None
    accepted = False
    chosen_label: str | None = None
    if slots:
        if _ORDINAL_FIRST.search(raw):
            offered_index = 0
            chosen_label = slots[0]
            accepted = True
        elif _ORDINAL_SECOND.search(raw) and len(slots) > 1:
            offered_index = 1
            chosen_label = slots[1]
            accepted = True
        else:
            mapped = resolve_slot_choice(raw, slots, now=instant)
            if mapped:
                accepted = True
                chosen_label = mapped
                try:
                    offered_index = slots.index(mapped)
                except ValueError:
                    offered_index = None

    day = _parse_date(raw, instant)
    clock = _parse_time(raw)
    period = _parse_period(raw)

    if chosen_label:
        if day is None:
            day = _parse_date(chosen_label, instant)
        if clock is None:
            clock = _parse_time(chosen_label)

    if declined:
        interest = False
        accepted = False
        chosen_label = None

    if courtesy and not accepted and day is None and clock is None and period is None:
        interest = False

    within = None if declined else _within_hours(day, clock, period)
    display = None if declined else _display(
        now=instant,
        day=day,
        clock=clock,
        period=period,
        offered_label=chosen_label,
    )

    if accepted or day is not None or clock is not None or period is not None:
        interest = True

    return VisitUtterance(
        courtesy=courtesy and not accepted and not declined,
        declined=declined,
        interest=interest,
        accepted_offered=accepted,
        offered_index=offered_index,
        date=day,
        period=period if clock is None else None,
        time=clock,
        raw=raw,
        display=display,
        within_store_hours=within,
    )


def has_visit_preference(state: Any) -> bool:
    if getattr(state, "visit_date", None) or getattr(state, "visit_time", None):
        return True
    if getattr(state, "visit_period", None):
        return True
    if getattr(state, "visit_preferred_time", None):
        return True
    return False


def apply_visit_utterance(state: Any, parsed: VisitUtterance) -> None:
    """Merge a parsed utterance into canonical state. Idempotent for same values."""
    state.visit_courtesy = bool(parsed.courtesy)
    state.visit_declined_this_turn = bool(parsed.declined)
    if parsed.declined:
        state.visit_declined = True
        return
    if parsed.interest:
        state.visit_interest = True
    if parsed.accepted_offered:
        state.visit_accepted_offered = True
    if parsed.date is not None:
        state.visit_date = parsed.date.isoformat()
    if parsed.period is not None:
        state.visit_period = parsed.period
    if parsed.time is not None:
        state.visit_time = parsed.time.strftime("%H:%M")
        state.visit_period = None
    if parsed.raw:
        state.visit_raw = parsed.raw
    if parsed.within_store_hours is not None:
        state.visit_within_hours = parsed.within_store_hours
    if parsed.display:
        state.visit_preferred_time = parsed.display
    elif parsed.interest and not state.visit_preferred_time:
        state.visit_preferred_time = parsed.raw or "visita"


def apply_visit_from_inbound(
    state: Any,
    inbound_text: str,
    *,
    now: datetime | None = None,
) -> VisitUtterance:
    parsed = parse_visit_utterance(
        inbound_text,
        list(getattr(state, "offered_visit_slots", None) or []),
        now=now,
    )
    apply_visit_utterance(state, parsed)
    return parsed


def relative_when(state: Any, *, now: datetime | None = None) -> str | None:
    instant = now or now_brt()
    day_s = getattr(state, "visit_date", None)
    if not day_s:
        return getattr(state, "visit_preferred_time", None)
    try:
        day = date.fromisoformat(str(day_s))
    except ValueError:
        return getattr(state, "visit_preferred_time", None)
    if day == instant.date():
        base = "hoje"
    elif day == (instant + timedelta(days=1)).date():
        base = "amanhã"
    else:
        base = getattr(state, "visit_preferred_time", None) or f"{day.day}/{day.month:02d}"
    clock_s = getattr(state, "visit_time", None)
    period = getattr(state, "visit_period", None)
    if clock_s:
        hour, minute = (int(p) for p in str(clock_s).split(":"))
        label = f"{hour}h" if minute == 0 else f"{hour}h{minute:02d}"
        if base in {"hoje", "amanhã"}:
            return f"{base} às {label}"
        preferred = getattr(state, "visit_preferred_time", None)
        if preferred:
            return preferred
        return f"{base} às {label}"
    if period == PERIOD_MORNING:
        return f"{base} de manhã"
    if period == PERIOD_AFTERNOON:
        return f"{base} à tarde"
    return base


def customer_copy_leaks_process(text: str) -> bool:
    low = (text or "").lower()
    return any(token in low for token in FORBIDDEN_CUSTOMER_PHRASES)


def _vehicle_label(state: Any) -> str:
    facts = getattr(state, "facts", None)
    if not isinstance(facts, dict):
        return "o veículo"
    vehicle = facts.get("desired_model") or facts.get("desired_vehicle_text")
    if isinstance(vehicle, str) and vehicle.strip():
        return vehicle.strip()
    return "o veículo"


def visit_confirmation_bubbles(
    state: Any,
    *,
    include_location: bool = False,
    handoff: bool = False,
) -> list[str]:
    """Commercial confirmation — never vendor-process language."""
    name = display_first_name(getattr(getattr(state, "customer", None), "name", None))
    vehicle_txt = _vehicle_label(state)
    when = relative_when(state)
    loc = " 📍" if include_location else ""
    within = getattr(state, "visit_within_hours", None)
    has_time = bool(getattr(state, "visit_time", None))
    has_date = bool(getattr(state, "visit_date", None) or getattr(state, "visit_period", None))
    declined_now = bool(getattr(state, "visit_declined_this_turn", False))
    declined = bool(getattr(state, "visit_declined", False))

    if declined_now or (declined and not has_date and not has_time):
        who = f", {name}" if name else ""
        return [f"Sem problema{who}! Vou encaminhar seu atendimento ao nosso time."]

    if getattr(state, "visit_courtesy", False) and not has_date and not has_time:
        if handoff:
            return ["Por nada! Vou encaminhar seu atendimento ao nosso time."]
        return [
            "Por nada! Se quiser conhecer o veículo pessoalmente, "
            "posso deixar registrada sua preferência de dia ou período."
        ]

    who = f", {name}" if name else ""
    if has_time and has_date and within is False:
        when_bit = f" para {when}" if when else ""
        return [
            f"Anotei sua preferência{who}{when_bit}. "
            "Vou encaminhar seu atendimento ao nosso time para alinhar os detalhes."
            f"{loc}"
        ]

    if has_time and within is True:
        greet = f"Combinado{who}!"
        return [
            f"{greet} Te esperamos {when} para conhecer o {vehicle_txt} "
            "e conversar sobre as condições. "
            f"Vou encaminhar seu atendimento ao nosso time.{loc}"
        ]

    if has_date or when:
        return [
            f"Perfeito{who}! "
            f"Vou registrar que você pretende vir {when} "
            f"e encaminhar seu atendimento ao nosso time.{loc}"
        ]

    return []


def should_send_store_location(state: Any) -> bool:
    if getattr(state, "location_sent", False):
        return False
    if getattr(state, "visit_declined_this_turn", False):
        return False
    return bool(
        getattr(state, "visit_accepted_offered", False)
        or getattr(state, "visit_date", None)
        or getattr(state, "visit_time", None)
        or getattr(state, "location_request", False)
    )
