"""Isolated CRM store for golden replay — same payload contract as LeadRepository.

Does not write to production. Persist then reread to verify the handoff record.
"""

from __future__ import annotations

import copy
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from sdr.domain.commercial_snapshot import (
    INTENT_TO_LEAD_TYPE,
    build_commercial_snapshot,
    original_message_from,
)
from sdr.domain.ownership import (
    confirm_vendor_dispatch,
    vendor_notify_idempotency_key,
)
from sdr.domain.types import ConversationCanonicalState
from sdr.domain.vehicle_roles import get_customer_vehicle, get_desired_vehicle
from sdr.domain.vendor_summary import compose_vendor_summary


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
        "summary_origin": getattr(composed, "origin", None),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _record_from_snapshot(
    *,
    lead_id: str,
    thread_id: str,
    snapshot: Any,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    interests = [
        {"vehicleId": vid, "isPrimary": vid == snapshot.primary_vehicle_id}
        for vid in snapshot.interest_ids
    ]
    if snapshot.primary_vehicle_id and snapshot.primary_vehicle_id not in snapshot.interest_ids:
        interests.append({"vehicleId": snapshot.primary_vehicle_id, "isPrimary": True})
    financing = None
    if snapshot.financing:
        fin = snapshot.financing
        financing = {
            "desiredMonthlyPayment": fin.desired_monthly_payment,
            "desiredInstallments": fin.desired_installments_count,
            "downPayment": fin.down_payment,
            "cpf": fin.cpf,
            "birthDate": fin.birth_date,
            "hasDriverLicense": fin.has_driver_license,
            "vehicleModel": fin.vehicle_model,
            "vehicleYear": fin.vehicle_year,
            "vehicleId": fin.vehicle_id,
            "paymentMethod": fin.payment_method,
            "zeroDown": fin.zero_down,
        }
    visit = snapshot.visit
    rec = dict(existing or {})
    rec.update(
        {
            "id": lead_id,
            "thread_id": thread_id,
            "status": snapshot.status if snapshot.status == "QUALIFIED" or rec.get("status") != "QUALIFIED" else rec.get("status"),
            "type": snapshot.lead_type,
            "juliaSummary": snapshot.julia_summary,
            "summary": snapshot.julia_summary,
            "message": rec.get("message") if rec.get("message") else snapshot.original_message,
            "name": snapshot.name or rec.get("name"),
            "temperature": snapshot.temperature,
            "vehicleId": snapshot.primary_vehicle_id,
            "commercialRevision": snapshot.revision,
            "interest_ids": list(snapshot.interest_ids),
            "vehicleInterests": interests,
            "financingRequest": financing,
            "sellRequest": {} if snapshot.sell else rec.get("sellRequest"),
            "visitInterest": {
                "interest": visit.interest,
                "declined": visit.declined,
                "accepted": visit.accepted,
                "preferredDate": visit.date,
                "period": visit.period,
                "preferredTime": visit.time,
                "originalText": visit.raw,
                "dateHint": visit.display,
                "locationSent": visit.location_sent,
            },
            "documents": [
                {
                    "component": d.component,
                    "commerciallyReceived": d.commercially_received,
                    "storageStatus": d.storage_status,
                    "downloadable": d.downloadable,
                }
                for d in snapshot.documents
            ],
            "metadataJson": snapshot.metadata,
            "city": snapshot.city,
            "state": snapshot.state,
        }
    )
    if rec.get("status") != "QUALIFIED" and snapshot.status == "QUALIFIED":
        rec["status"] = "QUALIFIED"
    if snapshot.status == "QUALIFIED":
        rec["status"] = "QUALIFIED"
    return rec


class IsolatedCrmStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records: dict[str, dict[str, Any]] = {}
        self._by_id: dict[str, dict[str, Any]] = {}
        self._payloads_sent: dict[str, dict[str, Any]] = {}
        self._notify_keys: set[str] = set()
        self._notify_at: dict[str, str] = {}
        self.qualified_notifications: int = 0
        self.handoff_count: int = 0
        self.fail_before_confirm: bool = False

    def _confirm_dispatch(self, state: ConversationCanonicalState, rec: dict[str, Any]) -> bool:
        """Stamp vendor notify once. QUALIFIED status is not confirmation."""
        key = vendor_notify_idempotency_key(state)
        existing_ts = rec.get("vendorNotifiedAt") or self._notify_at.get(key)
        already = key in self._notify_keys or bool(existing_ts)
        if already:
            self._notify_keys.add(key)
            ts = state.vendor_notified_at or existing_ts
            if ts and not state.vendor_notified_at:
                state.vendor_notified_at = str(ts)
            if state.vendor_notified_at:
                rec["vendorNotifiedAt"] = state.vendor_notified_at
                self._notify_at[key] = state.vendor_notified_at
            return False
        confirm_vendor_dispatch(state)
        self._notify_keys.add(key)
        self._notify_at[key] = str(state.vendor_notified_at)
        rec["vendorNotifiedAt"] = state.vendor_notified_at
        self.handoff_count += 1
        self.qualified_notifications += 1
        return True

    def persist_handoff(
        self,
        state: ConversationCanonicalState,
        composed: Any = None,
        *,
        first_inbound: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            existing = self._records.get(state.thread_id)
            existing_id = None
            if getattr(state, "active_lead_ids", None):
                existing_id = str(state.active_lead_ids[0])
            elif existing and existing.get("id"):
                existing_id = str(existing["id"])
            if existing_id and self._by_id.get(existing_id) is not None:
                rec = self.sync_from_state(
                    existing_id,
                    state,
                    qualify=True,
                    first_inbound=first_inbound,
                )
                self._payloads_sent[state.thread_id] = copy.deepcopy(rec)
                return rec
            payload = build_crm_payload(state, composed=composed)
            snapshot = build_commercial_snapshot(
                state,
                first_inbound=first_inbound,
                qualify=True,
            )
            rec = _record_from_snapshot(
                lead_id=str(payload["id"]),
                thread_id=state.thread_id,
                snapshot=snapshot,
            )
            message = rec.get("message") or original_message_from(
                first_inbound, payload.get("summary") or ""
            )
            stored = {
                **payload,
                "vehicleId": rec.get("vehicleId"),
                "vehicleInterests": rec.get("vehicleInterests"),
                "interest_ids": rec.get("interest_ids"),
                "financingRequest": rec.get("financingRequest"),
                "visitInterest": rec.get("visitInterest"),
                "documents": rec.get("documents"),
                "message": message,
                "commercialRevision": rec.get("commercialRevision"),
                "type": rec.get("type") or payload.get("lead_type"),
                "temperature": rec.get("temperature"),
                "juliaSummary": rec.get("juliaSummary") or payload.get("juliaSummary"),
            }
            self._records[state.thread_id] = stored
            self._by_id[str(stored["id"])] = stored
            if self.fail_before_confirm:
                raise RuntimeError("handoff dispatch confirmation failed")
            self._confirm_dispatch(state, stored)
            self._payloads_sent[state.thread_id] = copy.deepcopy(stored)
            return stored

    def create_from_state(
        self,
        state: ConversationCanonicalState,
        *,
        first_inbound: str | None = None,
    ) -> dict[str, Any]:
        snapshot = build_commercial_snapshot(state, first_inbound=first_inbound, qualify=False)
        lead_id = str(uuid.uuid4())
        rec = _record_from_snapshot(lead_id=lead_id, thread_id=state.thread_id, snapshot=snapshot)
        rec["status"] = "NEW"
        self._records[state.thread_id] = rec
        self._by_id[lead_id] = rec
        return copy.deepcopy(rec)

    def sync_from_state(
        self,
        lead_id: str,
        state: ConversationCanonicalState,
        *,
        qualify: bool = False,
        first_inbound: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            return self._sync_from_state_locked(
                lead_id, state, qualify=qualify, first_inbound=first_inbound
            )

    def _sync_from_state_locked(
        self,
        lead_id: str,
        state: ConversationCanonicalState,
        *,
        qualify: bool = False,
        first_inbound: str | None = None,
    ) -> dict[str, Any]:
        existing = self._by_id.get(lead_id)
        if existing is None:
            raise KeyError(lead_id)
        already = existing.get("status") == "QUALIFIED"
        snapshot = build_commercial_snapshot(
            state,
            first_inbound=first_inbound,
            qualify=qualify,
            already_qualified=already,
        )
        stored_rev = int(existing.get("commercialRevision") or 0)
        if snapshot.revision < stored_rev:
            out = copy.deepcopy(existing)
            out["stale_rejected"] = True
            return out
        rec = _record_from_snapshot(
            lead_id=lead_id,
            thread_id=state.thread_id,
            snapshot=snapshot,
            existing=existing,
        )
        if already:
            rec["status"] = "QUALIFIED"
        elif qualify:
            rec["status"] = "QUALIFIED"
        else:
            rec["status"] = existing.get("status") or "NEW"
        if qualify:
            if self.fail_before_confirm:
                self._by_id[lead_id] = rec
                self._records[state.thread_id] = rec
                raise RuntimeError("handoff dispatch confirmation failed")
            self._confirm_dispatch(state, rec)
        else:
            if existing.get("vendorNotifiedAt"):
                rec["vendorNotifiedAt"] = existing.get("vendorNotifiedAt")
        self._by_id[lead_id] = rec
        self._records[state.thread_id] = rec
        self._payloads_sent[state.thread_id] = copy.deepcopy(rec)
        return copy.deepcopy(rec)

    def reread(self, thread_id: str) -> dict[str, Any] | None:
        rec = self._records.get(thread_id)
        return copy.deepcopy(rec) if rec else None

    def reread_id(self, lead_id: str) -> dict[str, Any] | None:
        rec = self._by_id.get(lead_id)
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
