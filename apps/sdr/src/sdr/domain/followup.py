"""Contextual pause + follow-up policy — LLM suggests, code decides.

Wait-state is a separate axis from Conversation.botStatus / lifecycle.
HUMAN_ACTIVE and HANDOFF_SENT stay on ownership. DORMANT and
REMARKETING_ELIGIBLE never authorize an automatic send.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from enum import Enum
from typing import Any

from sdr.domain.clock import TZ_BRT, now_brt, parse_clock
from sdr.domain.facts_schema import is_pure_greeting
from sdr.domain.followup_config import (
    AWAITING_AFTER_FOLLOWUP_WINDOW,
    COMMERCIAL_SILENCE_WINDOW,
    DEFAULT_DAY_HOUR,
    DEFAULT_DAY_MINUTE,
    MAX_ATTEMPTS,
    MIN_LEAD_TIME,
)
from sdr.domain.scheduling import STORE_HOURS
from sdr.domain.types import (
    BusinessIntent,
    ConversationCanonicalState,
    LifecycleStatus,
    TurnFacts,
)

_COMMERCIAL_INTENTS = frozenset(
    {
        BusinessIntent.PURCHASE,
        BusinessIntent.PURCHASE_FINANCING,
        BusinessIntent.TRADE,
        BusinessIntent.SALE,
        BusinessIntent.CONSIGNMENT,
        BusinessIntent.REFINANCING,
    }
)
_LEAD_CLOSED_OUTCOMES = frozenset({"won", "lost", "spam", "closed"})


class FollowUpWaitState(str, Enum):
    """Operational wait-state — not ownership. Do not fold into botStatus."""

    ACTIVE_QUALIFICATION = "ACTIVE_QUALIFICATION"
    AWAITING_CUSTOMER = "AWAITING_CUSTOMER"
    PAUSED_WITH_FOLLOWUP = "PAUSED_WITH_FOLLOWUP"
    FOLLOWUP_DUE = "FOLLOWUP_DUE"
    FOLLOWUP_PROCESSING = "FOLLOWUP_PROCESSING"
    AWAITING_AFTER_FOLLOWUP = "AWAITING_AFTER_FOLLOWUP"
    DORMANT = "DORMANT"
    REMARKETING_ELIGIBLE = "REMARKETING_ELIGIBLE"


class PauseReason(str, Enum):
    DOCUMENTS_UNAVAILABLE = "DOCUMENTS_UNAVAILABLE"
    DOCUMENTS_PROMISED = "DOCUMENTS_PROMISED"
    DECISION_WITH_PARTNER = "DECISION_WITH_PARTNER"
    CUSTOMER_WILL_RETURN = "CUSTOMER_WILL_RETURN"
    THINKING = "THINKING"
    NO_RESPONSE_AFTER_QUESTION = "NO_RESPONSE_AFTER_QUESTION"
    VISIT_FUTURE_CONTACT = "VISIT_FUTURE_CONTACT"
    OTHER_CONTEXTUAL_PAUSE = "OTHER_CONTEXTUAL_PAUSE"
    OPT_OUT = "OPT_OUT"


class ConsentLevel(str, Enum):
    EXPLICIT_TIME = "EXPLICIT_TIME"
    CONTEXTUAL = "CONTEXTUAL"
    NONE = "NONE"
    REFUSED = "REFUSED"


class ConsentSource(str, Enum):
    """How a resume window was obtained — never confuse fallback with a promise."""

    EXPLICIT_CUSTOMER_TIME = "explicit_customer_time"
    EXPLICIT_PERMISSION = "explicit_permission"
    CONTEXTUAL_SINGLE_ATTEMPT = "contextual_single_attempt"
    NONE = "none"


class FollowUpCancelIntent(str, Enum):
    """Returned for Frente C to wire. This module does not persist cancels."""

    HUMAN_ASSUMED = "HUMAN_ASSUMED"
    OPT_OUT = "OPT_OUT"
    CONVERSATION_CLOSED = "CONVERSATION_CLOSED"


class TemporalKind(str, Enum):
    INSTANT = "instant"
    PERIOD = "period"


_PAUSE_REASONS = {item.value: item for item in PauseReason}
_CONSENT_LEVELS = {item.value: item for item in ConsentLevel}
_WAIT_STATES = {item.value: item for item in FollowUpWaitState}
_WEEKDAY_INDEX = {
    "segunda": 0,
    "terca": 1,
    "quarta": 2,
    "quinta": 3,
    "sexta": 4,
    "sabado": 5,
    "domingo": 6,
}


@dataclass(slots=True)
class TemporalCommitment:
    """LLM-suggested temporal payload. Code re-normalizes; never trusts the instant."""

    original_text: str | None = None
    instant: datetime | None = None
    date: date | None = None
    time: time | None = None
    period: str | None = None
    relative: str | None = None
    weekday: int | None = None


@dataclass(slots=True)
class NormalizedTemporal:
    original_text: str | None = None
    kind: TemporalKind | None = None
    instant: datetime | None = None
    period_label: str | None = None
    date: date | None = None
    moved_outside_hours: bool = False


@dataclass(slots=True)
class FollowUpRecord:
    """Canonical follow-up fields copied by merge. LLM omission must not clear them."""

    pause_reason: PauseReason | None = None
    consent_level: ConsentLevel = ConsentLevel.NONE
    pause_confidence: float | None = None
    original_temporal_text: str | None = None
    scheduled_at: str | None = None
    temporal_kind: str | None = None
    period_label: str | None = None
    attempt_number: int = 0
    sent_at: str | None = None
    awaiting_until: str | None = None
    remarketing_eligible: bool = False
    last_bot_had_actionable_question: bool = False
    significant_commercial_exchange: bool = False
    commercially_closed: bool = False
    customer_commitment: bool = False
    permission_requested: bool = False
    consent_source: str = ConsentSource.NONE.value
    fallback_resume_at: str | None = None
    opted_out: bool = False


@dataclass(slots=True)
class FollowUpDecision:
    eligible: bool
    wait_state: FollowUpWaitState
    pause_reason: PauseReason | None = None
    consent_level: ConsentLevel = ConsentLevel.NONE
    may_ask_return_permission: bool = False
    schedule_at: datetime | None = None
    original_temporal_text: str | None = None
    temporal_kind: TemporalKind | None = None
    period_label: str | None = None
    authorize_send: bool = False
    send_now: bool = False
    next_window: datetime | None = None
    cancel_intent: FollowUpCancelIntent | None = None
    attempt_number: int = 0
    maximum_attempts: int = MAX_ATTEMPTS
    remarketing_eligible: bool = False
    forbid_handoff_repeat: bool = False
    reason_code: str = "not_eligible"
    fallback_resume_at: datetime | None = None
    permission_requested: bool = False
    consent_source: ConsentSource = ConsentSource.NONE


def coerce_pause_reason(raw: Any) -> PauseReason | None:
    if raw is None:
        return None
    if isinstance(raw, PauseReason):
        return raw
    return _PAUSE_REASONS.get(str(raw).strip().upper())


def coerce_consent_level(raw: Any) -> ConsentLevel | None:
    if raw is None:
        return None
    if isinstance(raw, ConsentLevel):
        return raw
    return _CONSENT_LEVELS.get(str(raw).strip().upper())


def coerce_wait_state(raw: Any) -> FollowUpWaitState:
    if isinstance(raw, FollowUpWaitState):
        return raw
    if raw is None or raw == "":
        return FollowUpWaitState.ACTIVE_QUALIFICATION
    return _WAIT_STATES.get(str(raw).strip().upper(), FollowUpWaitState.ACTIVE_QUALIFICATION)


def _record_from_dict(data: dict[str, Any]) -> FollowUpRecord:
    return FollowUpRecord(
        pause_reason=coerce_pause_reason(data.get("pause_reason")),
        consent_level=coerce_consent_level(data.get("consent_level")) or ConsentLevel.NONE,
        pause_confidence=data.get("pause_confidence"),
        original_temporal_text=data.get("original_temporal_text"),
        scheduled_at=data.get("scheduled_at"),
        temporal_kind=data.get("temporal_kind"),
        period_label=data.get("period_label"),
        attempt_number=int(data.get("attempt_number") or 0),
        sent_at=data.get("sent_at"),
        awaiting_until=data.get("awaiting_until"),
        remarketing_eligible=bool(data.get("remarketing_eligible")),
        last_bot_had_actionable_question=bool(data.get("last_bot_had_actionable_question")),
        significant_commercial_exchange=bool(data.get("significant_commercial_exchange")),
        commercially_closed=bool(data.get("commercially_closed")),
        customer_commitment=bool(data.get("customer_commitment")),
        permission_requested=bool(data.get("permission_requested")),
        consent_source=str(data.get("consent_source") or ConsentSource.NONE.value),
        fallback_resume_at=data.get("fallback_resume_at"),
        opted_out=bool(data.get("opted_out")),
    )


def parse_temporal_commitment(raw: Any) -> TemporalCommitment | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, TemporalCommitment):
        return raw
    if isinstance(raw, str):
        return TemporalCommitment(original_text=raw)
    if not isinstance(raw, dict):
        return None
    instant = parse_clock(raw["instant"]) if raw.get("instant") else None
    raw_date = raw.get("date")
    parsed_date: date | None = None
    if isinstance(raw_date, datetime):
        parsed_date = raw_date.date()
    elif isinstance(raw_date, date):
        parsed_date = raw_date
    elif isinstance(raw_date, str) and raw_date.strip():
        try:
            parsed_date = date.fromisoformat(raw_date.strip()[:10])
        except ValueError:
            parsed_date = None
    raw_time = raw.get("time")
    parsed_time: time | None = None
    if isinstance(raw_time, time):
        parsed_time = raw_time
    elif isinstance(raw_time, str) and raw_time.strip():
        try:
            parsed_time = time.fromisoformat(raw_time.strip())
        except ValueError:
            parsed_time = None
    try:
        weekday_i = int(raw["weekday"]) if raw.get("weekday") is not None else None
    except (TypeError, ValueError):
        weekday_i = None
    return TemporalCommitment(
        original_text=raw.get("original_text") or raw.get("text"),
        instant=instant,
        date=parsed_date,
        time=parsed_time,
        period=raw.get("period"),
        relative=raw.get("relative"),
        weekday=weekday_i,
    )


def followup_record(state: ConversationCanonicalState) -> FollowUpRecord:
    current = getattr(state, "followup", None)
    if isinstance(current, FollowUpRecord):
        return current
    if isinstance(current, dict):
        record = _record_from_dict(current)
        state.followup = record
        return record
    record = FollowUpRecord()
    state.followup = record
    return record


def copy_followup_record(prev: ConversationCanonicalState) -> FollowUpRecord:
    current = getattr(prev, "followup", None)
    if isinstance(current, FollowUpRecord):
        return replace(current)
    if isinstance(current, dict):
        return _record_from_dict(current)
    return FollowUpRecord()


def wait_state_of(state: ConversationCanonicalState) -> FollowUpWaitState:
    return coerce_wait_state(getattr(state, "wait_state", None))


def authorizes_automatic_send(wait_state: FollowUpWaitState | str | None) -> bool:
    """Only FOLLOWUP_DUE may authorize a send. DORMANT / REMARKETING never do."""
    return coerce_wait_state(wait_state) == FollowUpWaitState.FOLLOWUP_DUE


def is_open_datetime(dt: datetime) -> bool:
    hours = STORE_HOURS.get(dt.weekday())
    if hours is None:
        return False
    open_h, close_h = hours
    minutes = dt.hour * 60 + dt.minute
    return open_h * 60 <= minutes < close_h * 60


def is_open_date(day: date) -> bool:
    return STORE_HOURS.get(day.weekday()) is not None


def next_open_datetime(dt: datetime) -> datetime:
    instant = dt.astimezone(TZ_BRT) if dt.tzinfo else dt.replace(tzinfo=TZ_BRT)
    hours = STORE_HOURS.get(instant.weekday())
    if hours is not None:
        open_h, close_h = hours
        open_dt = instant.replace(hour=open_h, minute=0, second=0, microsecond=0)
        close_dt = instant.replace(hour=close_h, minute=0, second=0, microsecond=0)
        if open_dt <= instant < close_dt:
            return instant.replace(second=0, microsecond=0)
        if instant < open_dt:
            return open_dt
    for offset in range(1, 15):
        day = instant + timedelta(days=offset)
        hours = STORE_HOURS.get(day.weekday())
        if hours is None:
            continue
        return day.replace(hour=hours[0], minute=0, second=0, microsecond=0)
    return instant


def next_business_datetime(
    now: datetime,
    *,
    hour: int = DEFAULT_DAY_HOUR,
    minute: int = DEFAULT_DAY_MINUTE,
    skip_today: bool = True,
) -> datetime:
    start = now.astimezone(TZ_BRT) if now.tzinfo else now.replace(tzinfo=TZ_BRT)
    first_offset = 1 if skip_today else 0
    for offset in range(first_offset, 15):
        day = start + timedelta(days=offset)
        hours = STORE_HOURS.get(day.weekday())
        if hours is None:
            continue
        open_h, close_h = hours
        chosen_hour = hour if open_h <= hour < close_h else open_h
        chosen_minute = minute if chosen_hour == hour else 0
        candidate = day.replace(
            hour=chosen_hour, minute=chosen_minute, second=0, microsecond=0
        )
        if candidate >= start + MIN_LEAD_TIME and is_open_datetime(candidate):
            return candidate
        snapped = next_open_datetime(max(candidate, start + MIN_LEAD_TIME))
        if snapped >= start + MIN_LEAD_TIME:
            return snapped
    return next_open_datetime(start + timedelta(days=1))


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text or "")
    stripped = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return stripped.lower()


def _parse_clock_token(text: str) -> time | None:
    match = re.search(r"\b(?:as|aas|depois das)?\s*(\d{1,2})\s*(?:h|:)\s*(\d{2})?\b", text)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    if hour > 23 or minute > 59:
        return None
    return time(hour, minute)


def _parse_weekday(folded: str) -> int | None:
    match = re.search(
        r"\b(segunda|terca|quarta|quinta|sexta|sabado|domingo)(?:[\s-]feira)?\b",
        folded,
    )
    if not match:
        return None
    return _WEEKDAY_INDEX.get(match.group(1))


def _next_weekday(now: datetime, weekday: int) -> date:
    delta = (weekday - now.weekday()) % 7
    if delta == 0:
        delta = 7
    return (now + timedelta(days=delta)).date()


def _snap_explicit_time(day: date, clock: time, now: datetime) -> tuple[datetime, bool]:
    candidate = datetime(day.year, day.month, day.day, clock.hour, clock.minute, tzinfo=TZ_BRT)
    earliest = now + MIN_LEAD_TIME
    if is_open_datetime(candidate) and candidate >= earliest:
        return candidate, False
    for offset in range(0, 14):
        probe_day = day + timedelta(days=offset)
        probe = datetime(
            probe_day.year, probe_day.month, probe_day.day,
            clock.hour, clock.minute, tzinfo=TZ_BRT,
        )
        if is_open_datetime(probe) and probe >= earliest:
            moved = probe.date() != day or not is_open_datetime(candidate)
            return probe, moved
    return next_open_datetime(max(candidate, earliest)), True


def normalize_temporal(
    commitment: TemporalCommitment | str | dict | None,
    now: datetime | None = None,
) -> NormalizedTemporal:
    """Normalize a suggested commitment against store hours. Code owns the instant."""
    instant_now = now or now_brt()
    if instant_now.tzinfo is None:
        instant_now = instant_now.replace(tzinfo=TZ_BRT)
    else:
        instant_now = instant_now.astimezone(TZ_BRT)

    parsed = parse_temporal_commitment(commitment)
    if parsed is None:
        return NormalizedTemporal()

    original = (parsed.original_text or "").strip() or None
    folded = _fold(original or "")
    relative = (parsed.relative or "").strip().lower() or None
    period = (parsed.period or "").strip().lower() or None

    if not period and ("semana que vem" in folded or "proxima semana" in folded):
        period = "next_week"
    if not period and (
        "depois do almoco" in folded or relative in {"after_lunch", "depois_do_almoco"}
    ):
        period = "after_lunch"
    if period in {"depois_do_almoco", "after_lunch"}:
        period = "after_lunch"
    if period in {"next_week", "semana_que_vem", "proxima_semana"}:
        period = "next_week"

    if period == "next_week" and parsed.weekday is None and _parse_weekday(folded) is None:
        return NormalizedTemporal(
            original_text=original, kind=TemporalKind.PERIOD, period_label="next_week"
        )
    if period == "after_lunch" and parsed.time is None and not _parse_clock_token(folded):
        day = parsed.date
        if relative in {"tomorrow", "amanha"} or "amanha" in folded:
            day = (instant_now + timedelta(days=1)).date()
        elif relative in {"today", "hoje"} or (not day and "hoje" in folded):
            day = instant_now.date()
        return NormalizedTemporal(
            original_text=original,
            kind=TemporalKind.PERIOD,
            period_label="after_lunch",
            date=day,
        )

    clock = parsed.time or _parse_clock_token(folded)
    weekday = parsed.weekday if parsed.weekday is not None else _parse_weekday(folded)
    day = parsed.date

    if day is None:
        if relative in {"tomorrow", "amanha"} or "amanha" in folded:
            day = (instant_now + timedelta(days=1)).date()
        elif relative in {"day_after", "depois_de_amanha"} or "depois de amanha" in folded:
            day = (instant_now + timedelta(days=2)).date()
        elif relative in {"today", "hoje"} or "hoje" in folded:
            day = instant_now.date()
        elif weekday is not None:
            day = _next_weekday(instant_now, weekday)

    if clock is None and parsed.instant is not None:
        suggested = parsed.instant
        if suggested.tzinfo is None:
            suggested = suggested.replace(tzinfo=TZ_BRT)
        else:
            suggested = suggested.astimezone(TZ_BRT)
        day = day or suggested.date()
        clock = time(suggested.hour, suggested.minute)

    if day is not None and clock is not None:
        snapped, moved = _snap_explicit_time(day, clock, instant_now)
        return NormalizedTemporal(
            original_text=original,
            kind=TemporalKind.INSTANT,
            instant=snapped,
            date=snapped.date(),
            moved_outside_hours=moved,
        )

    if day is not None and clock is None:
        if period in {"afternoon", "tarde", "morning", "manha", "evening", "noite"}:
            return NormalizedTemporal(
                original_text=original,
                kind=TemporalKind.PERIOD,
                period_label=period,
                date=day,
            )
        hours = STORE_HOURS.get(day.weekday())
        target_day = day
        moved = False
        if hours is None:
            probe = datetime(day.year, day.month, day.day, 12, 0, tzinfo=TZ_BRT)
            opened = next_open_datetime(probe)
            target_day = opened.date()
            hours = STORE_HOURS.get(target_day.weekday())
            moved = True
        open_h, close_h = hours or (DEFAULT_DAY_HOUR, DEFAULT_DAY_HOUR + 1)
        chosen_hour = DEFAULT_DAY_HOUR if open_h <= DEFAULT_DAY_HOUR < close_h else open_h
        candidate = datetime(
            target_day.year, target_day.month, target_day.day,
            chosen_hour,
            DEFAULT_DAY_MINUTE if chosen_hour == DEFAULT_DAY_HOUR else 0,
            tzinfo=TZ_BRT,
        )
        if candidate < instant_now + MIN_LEAD_TIME or not is_open_datetime(candidate):
            candidate = next_open_datetime(max(candidate, instant_now + MIN_LEAD_TIME))
            moved = True
        return NormalizedTemporal(
            original_text=original,
            kind=TemporalKind.INSTANT,
            instant=candidate,
            date=candidate.date(),
            moved_outside_hours=moved,
        )

    if clock is not None:
        snapped, moved = _snap_explicit_time(instant_now.date(), clock, instant_now)
        return NormalizedTemporal(
            original_text=original,
            kind=TemporalKind.INSTANT,
            instant=snapped,
            date=snapped.date(),
            moved_outside_hours=moved,
        )

    if period:
        return NormalizedTemporal(
            original_text=original, kind=TemporalKind.PERIOD, period_label=period
        )
    return NormalizedTemporal(original_text=original)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def _parse_iso(raw: str | None) -> datetime | None:
    return parse_clock(raw) if raw else None


def _has_vehicle_or_intent(state: ConversationCanonicalState) -> bool:
    if state.intent in _COMMERCIAL_INTENTS:
        return True
    facts = state.facts or {}
    return any(
        facts.get(key)
        for key in (
            "desired_model",
            "desired_vehicle",
            "desired_vehicle_text",
            "customer_vehicle",
            "vehicle_model",
        )
    )


def _significant_exchange(state: ConversationCanonicalState) -> bool:
    record = followup_record(state)
    if record.significant_commercial_exchange:
        return True
    return int(state.assistant_turn_count or 0) >= 1 and _has_vehicle_or_intent(state)


def _had_actionable_question(state: ConversationCanonicalState) -> bool:
    return followup_record(state).last_bot_had_actionable_question or bool(state.pending_question)


def _is_human_active(state: ConversationCanonicalState) -> bool:
    return state.lifecycle.status == LifecycleStatus.HUMAN_ACTIVE


def _is_handoff_sent(state: ConversationCanonicalState) -> bool:
    return state.lifecycle.status == LifecycleStatus.HANDOFF_SENT


def _commercially_closed(state: ConversationCanonicalState, facts: TurnFacts | None) -> bool:
    if state.lifecycle.status == LifecycleStatus.HUMAN_CLOSED:
        return True
    if followup_record(state).commercially_closed:
        return True
    incoming = (facts.facts if facts else {}) or {}
    outcome = str(incoming.get("lead_outcome") or state.facts.get("lead_outcome") or "").lower()
    return outcome in _LEAD_CLOSED_OUTCOMES


def _opt_out(state: ConversationCanonicalState, facts: TurnFacts | None) -> bool:
    if getattr(state, "sdr_opted_out_at", None):
        return True
    if followup_record(state).opted_out:
        return True
    if followup_record(state).pause_reason == PauseReason.OPT_OUT:
        return True
    return facts is not None and coerce_pause_reason(facts.pause_reason) == PauseReason.OPT_OUT


def _refused(state: ConversationCanonicalState, facts: TurnFacts | None) -> bool:
    if followup_record(state).consent_level == ConsentLevel.REFUSED:
        return True
    return facts is not None and coerce_consent_level(facts.consent_level) == ConsentLevel.REFUSED


def _overlay_consent(prev: ConsentLevel, incoming: ConsentLevel | None) -> ConsentLevel:
    if incoming is None:
        return prev
    if prev == ConsentLevel.REFUSED or incoming == ConsentLevel.REFUSED:
        return ConsentLevel.REFUSED if prev == ConsentLevel.REFUSED else incoming
    rank = {
        ConsentLevel.NONE: 0,
        ConsentLevel.CONTEXTUAL: 1,
        ConsentLevel.EXPLICIT_TIME: 2,
        ConsentLevel.REFUSED: 3,
    }
    return incoming if rank[incoming] >= rank[prev] else prev


def overlay_followup_suggestions(record: FollowUpRecord, facts: TurnFacts) -> FollowUpRecord:
    """Copy LLM pause suggestions onto the record. Does not change wait_state."""
    incoming_reason = coerce_pause_reason(facts.pause_reason)
    if incoming_reason is not None and record.pause_reason != PauseReason.OPT_OUT:
        record.pause_reason = incoming_reason
    record.consent_level = _overlay_consent(
        record.consent_level, coerce_consent_level(facts.consent_level)
    )
    if facts.pause_confidence is not None:
        record.pause_confidence = facts.pause_confidence
    commitment = parse_temporal_commitment(facts.temporal_commitment)
    if commitment is not None:
        if commitment.original_text:
            record.original_temporal_text = commitment.original_text
        if incoming_reason != PauseReason.OPT_OUT and (
            commitment.relative or commitment.date or commitment.time
            or commitment.period or commitment.original_text
        ):
            record.customer_commitment = True
    return record


def _ineligible(
    *,
    state: ConversationCanonicalState,
    reason_code: str,
    wait_state: FollowUpWaitState | None = None,
    cancel_intent: FollowUpCancelIntent | None = None,
    remarketing_eligible: bool | None = None,
) -> FollowUpDecision:
    record = followup_record(state)
    resolved = wait_state or wait_state_of(state)
    remarketing = record.remarketing_eligible if remarketing_eligible is None else remarketing_eligible
    if resolved in (FollowUpWaitState.DORMANT, FollowUpWaitState.REMARKETING_ELIGIBLE):
        remarketing = True if remarketing_eligible is None else remarketing
    return FollowUpDecision(
        eligible=False,
        wait_state=resolved,
        pause_reason=record.pause_reason,
        consent_level=record.consent_level,
        original_temporal_text=record.original_temporal_text,
        attempt_number=record.attempt_number,
        remarketing_eligible=bool(remarketing),
        cancel_intent=cancel_intent,
        forbid_handoff_repeat=_is_handoff_sent(state),
        reason_code=reason_code,
        authorize_send=False,
        send_now=False,
    )


def _attempts_exhausted(record: FollowUpRecord) -> bool:
    return int(record.attempt_number or 0) >= MAX_ATTEMPTS or bool(record.sent_at)


def evaluate_followup(
    state: ConversationCanonicalState,
    facts: TurnFacts | None = None,
    now: datetime | None = None,
    *,
    inbound_text: str = "",
) -> FollowUpDecision:
    """Decide eligibility, wait-state, and schedule. Never sends."""
    instant = now or now_brt()
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=TZ_BRT)
    else:
        instant = instant.astimezone(TZ_BRT)

    record = followup_record(state)
    current_wait = wait_state_of(state)
    facts = facts or TurnFacts()

    if _is_human_active(state):
        return _ineligible(
            state=state,
            reason_code="human_active",
            cancel_intent=FollowUpCancelIntent.HUMAN_ASSUMED,
        )
    if _opt_out(state, facts):
        return _ineligible(
            state=state,
            reason_code="opt_out",
            cancel_intent=FollowUpCancelIntent.OPT_OUT,
        )
    if _commercially_closed(state, facts):
        return _ineligible(
            state=state,
            reason_code="commercially_closed",
            cancel_intent=FollowUpCancelIntent.CONVERSATION_CLOSED,
        )
    if current_wait in (FollowUpWaitState.DORMANT, FollowUpWaitState.REMARKETING_ELIGIBLE):
        return _ineligible(
            state=state,
            reason_code="dormant_no_automatic_send",
            wait_state=current_wait,
            remarketing_eligible=True,
        )

    pause_reason = coerce_pause_reason(facts.pause_reason) or record.pause_reason
    consent = _overlay_consent(record.consent_level, coerce_consent_level(facts.consent_level))
    commitment = parse_temporal_commitment(facts.temporal_commitment)
    has_inbound_pause = bool(
        coerce_pause_reason(facts.pause_reason)
        or commitment
        or coerce_consent_level(facts.consent_level)
        in {ConsentLevel.EXPLICIT_TIME, ConsentLevel.CONTEXTUAL}
    )

    if _refused(state, facts) and not (
        coerce_pause_reason(facts.pause_reason) and pause_reason != PauseReason.OPT_OUT and commitment
    ):
        if coerce_consent_level(facts.consent_level) == ConsentLevel.REFUSED or (
            record.consent_level == ConsentLevel.REFUSED and not has_inbound_pause
        ):
            if not has_inbound_pause or coerce_consent_level(facts.consent_level) == ConsentLevel.REFUSED:
                return _ineligible(state=state, reason_code="explicit_refusal")

    if inbound_text and is_pure_greeting(inbound_text) and not has_inbound_pause:
        if not _significant_exchange(state):
            return _ineligible(state=state, reason_code="greeting_only")

    if current_wait == FollowUpWaitState.AWAITING_AFTER_FOLLOWUP:
        awaiting_until = _parse_iso(record.awaiting_until)
        sent_at = _parse_iso(record.sent_at)
        deadline = awaiting_until or (
            sent_at + AWAITING_AFTER_FOLLOWUP_WINDOW if sent_at is not None else None
        )
        if deadline is not None and instant >= deadline:
            return FollowUpDecision(
                eligible=False,
                wait_state=FollowUpWaitState.DORMANT,
                pause_reason=record.pause_reason,
                consent_level=record.consent_level,
                original_temporal_text=record.original_temporal_text,
                attempt_number=record.attempt_number,
                remarketing_eligible=True,
                authorize_send=False,
                send_now=False,
                forbid_handoff_repeat=_is_handoff_sent(state),
                reason_code="unanswered_followup_dormant",
            )

    if _attempts_exhausted(record) and not has_inbound_pause:
        if current_wait in (
            FollowUpWaitState.PAUSED_WITH_FOLLOWUP,
            FollowUpWaitState.FOLLOWUP_DUE,
            FollowUpWaitState.FOLLOWUP_PROCESSING,
            FollowUpWaitState.AWAITING_AFTER_FOLLOWUP,
        ):
            return _ineligible(state=state, reason_code="max_attempts")

    if _is_handoff_sent(state) and has_inbound_pause:
        commitment_ok = record.customer_commitment or commitment is not None or pause_reason in {
            PauseReason.DOCUMENTS_PROMISED,
            PauseReason.DECISION_WITH_PARTNER,
            PauseReason.CUSTOMER_WILL_RETURN,
            PauseReason.THINKING,
            PauseReason.VISIT_FUTURE_CONTACT,
            PauseReason.DOCUMENTS_UNAVAILABLE,
        }
        if not commitment_ok:
            return _ineligible(state=state, reason_code="post_handoff_without_commitment")

    if has_inbound_pause and pause_reason != PauseReason.OPT_OUT:
        return _decision_from_pause(
            state=state,
            record=record,
            pause_reason=pause_reason or PauseReason.OTHER_CONTEXTUAL_PAUSE,
            consent=consent,
            commitment=commitment,
            instant=instant,
        )

    scheduled = _parse_iso(record.scheduled_at)
    if scheduled is not None and not _attempts_exhausted(record):
        if instant >= scheduled:
            return _due_decision(state, record, instant, scheduled)
        return FollowUpDecision(
            eligible=True,
            wait_state=FollowUpWaitState.PAUSED_WITH_FOLLOWUP,
            pause_reason=record.pause_reason,
            consent_level=record.consent_level,
            schedule_at=scheduled,
            original_temporal_text=record.original_temporal_text,
            temporal_kind=TemporalKind.INSTANT,
            period_label=record.period_label,
            authorize_send=False,
            send_now=False,
            attempt_number=record.attempt_number,
            forbid_handoff_repeat=_is_handoff_sent(state),
            reason_code="scheduled_future",
        )

    if current_wait in (
        FollowUpWaitState.AWAITING_CUSTOMER,
        FollowUpWaitState.ACTIVE_QUALIFICATION,
    ):
        silence = _silence_decision(state, record, instant)
        if silence is not None:
            return silence

    return _ineligible(state=state, reason_code="not_eligible")


def _decision_from_pause(
    *,
    state: ConversationCanonicalState,
    record: FollowUpRecord,
    pause_reason: PauseReason,
    consent: ConsentLevel,
    commitment: TemporalCommitment | None,
    instant: datetime,
) -> FollowUpDecision:
    if _attempts_exhausted(record) and record.sent_at:
        return _ineligible(state=state, reason_code="max_attempts")

    normalized = normalize_temporal(commitment, instant)
    original = normalized.original_text or record.original_temporal_text
    forbid_handoff = _is_handoff_sent(state)

    if normalized.kind == TemporalKind.PERIOD:
        return FollowUpDecision(
            eligible=True,
            wait_state=FollowUpWaitState.PAUSED_WITH_FOLLOWUP,
            pause_reason=pause_reason,
            consent_level=consent if consent != ConsentLevel.NONE else ConsentLevel.CONTEXTUAL,
            may_ask_return_permission=consent != ConsentLevel.EXPLICIT_TIME,
            permission_requested=consent != ConsentLevel.EXPLICIT_TIME,
            consent_source=ConsentSource.CONTEXTUAL_SINGLE_ATTEMPT,
            schedule_at=None,
            original_temporal_text=original,
            temporal_kind=TemporalKind.PERIOD,
            period_label=normalized.period_label,
            authorize_send=False,
            send_now=False,
            attempt_number=record.attempt_number,
            forbid_handoff_repeat=forbid_handoff,
            reason_code="period_no_invented_time",
            fallback_resume_at=next_business_datetime(instant),
        )

    if consent == ConsentLevel.EXPLICIT_TIME or normalized.instant is not None:
        schedule_at = normalized.instant or next_business_datetime(instant)
        resolved_consent = (
            ConsentLevel.EXPLICIT_TIME
            if consent == ConsentLevel.EXPLICIT_TIME or normalized.instant is not None
            else consent
        )
        return FollowUpDecision(
            eligible=True,
            wait_state=FollowUpWaitState.PAUSED_WITH_FOLLOWUP,
            pause_reason=pause_reason,
            consent_level=resolved_consent,
            may_ask_return_permission=False,
            permission_requested=False,
            consent_source=ConsentSource.EXPLICIT_CUSTOMER_TIME,
            schedule_at=schedule_at,
            original_temporal_text=original,
            temporal_kind=TemporalKind.INSTANT,
            period_label=normalized.period_label,
            authorize_send=False,
            send_now=False,
            attempt_number=record.attempt_number,
            forbid_handoff_repeat=forbid_handoff,
            reason_code="explicit_time",
        )

    fallback = next_business_datetime(instant)
    grant = _fold(original or "")
    permission_granted = any(
        token in grant
        for token in ("pode me chamar", "me chama", "pode chamar", "me liga")
    )
    if permission_granted:
        return FollowUpDecision(
            eligible=True,
            wait_state=FollowUpWaitState.PAUSED_WITH_FOLLOWUP,
            pause_reason=pause_reason,
            consent_level=consent if consent != ConsentLevel.NONE else ConsentLevel.CONTEXTUAL,
            may_ask_return_permission=False,
            permission_requested=False,
            consent_source=ConsentSource.EXPLICIT_PERMISSION,
            schedule_at=None,
            original_temporal_text=original,
            authorize_send=False,
            send_now=False,
            attempt_number=record.attempt_number,
            forbid_handoff_repeat=forbid_handoff,
            reason_code="explicit_permission",
            fallback_resume_at=fallback,
        )
    return FollowUpDecision(
        eligible=True,
        wait_state=FollowUpWaitState.PAUSED_WITH_FOLLOWUP,
        pause_reason=pause_reason,
        consent_level=consent if consent != ConsentLevel.NONE else ConsentLevel.CONTEXTUAL,
        may_ask_return_permission=True,
        permission_requested=True,
        consent_source=ConsentSource.CONTEXTUAL_SINGLE_ATTEMPT,
        schedule_at=None,
        original_temporal_text=original,
        authorize_send=False,
        send_now=False,
        attempt_number=record.attempt_number,
        forbid_handoff_repeat=forbid_handoff,
        reason_code="contextual_without_time",
        fallback_resume_at=fallback,
    )


def _due_decision(
    state: ConversationCanonicalState,
    record: FollowUpRecord,
    instant: datetime,
    scheduled: datetime,
) -> FollowUpDecision:
    if _attempts_exhausted(record):
        return _ineligible(state=state, reason_code="max_attempts")
    if not is_open_datetime(instant):
        return FollowUpDecision(
            eligible=True,
            wait_state=FollowUpWaitState.FOLLOWUP_DUE,
            pause_reason=record.pause_reason,
            consent_level=record.consent_level,
            schedule_at=scheduled,
            original_temporal_text=record.original_temporal_text,
            temporal_kind=TemporalKind.INSTANT,
            authorize_send=False,
            send_now=False,
            next_window=next_open_datetime(instant),
            attempt_number=record.attempt_number,
            forbid_handoff_repeat=_is_handoff_sent(state),
            reason_code="due_outside_hours",
        )
    return FollowUpDecision(
        eligible=True,
        wait_state=FollowUpWaitState.FOLLOWUP_DUE,
        pause_reason=record.pause_reason,
        consent_level=record.consent_level,
        schedule_at=scheduled,
        original_temporal_text=record.original_temporal_text,
        temporal_kind=TemporalKind.INSTANT,
        authorize_send=True,
        send_now=True,
        attempt_number=record.attempt_number,
        forbid_handoff_repeat=_is_handoff_sent(state),
        reason_code="followup_due",
    )


def _silence_decision(
    state: ConversationCanonicalState,
    record: FollowUpRecord,
    instant: datetime,
) -> FollowUpDecision | None:
    if _attempts_exhausted(record):
        return None
    if not _has_vehicle_or_intent(state) or not _significant_exchange(state):
        return None
    if not _had_actionable_question(state):
        return None
    if record.consent_level == ConsentLevel.REFUSED:
        return None
    deadline = _parse_iso(record.awaiting_until)
    if deadline is None or instant < deadline:
        return None
    if not is_open_datetime(instant):
        return FollowUpDecision(
            eligible=True,
            wait_state=FollowUpWaitState.FOLLOWUP_DUE,
            pause_reason=PauseReason.NO_RESPONSE_AFTER_QUESTION,
            consent_level=ConsentLevel.NONE,
            schedule_at=deadline,
            authorize_send=False,
            send_now=False,
            next_window=next_open_datetime(instant),
            attempt_number=record.attempt_number,
            forbid_handoff_repeat=_is_handoff_sent(state),
            reason_code="silence_outside_hours",
        )
    return FollowUpDecision(
        eligible=True,
        wait_state=FollowUpWaitState.FOLLOWUP_DUE,
        pause_reason=PauseReason.NO_RESPONSE_AFTER_QUESTION,
        consent_level=ConsentLevel.NONE,
        schedule_at=deadline,
        authorize_send=True,
        send_now=True,
        attempt_number=record.attempt_number,
        forbid_handoff_repeat=_is_handoff_sent(state),
        reason_code="commercial_silence",
    )


def followup_decision(
    state: ConversationCanonicalState,
    facts: TurnFacts | None = None,
    now: datetime | None = None,
    *,
    inbound_text: str = "",
) -> FollowUpDecision:
    """Public entry for other fronts. Pure; does not persist or compose."""
    return evaluate_followup(state, facts, now, inbound_text=inbound_text)


def apply_followup_transition(
    state: ConversationCanonicalState,
    decision: FollowUpDecision,
) -> ConversationCanonicalState:
    """Write wait-state and follow-up fields from a policy decision. No IO."""
    record = followup_record(state)
    state.wait_state = decision.wait_state.value
    if decision.pause_reason is not None:
        record.pause_reason = decision.pause_reason
    record.consent_level = decision.consent_level
    if decision.original_temporal_text:
        record.original_temporal_text = decision.original_temporal_text
    if decision.schedule_at is not None:
        record.scheduled_at = _iso(decision.schedule_at)
    elif decision.consent_source in {
        ConsentSource.CONTEXTUAL_SINGLE_ATTEMPT,
        ConsentSource.EXPLICIT_PERMISSION,
    }:
        # Fallback window is operational only — never an agreed customer clock.
        record.scheduled_at = None
    elif decision.temporal_kind == TemporalKind.PERIOD:
        record.scheduled_at = None
    if decision.temporal_kind is not None:
        record.temporal_kind = decision.temporal_kind.value
    if decision.period_label is not None:
        record.period_label = decision.period_label
    record.attempt_number = decision.attempt_number
    record.remarketing_eligible = bool(decision.remarketing_eligible)
    record.permission_requested = bool(decision.permission_requested)
    record.consent_source = decision.consent_source.value
    if decision.fallback_resume_at is not None:
        record.fallback_resume_at = _iso(decision.fallback_resume_at)
    if decision.wait_state == FollowUpWaitState.AWAITING_AFTER_FOLLOWUP:
        sent = now_brt()
        record.sent_at = record.sent_at or _iso(sent)
        record.awaiting_until = _iso(sent + AWAITING_AFTER_FOLLOWUP_WINDOW)
        record.attempt_number = max(record.attempt_number, 1)
    if decision.wait_state == FollowUpWaitState.AWAITING_CUSTOMER and record.awaiting_until is None:
        record.awaiting_until = _iso(now_brt() + COMMERCIAL_SILENCE_WINDOW)
    if decision.wait_state == FollowUpWaitState.DORMANT:
        record.remarketing_eligible = True
    if decision.cancel_intent == FollowUpCancelIntent.OPT_OUT:
        record.opted_out = True
        record.pause_reason = PauseReason.OPT_OUT
        record.consent_level = ConsentLevel.REFUSED
        if not getattr(state, "sdr_opted_out_at", None):
            state.sdr_opted_out_at = _iso(now_brt())
    return state


def resume_after_customer_reply(state: ConversationCanonicalState) -> ConversationCanonicalState:
    """Clear operational schedule after a later inbound. Does not touch opt-out."""
    record = followup_record(state)
    if record.opted_out or getattr(state, "sdr_opted_out_at", None):
        return state
    state.wait_state = FollowUpWaitState.ACTIVE_QUALIFICATION.value
    record.scheduled_at = None
    record.fallback_resume_at = None
    record.permission_requested = False
    record.consent_source = ConsentSource.NONE.value
    return state


def mark_followup_sent(state: ConversationCanonicalState) -> ConversationCanonicalState:
    record = followup_record(state)
    return apply_followup_transition(
        state,
        FollowUpDecision(
            eligible=True,
            wait_state=FollowUpWaitState.AWAITING_AFTER_FOLLOWUP,
            pause_reason=record.pause_reason,
            consent_level=record.consent_level,
            original_temporal_text=record.original_temporal_text,
            attempt_number=max(int(record.attempt_number or 0), 1),
            reason_code="followup_sent",
            consent_source=ConsentSource(record.consent_source)
            if record.consent_source in {item.value for item in ConsentSource}
            else ConsentSource.NONE,
        ),
    )


def mark_awaiting_customer(
    state: ConversationCanonicalState,
    *,
    now: datetime | None = None,
    had_actionable_question: bool = True,
) -> ConversationCanonicalState:
    """Stamp AWAITING_CUSTOMER after an actionable bot question. Code-owned."""
    instant = now or now_brt()
    record = followup_record(state)
    state.wait_state = FollowUpWaitState.AWAITING_CUSTOMER.value
    record.last_bot_had_actionable_question = (
        record.last_bot_had_actionable_question or had_actionable_question
    )
    record.awaiting_until = _iso(instant + COMMERCIAL_SILENCE_WINDOW)
    return state


PERMISSION_ASK_PT = "Claro. Posso te chamar amanhã para saber o que decidiram?"
EXPLICIT_TIME_ACK_PT = "Certo. Te chamo no horário combinado."

_VISIT_TOKENS = (
    "visitar",
    "visita",
    "conhecer a loja",
    "passar na loja",
    "ir ai",
    "ir aí",
    "ir la",
    "ir lá",
    "consigo ir",
    "posso ir",
    "quero ir",
    "vou ai",
    "vou aí",
    "em vez de",
    "na loja",
    "ver o carro",
)
_CALL_ME_TOKENS = (
    "pode me chamar",
    "me chama",
    "pode chamar",
    "me liga",
    "me manda mensagem",
)
_DOCUMENT_TOKENS = ("comprovante", "documento", "cnh", "holerite", "imposto de renda")
_PARTNER_TOKENS = (
    "marido",
    "esposa",
    "esposo",
    "mulher",
    "namorado",
    "namorada",
    "parceiro",
    "parceira",
    "familia",
    "cônjuge",
    "conjuge",
)


def inbound_looks_like_visit(text: str) -> bool:
    folded = _fold(text)
    return any(token in folded for token in _VISIT_TOKENS)


def suggest_pause_from_inbound(text: str) -> tuple[PauseReason | None, ConsentLevel, TemporalCommitment | None]:
    """Deterministic pause interpretation when Understanding omitted suggestions.

    Structural Portuguese cues, not brand/model lists. Temporal parsing still
    owns the clock via ``normalize_temporal``.
    """
    from sdr.domain.followup_cancel import is_opt_out_text

    raw = (text or "").strip()
    if not raw:
        return None, ConsentLevel.NONE, None
    if is_opt_out_text(raw):
        return PauseReason.OPT_OUT, ConsentLevel.REFUSED, None
    if inbound_looks_like_visit(raw):
        return None, ConsentLevel.NONE, None

    folded = _fold(raw)
    commitment = TemporalCommitment(original_text=raw)
    normalized = normalize_temporal(commitment)
    reason: PauseReason | None = None
    call_me = any(token in folded for token in _CALL_ME_TOKENS)
    if any(token in folded for token in _DOCUMENT_TOKENS):
        # Deferring documents stays in qualification. Pause only when the
        # customer asked to be called back about the documents.
        if call_me:
            reason = PauseReason.DOCUMENTS_PROMISED
    elif any(token in folded for token in _PARTNER_TOKENS):
        reason = PauseReason.DECISION_WITH_PARTNER
    elif "vou pensar" in folded or "deixar para pensar" in folded:
        reason = PauseReason.THINKING
    elif (
        "te retorno" in folded
        or "depois te chamo" in folded
        or "te falo" in folded
        or call_me
    ):
        reason = PauseReason.CUSTOMER_WILL_RETURN

    if reason is None:
        return None, ConsentLevel.NONE, None
    consent = ConsentLevel.NONE
    if reason == PauseReason.OPT_OUT:
        consent = ConsentLevel.REFUSED
    elif normalized.kind == TemporalKind.INSTANT:
        consent = ConsentLevel.EXPLICIT_TIME
    else:
        consent = ConsentLevel.CONTEXTUAL
    return reason, consent, commitment


def enrich_turn_facts_from_inbound(facts: TurnFacts, inbound_text: str) -> TurnFacts:
    """Fill omitted pause suggestions from inbound. Never overwrite LLM values."""
    reason, consent, commitment = suggest_pause_from_inbound(inbound_text)
    if facts.pause_reason is None and reason is not None:
        facts.pause_reason = reason.value
    if facts.consent_level is None and consent != ConsentLevel.NONE:
        facts.consent_level = consent.value
    if facts.temporal_commitment is None and commitment is not None:
        facts.temporal_commitment = commitment.original_text or inbound_text
    return facts


def inbound_is_followup_pause(
    text: str,
    facts: TurnFacts | None = None,
    state: ConversationCanonicalState | None = None,
) -> bool:
    if inbound_looks_like_visit(text):
        return False
    if state is not None:
        in_visit_flow = (
            getattr(state, "pending_question", None) == "visit"
            or bool(getattr(state, "visit_invited", False))
            or bool(getattr(state, "offered_visit_slots", None))
            or bool(getattr(state, "visit_preferred_time", None))
        )
        if in_visit_flow:
            folded = _fold(text)
            call_me = any(
                token in folded
                for token in (*_CALL_ME_TOKENS, "te retorno")
            )
            if not call_me:
                return False
    if facts is not None and coerce_pause_reason(facts.pause_reason):
        return coerce_pause_reason(facts.pause_reason) != PauseReason.OPT_OUT
    reason, _consent, _commitment = suggest_pause_from_inbound(text)
    return reason is not None and reason != PauseReason.OPT_OUT


def followup_record_to_dict(record: FollowUpRecord | None) -> dict[str, Any]:
    if record is None:
        return {}
    return {
        "pause_reason": record.pause_reason.value if record.pause_reason else None,
        "consent_level": record.consent_level.value,
        "pause_confidence": record.pause_confidence,
        "original_temporal_text": record.original_temporal_text,
        "scheduled_at": record.scheduled_at,
        "temporal_kind": record.temporal_kind,
        "period_label": record.period_label,
        "attempt_number": record.attempt_number,
        "sent_at": record.sent_at,
        "awaiting_until": record.awaiting_until,
        "remarketing_eligible": record.remarketing_eligible,
        "last_bot_had_actionable_question": record.last_bot_had_actionable_question,
        "significant_commercial_exchange": record.significant_commercial_exchange,
        "commercially_closed": record.commercially_closed,
        "customer_commitment": record.customer_commitment,
        "permission_requested": record.permission_requested,
        "consent_source": record.consent_source,
        "fallback_resume_at": record.fallback_resume_at,
        "customer_agreed_at": record.scheduled_at
        if record.consent_source == ConsentSource.EXPLICIT_CUSTOMER_TIME.value
        else None,
        "opted_out": record.opted_out,
    }
