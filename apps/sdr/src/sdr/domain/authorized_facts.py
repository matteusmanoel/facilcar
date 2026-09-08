"""Authorized CRM facts — the only payload the summary generator may use."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sdr.domain.age import compute_age
from sdr.domain.debts import compute_debt_status, persistable_checks
from sdr.domain.document_status import deferred_components
from sdr.domain.qualifications import field_is_applicable
from sdr.domain.types import ConversationCanonicalState
from sdr.domain.vehicle_roles import (
    canonicalize_vehicle_roles,
    format_vehicle_label,
    get_customer_vehicle,
    get_desired_vehicle,
)


def _is_placeholder_name(name: str | None) -> bool:
    value = (name or "").strip()
    return not value or value.lower().startswith("whatsapp ")


@dataclass
class AuthorizedFacts:
    name: str | None = None
    intent: str = "unknown"
    desired_vehicle: dict[str, Any] = field(default_factory=dict)
    customer_vehicle: dict[str, Any] = field(default_factory=dict)
    payment_method: str | None = None
    payment_applies_to: str | None = None
    down_payment: Any = None
    desired_installment: Any = None
    financing_status: str | None = None
    debt_status: str | None = None
    debt_checks: dict[str, Any] = field(default_factory=dict)
    debt_types: str | None = None
    price_expectation: Any = None
    documents_received: bool = False
    documents_deferred: list[str] = field(default_factory=list)
    document_status: dict[str, str] = field(default_factory=dict)
    visit_preferred_time: str | None = None
    visit_pending_vendor_confirm: bool = False
    age: int | None = None
    birth_date: str | None = None
    missing_fields: list[str] = field(default_factory=list)
    deferred_fields: list[str] = field(default_factory=list)
    handoff_reason: str | None = None
    amount_needed: Any = None
    leave_at_store: Any = None
    profile_complete: bool = False
    handoff_ready: bool = False
    documents_applicable: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "intent": self.intent,
            "desired_vehicle": dict(self.desired_vehicle),
            "customer_vehicle": {
                k: v for k, v in self.customer_vehicle.items() if k != "_provenance"
            },
            "payment_method": self.payment_method,
            "payment_applies_to": self.payment_applies_to,
            "down_payment": self.down_payment,
            "desired_installment": self.desired_installment,
            "financing_status": self.financing_status,
            "debt_status": self.debt_status,
            "debt_checks": dict(self.debt_checks),
            "debt_types": self.debt_types,
            "price_expectation": self.price_expectation,
            "documents_received": self.documents_received,
            "documents_deferred": list(self.documents_deferred),
            "document_status": dict(self.document_status),
            "visit_preferred_time": self.visit_preferred_time,
            "visit_pending_vendor_confirm": self.visit_pending_vendor_confirm,
            "age": self.age,
            "birth_date": self.birth_date,
            "missing_fields": list(self.missing_fields),
            "deferred_fields": list(self.deferred_fields),
            "handoff_reason": self.handoff_reason,
            "amount_needed": self.amount_needed,
            "leave_at_store": self.leave_at_store,
            "profile_complete": self.profile_complete,
            "handoff_ready": self.handoff_ready,
            "documents_applicable": self.documents_applicable,
        }


def build_authorized_facts(state: ConversationCanonicalState) -> AuthorizedFacts:
    facts = canonicalize_vehicle_roles(dict(state.facts or {}), state.intent)
    desired = {
        k: v
        for k, v in get_desired_vehicle(facts).items()
        if k != "_provenance" and v not in (None, "")
    }
    customer = {
        k: v
        for k, v in get_customer_vehicle(facts).items()
        if k != "_provenance" and v not in (None, "")
    }
    name = (state.customer.name or facts.get("name") or "").strip() or None
    if name and _is_placeholder_name(name):
        name = None
    deferred = list(state.deferred_fields or [])
    checks = customer.get("debt_checks") if isinstance(customer.get("debt_checks"), dict) else {}
    if checks:
        checks = persistable_checks(checks)
        customer["debt_checks"] = checks
    status = customer.get("debt_status") or compute_debt_status(checks)
    visit = state.visit_preferred_time
    intent = state.intent.value
    doc_status = facts.get("document_status") if isinstance(facts.get("document_status"), dict) else {}
    deferred = list(state.deferred_fields or []) or deferred_components(doc_status)
    docs_ok = field_is_applicable(state, "documents")
    if intent == "purchase":
        customer = {}
        status = None
        checks = {}
    if not docs_ok:
        deferred = []
        doc_status = {}
    if intent in {"sale", "consignment", "refinancing"}:
        desired = {}
    applicable_missing = [
        f for f in (state.missing_fields or []) if field_is_applicable(state, f)
    ]
    birth_raw = facts.get("birth_date")
    birth = str(birth_raw).strip() if birth_raw else None
    return AuthorizedFacts(
        name=name,
        intent=intent,
        desired_vehicle=desired,
        customer_vehicle=customer,
        payment_method=facts.get("payment_method"),
        payment_applies_to=facts.get("payment_applies_to"),
        down_payment=facts.get("down_payment") if intent != "purchase" or facts.get("payment_method") != "cash" else None,
        desired_installment=facts.get("desired_installment") if intent in {"purchase_financing", "trade"} else None,
        financing_status=customer.get("financing_status") if customer else None,
        debt_status=status if isinstance(status, str) and customer else None,
        debt_checks=dict(checks or {}) if customer else {},
        debt_types=customer.get("debt_types") if customer and customer.get("debt_types") not in {"sem_multas"} else None,
        price_expectation=customer.get("price_expectation") or facts.get("trade_price_expectation") if customer else None,
        documents_received=bool(state.document_received or facts.get("documents_received")) if docs_ok else False,
        documents_deferred=deferred if docs_ok else [],
        document_status=dict(doc_status) if docs_ok else {},
        visit_preferred_time=visit,
        visit_pending_vendor_confirm=bool(visit),
        age=compute_age(birth),
        birth_date=birth,
        missing_fields=applicable_missing,
        deferred_fields=list(state.deferred_fields or []) if docs_ok else [],
        handoff_reason=state.lifecycle.handoff_reason,
        amount_needed=facts.get("amount_needed") if intent == "refinancing" else None,
        leave_at_store=facts.get("leave_at_store") if intent == "consignment" else None,
        profile_complete=bool(state.profile_complete),
        handoff_ready=bool(state.handoff_ready),
        documents_applicable=docs_ok,
    )


def desired_label(auth: AuthorizedFacts) -> str | None:
    return format_vehicle_label(auth.desired_vehicle)


def customer_label(auth: AuthorizedFacts) -> str | None:
    return format_vehicle_label(auth.customer_vehicle)
