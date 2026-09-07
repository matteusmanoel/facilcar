"""Isolated CRM store for golden replay — same payload contract as LeadRepository.

Does not write to production. Persist then reread to verify the handoff record.
"""

from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from typing import Any

from sdr.domain.types import ConversationCanonicalState
from sdr.domain.vehicle_roles import get_customer_vehicle, get_desired_vehicle
from sdr.domain.vendor_summary import compose_vendor_summary
from sdr.infrastructure.lead_repository import INTENT_TO_LEAD_TYPE


def build_crm_payload(state: ConversationCanonicalState, composed: Any = None) -> dict[str, Any]:
    """Structured payload equivalent to what mark_qualified_for_handoff persists."""
    if composed is None:
        composed = compose_vendor_summary(state)
    summary = composed.text
    desired = get_desired_vehicle(state.facts)
    customer = get_customer_vehicle(state.facts)
    return {
        "id": str(uuid.uuid4()),
        "thread_id": state.thread_id,
        "status": "QUALIFIED",
        "intent": state.intent.value,
        "lead_type": INTENT_TO_LEAD_TYPE.get(state.intent, "VEHICLE_INTEREST"),
        "priority": "HOT" if state.signals.explicit_handoff else (
            state.temperature.value if state.temperature else "WARM"
        ),
        "name": state.customer.name or state.facts.get("name"),
        "phone": state.customer.phone,
        "summary": summary,
        "juliaSummary": summary,
        "desired_vehicle": desired,
        "customer_vehicle": customer,
        "payment_method": state.facts.get("payment_method"),
        "collected_fields": list(state.collected_fields or []),
        "missing_fields": list(state.missing_fields or []),
        "deferred_fields": list(state.deferred_fields or []),
        "handoff_reason": state.lifecycle.handoff_reason,
        "visit_preferred_time": state.visit_preferred_time,
        "profile_complete": bool(state.profile_complete),
        "handoff_ready": bool(state.handoff_ready),
        "summary_validation": composed.validation,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


class IsolatedCrmStore:
    def __init__(self) -> None:
        self._records: dict[str, dict[str, Any]] = {}
        self._payloads_sent: dict[str, dict[str, Any]] = {}

    def persist_handoff(self, state: ConversationCanonicalState, composed: Any = None) -> dict[str, Any]:
        payload = build_crm_payload(state, composed=composed)
        self._payloads_sent[state.thread_id] = copy.deepcopy(payload)
        stored = copy.deepcopy(payload)
        self._records[state.thread_id] = stored
        return stored

    def reread(self, thread_id: str) -> dict[str, Any] | None:
        rec = self._records.get(thread_id)
        return copy.deepcopy(rec) if rec else None

    def payload_sent(self, thread_id: str) -> dict[str, Any] | None:
        rec = self._payloads_sent.get(thread_id)
        return copy.deepcopy(rec) if rec else None

    def verify(self, thread_id: str) -> dict[str, Any]:
        sent = self.payload_sent(thread_id)
        stored = self.reread(thread_id)
        return {
            "summary_generated": bool(sent and sent.get("summary")),
            "payload_sent": sent,
            "record_persisted": stored is not None,
            "record_reread": stored,
            "matches_payload": sent == stored,
        }
