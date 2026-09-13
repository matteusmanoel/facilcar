"""TEST DOUBLE — Phase 11 follow-up replay harness.

Frente A/B/C/D should swap this module for domain policy, durable scheduler,
cancellation, and Composer. Goldens and ``gate_phase11`` land first on the
isolated tree, so this in-memory double keeps G1–G10 and E1–E12 deterministic.

Do not import from the production orchestrator send path.
No ``sleep``. Clock jumps go through ``sdr.domain.clock.set_clock``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from sdr.domain.clock import now_brt, parse_clock, set_clock
from sdr.domain.scheduling import STORE_HOURS

# ---------------------------------------------------------------------------
# Wait / task vocabulary (semantic; Frente A may rename, not drop)
# ---------------------------------------------------------------------------

WAIT_ACTIVE = "ACTIVE_QUALIFICATION"
WAIT_PAUSED = "PAUSED_WITH_FOLLOWUP"
WAIT_DUE = "FOLLOWUP_DUE"
WAIT_PROCESSING = "FOLLOWUP_PROCESSING"
WAIT_AFTER = "AWAITING_AFTER_FOLLOWUP"
WAIT_DORMANT = "DORMANT"

STATUS_PENDING = "PENDING"
STATUS_CLAIMED = "CLAIMED"
STATUS_SENT = "SENT"
STATUS_CANCELLED = "CANCELLED"
STATUS_RESCHEDULED = "RESCHEDULED"

CANCEL_CUSTOMER_REPLIED = "CUSTOMER_REPLIED"
CANCEL_HUMAN_ASSUMED = "HUMAN_ASSUMED"
CANCEL_OPT_OUT = "OPT_OUT"
CANCEL_RESET = "CONVERSATION_RESET"
CANCEL_SOLD = "VEHICLE_NO_LONGER_APPLICABLE"
CANCEL_SUPERSEDED = "SUPERSEDED"

DORMANT_AFTER = timedelta(hours=24)

_SECRET_KEYS = frozenset({
    "authorization",
    "api_key",
    "openai_api_key",
    "token",
    "secret",
    "password",
    "cpf",
    "cnpj",
    "cookie",
})

_PII_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"),
    re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b"),
    re.compile(r"sk-[A-Za-z0-9]{12,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{8,}", re.I),
    re.compile(r"OPENAI_API_KEY"),
    re.compile(r"postgresql://[^:\s]+:[^@\s]+@"),
)

_PRESSURE = (
    "vi que você sumiu",
    "vi que voce sumiu",
    "última chance",
    "ultima chance",
    "não perca",
    "nao perca",
    "urgente",
)


@dataclass
class FollowUpTask:
    id: str
    conversation_id: str
    reason: str
    status: str
    scheduled_at: datetime
    original_temporal_text: str
    consent_source: str
    consent_level: str
    attempt_number: int = 0
    maximum_attempts: int = 1
    ownership_revision: int = 0
    idempotency_key: str = ""
    claimed_by: str | None = None
    sent_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancel_reason: str | None = None
    vehicle_id: str | None = None
    vehicle_label: str | None = None
    outbound_text: str | None = None
    composer_calls: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "conversationId": self.conversation_id,
            "reason": self.reason,
            "status": self.status,
            "scheduledAt": self.scheduled_at.isoformat(),
            "originalTemporalText": self.original_temporal_text,
            "consentSource": self.consent_source,
            "consentLevel": self.consent_level,
            "attemptNumber": self.attempt_number,
            "maximumAttempts": self.maximum_attempts,
            "ownershipRevision": self.ownership_revision,
            "idempotencyKey": self.idempotency_key,
            "claimedBy": self.claimed_by,
            "sentAt": self.sent_at.isoformat() if self.sent_at else None,
            "cancelledAt": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "cancelReason": self.cancel_reason,
            "vehicleId": self.vehicle_id,
            "vehicleLabel": self.vehicle_label,
            "outboundText": self.outbound_text,
            "composerCalls": self.composer_calls,
        }


@dataclass
class TickResult:
    sent: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    cancelled: list[str] = field(default_factory=list)
    rescheduled: list[dict[str, Any]] = field(default_factory=list)
    claims: list[dict[str, Any]] = field(default_factory=list)
    composer_calls: int = 0
    llm_calls: int = 0
    wait_state: str = WAIT_ACTIVE


def apply_clock_jump(raw: Any) -> datetime:
    """Advance the injectable clock. Never sleeps."""
    if isinstance(raw, dict):
        if raw.get("to"):
            dt = set_clock(str(raw["to"]))
            if dt is None:
                raise ValueError("clock_jump.to did not parse")
            return dt
        current = now_brt()
        delta = timedelta(
            days=int(raw.get("days") or 0),
            hours=int(raw.get("hours") or 0),
            minutes=int(raw.get("minutes") or 0),
        )
        dt = set_clock(current + delta)
        if dt is None:
            raise ValueError("clock_jump delta did not parse")
        return dt
    dt = set_clock(str(raw))
    if dt is None:
        raise ValueError(f"clock_jump {raw!r} did not parse")
    return dt


def is_within_store_hours(dt: datetime | None = None) -> bool:
    instant = dt or now_brt()
    hours = STORE_HOURS.get(instant.weekday())
    if hours is None:
        return False
    open_h, close_h = hours
    minutes = instant.hour * 60 + instant.minute
    return open_h * 60 <= minutes < close_h * 60


def next_open_window(dt: datetime | None = None) -> datetime:
    """Next store-open instant (same day if still before open, else next open day)."""
    cursor = (dt or now_brt()).replace(second=0, microsecond=0)
    for offset in range(14):
        day = cursor + timedelta(days=offset)
        hours = STORE_HOURS.get(day.weekday())
        if hours is None:
            continue
        open_h, _close_h = hours
        candidate = day.replace(hour=open_h, minute=0, second=0, microsecond=0)
        if candidate > cursor or (offset == 0 and candidate >= cursor):
            if offset == 0 and is_within_store_hours(cursor):
                return cursor
            if candidate > cursor:
                return candidate
            if offset == 0 and cursor.hour * 60 + cursor.minute < open_h * 60:
                return candidate
        if offset > 0:
            return candidate
    return cursor + timedelta(days=1)


def pii_leaks(blob: str) -> list[str]:
    hits: list[str] = []
    for pattern in _PII_PATTERNS:
        found = pattern.findall(blob)
        hits.extend(str(item) for item in found)
    return hits


def sanitize_artifact(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in _SECRET_KEYS:
                out[key] = "[redacted]"
            else:
                out[key] = sanitize_artifact(item)
        return out
    if isinstance(value, list):
        return [sanitize_artifact(item) for item in value]
    if isinstance(value, str):
        text = value
        for pattern in _PII_PATTERNS:
            text = pattern.sub("[redacted]", text)
        return text
    return value


def _compose_fallback(task: FollowUpTask) -> str:
    label = task.vehicle_label or "o veículo que você viu"
    if task.reason == "DOCUMENTS_UNAVAILABLE":
        return "Conseguiu separar os comprovantes?"
    if task.reason == "DOCUMENTS_PROMISED":
        return "Conseguiu reunir os comprovantes que comentou que enviaria?"
    if task.reason == "DECISION_WITH_PARTNER":
        return f"Oi, conseguiu conversar sobre a {label}?"
    if task.reason == "CUSTOMER_WILL_RETURN":
        return f"Oi, ainda posso te ajudar com a {label}?"
    return f"Oi, ainda faz sentido seguirmos com a {label}?"


class FollowUpHarness:
    """In-memory scheduler used only by Phase 11 goldens/gate until A/B swap."""

    def __init__(self, *, scenario_name: str, thread_id: str) -> None:
        self.scenario_name = scenario_name
        self.thread_id = thread_id
        self.tasks: list[FollowUpTask] = []
        self.wait_state = WAIT_ACTIVE
        self.transitions: list[dict[str, Any]] = []
        self.clock_jumps: list[dict[str, Any]] = []
        self.claims: list[dict[str, Any]] = []
        self.cancels: list[dict[str, Any]] = []
        self.sends: list[dict[str, Any]] = []
        self.inventory: dict[str, str] = {}
        self.composer_calls = 0
        self.consent: list[dict[str, Any]] = []
        self.reasons: list[str] = []

    def snapshot(self) -> dict[str, Any]:
        return {
            "wait_state": self.wait_state,
            "followup_sends": len(self.sends),
            "composer_calls": self.composer_calls,
            "task_count": len(self.tasks),
            "pending": sum(1 for t in self.tasks if t.status == STATUS_PENDING),
            "cancelled": sum(1 for t in self.tasks if t.status == STATUS_CANCELLED),
            "idempotency_keys": [t.idempotency_key for t in self.tasks],
            "inventory": dict(self.inventory),
        }

    def _set_wait(self, nxt: str, *, reason: str) -> None:
        prev = self.wait_state
        if prev == nxt:
            return
        self.wait_state = nxt
        self.transitions.append(
            {
                "from": prev,
                "to": nxt,
                "reason": reason,
                "clock": now_brt().isoformat(),
            }
        )

    def record_clock_jump(self, raw: Any, instant: datetime) -> None:
        self.clock_jumps.append(
            {"raw": raw, "clock": instant.isoformat(), "wait_state": self.wait_state}
        )
        self._maybe_dormant()

    def override_inventory(self, spec: dict[str, Any]) -> dict[str, Any]:
        vehicle_id = str(spec.get("vehicle_id") or spec.get("id") or "").strip()
        status = str(spec.get("status") or "SOLD").strip().upper()
        if vehicle_id:
            self.inventory[vehicle_id] = status
        return {"vehicle_id": vehicle_id, "status": status}

    def schedule_from_turn(self, turn_def: dict[str, Any], *, ownership_revision: int = 0) -> FollowUpTask | None:
        spec = turn_def.get("followup") if isinstance(turn_def.get("followup"), dict) else {}
        if not spec or not spec.get("schedule"):
            return None
        scheduled_raw = spec.get("scheduled_at")
        scheduled = parse_clock(str(scheduled_raw)) if scheduled_raw else None
        if scheduled is None:
            scheduled = next_open_window(now_brt() + timedelta(days=1))
        for existing in self.tasks:
            if existing.status == STATUS_PENDING:
                existing.status = STATUS_CANCELLED
                existing.cancelled_at = now_brt()
                existing.cancel_reason = CANCEL_SUPERSEDED
                self.cancels.append(existing.as_dict())
        task = FollowUpTask(
            id=str(spec.get("id") or uuid4()),
            conversation_id=self.thread_id,
            reason=str(spec.get("reason") or "OTHER_CONTEXTUAL_PAUSE"),
            status=STATUS_PENDING,
            scheduled_at=scheduled,
            original_temporal_text=str(spec.get("original_temporal_text") or ""),
            consent_source=str(spec.get("consent_source") or "CONTEXTUAL"),
            consent_level=str(spec.get("consent_level") or "CONTEXTUAL_WITHOUT_TIME"),
            ownership_revision=ownership_revision,
            idempotency_key=str(spec.get("idempotency_key") or f"{self.thread_id}:{scheduled.isoformat()}"),
            vehicle_id=spec.get("vehicle_id"),
            vehicle_label=spec.get("vehicle_label"),
        )
        self.tasks.append(task)
        self.reasons.append(task.reason)
        self.consent.append(
            {
                "source": task.consent_source,
                "level": task.consent_level,
                "temporal": task.original_temporal_text,
            }
        )
        self._set_wait(WAIT_PAUSED, reason="scheduled")
        return task

    def after_customer_inbound(self, turn_def: dict[str, Any], *, ownership_revision: int = 0) -> None:
        if turn_def.get("opt_out"):
            self.cancel(CANCEL_OPT_OUT)
            return
        pending = [t for t in self.tasks if t.status == STATUS_PENDING]
        if pending:
            self.cancel(CANCEL_CUSTOMER_REPLIED)
        self.schedule_from_turn(turn_def, ownership_revision=ownership_revision)

    def on_admin(self, event_name: str) -> None:
        if event_name == "assume":
            self.cancel(CANCEL_HUMAN_ASSUMED)
        # resume must not restore cancelled tasks

    def on_reset(self) -> None:
        self.cancel(CANCEL_RESET)

    def cancel(self, reason: str) -> None:
        now = now_brt()
        for task in self.tasks:
            if task.status in {STATUS_PENDING, STATUS_CLAIMED, STATUS_RESCHEDULED}:
                task.status = STATUS_CANCELLED
                task.cancelled_at = now
                task.cancel_reason = reason
                self.cancels.append(task.as_dict())
        if self.sends:
            self._set_wait(WAIT_DORMANT, reason=reason)
        else:
            self._set_wait(WAIT_ACTIVE, reason=reason)

    def _maybe_dormant(self) -> None:
        now = now_brt()
        for task in self.tasks:
            if task.status != STATUS_SENT or task.sent_at is None:
                continue
            if now >= task.sent_at + DORMANT_AFTER and self.wait_state == WAIT_AFTER:
                self._set_wait(WAIT_DORMANT, reason="no_reply_after_followup")

    def _vehicle_sold(self, task: FollowUpTask) -> bool:
        if not task.vehicle_id:
            return False
        return self.inventory.get(task.vehicle_id) == "SOLD"

    def _claim(self, task: FollowUpTask, worker_id: str) -> bool:
        if task.status != STATUS_PENDING:
            return False
        task.status = STATUS_CLAIMED
        task.claimed_by = worker_id
        self.claims.append(
            {
                "task_id": task.id,
                "worker": worker_id,
                "idempotencyKey": task.idempotency_key,
                "clock": now_brt().isoformat(),
            }
        )
        return True

    def _send(self, task: FollowUpTask) -> str:
        self._set_wait(WAIT_PROCESSING, reason="claimed")
        self.composer_calls += 1
        task.composer_calls += 1
        text = _compose_fallback(task)
        low = text.lower()
        if any(p in low for p in _PRESSURE):
            text = f"Oi, ainda faz sentido falarmos da {task.vehicle_label or 'proposta'}?"
        task.status = STATUS_SENT
        task.attempt_number += 1
        task.sent_at = now_brt()
        task.outbound_text = text
        self.sends.append(
            {
                "task_id": task.id,
                "text": text,
                "idempotencyKey": task.idempotency_key,
                "clock": task.sent_at.isoformat(),
                "attemptNumber": task.attempt_number,
            }
        )
        self._set_wait(WAIT_AFTER, reason="sent")
        return text

    def tick(self, spec: dict[str, Any] | bool | None = None) -> TickResult:
        payload = spec if isinstance(spec, dict) else {}
        kind = str(payload.get("kind") or "due").lower()
        workers = list(payload.get("workers") or ["w1"])
        result = TickResult(wait_state=self.wait_state)
        if kind == "dormant":
            self._maybe_dormant()
            result.wait_state = self.wait_state
            return result
        now = now_brt()
        due = [
            t
            for t in self.tasks
            if t.status == STATUS_PENDING and t.scheduled_at <= now
        ]
        if not due:
            result.wait_state = self.wait_state
            return result
        self._set_wait(WAIT_DUE, reason="due")
        for task in due:
            claimed = False
            for worker in workers:
                if self._claim(task, str(worker)):
                    claimed = True
                    result.claims.append({"task_id": task.id, "worker": worker})
                    break
            if not claimed:
                result.skipped.append(task.id)
                continue
            if task.attempt_number >= task.maximum_attempts and task.status == STATUS_SENT:
                result.skipped.append(task.id)
                continue
            if self._vehicle_sold(task):
                task.status = STATUS_CANCELLED
                task.cancelled_at = now
                task.cancel_reason = CANCEL_SOLD
                task.claimed_by = None
                self.cancels.append(task.as_dict())
                result.cancelled.append(task.id)
                self._set_wait(WAIT_DORMANT, reason=CANCEL_SOLD)
                continue
            if not is_within_store_hours(now):
                nxt = next_open_window(now)
                task.status = STATUS_PENDING
                task.claimed_by = None
                task.scheduled_at = nxt
                result.rescheduled.append(
                    {"task_id": task.id, "scheduled_at": nxt.isoformat()}
                )
                self._set_wait(WAIT_PAUSED, reason="after_hours")
                continue
            if self.wait_state in {WAIT_DORMANT} and not due:
                result.skipped.append(task.id)
                continue
            text = self._send(task)
            result.sent.append(text)
            result.composer_calls += 1
        result.llm_calls = 0
        result.wait_state = self.wait_state
        return result

    def pending_tasks(self) -> list[FollowUpTask]:
        return [t for t in self.tasks if t.status == STATUS_PENDING]


def two_workers_claim_once(harness: FollowUpHarness) -> dict[str, Any]:
    """Deterministic G6 helper: two workers, one claim, one send, one key."""
    tick = harness.tick({"kind": "due", "workers": ["w1", "w2"]})
    return {
        "claims": len(harness.claims),
        "composer_calls": harness.composer_calls,
        "sends": len(harness.sends),
        "idempotency_keys": {t.idempotency_key for t in harness.tasks},
        "sent_texts": tick.sent,
    }
