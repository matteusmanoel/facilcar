"""Authorized CRM facts — the only payload the summary generator may use."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sdr.domain.debts import compute_debt_status
from sdr.domain.types import ConversationCanonicalState
from sdr.domain.vehicle_roles import format_vehicle_label, get_customer_vehicle, get_desired_vehicle


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
    visit_preferred_time: str | None = None
    visit_pending_vendor_confirm: bool = False
    missing_fields: list[str] = field(default_factory=list)
    deferred_fields: list[str] = field(default_factory=list)
    handoff_reason: str | None = None
    amount_needed: Any = None
    leave_at_store: Any = None
    profile_complete: bool = False
    handoff_ready: bool = False

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
            "visit_preferred_time": self.visit_preferred_time,
            "visit_pending_vendor_confirm": self.visit_pending_vendor_confirm,
            "missing_fields": list(self.missing_fields),
            "deferred_fields": list(self.deferred_fields),
            "handoff_reason": self.handoff_reason,
            "amount_needed": self.amount_needed,
            "leave_at_store": self.leave_at_store,
            "profile_complete": self.profile_complete,
            "handoff_ready": self.handoff_ready,
        }


def build_authorized_facts(state: ConversationCanonicalState) -> AuthorizedFacts:
    facts = state.facts or {}
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
    status = customer.get("debt_status") or compute_debt_status(checks)
    visit = state.visit_preferred_time
    return AuthorizedFacts(
        name=name,
        intent=state.intent.value,
        desired_vehicle=desired,
        customer_vehicle=customer,
        payment_method=facts.get("payment_method"),
        payment_applies_to=facts.get("payment_applies_to"),
        down_payment=facts.get("down_payment"),
        desired_installment=facts.get("desired_installment"),
        financing_status=customer.get("financing_status"),
        debt_status=status if isinstance(status, str) else None,
        debt_checks=dict(checks or {}),
        debt_types=customer.get("debt_types") if customer.get("debt_types") not in {"sem_multas"} else None,
        price_expectation=customer.get("price_expectation") or facts.get("trade_price_expectation"),
        documents_received=bool(state.document_received or facts.get("documents_received")),
        documents_deferred=deferred,
        visit_preferred_time=visit,
        visit_pending_vendor_confirm=bool(visit),
        missing_fields=list(state.missing_fields or []),
        deferred_fields=deferred,
        handoff_reason=state.lifecycle.handoff_reason,
        amount_needed=facts.get("amount_needed"),
        leave_at_store=facts.get("leave_at_store"),
        profile_complete=bool(state.profile_complete),
        handoff_ready=bool(state.handoff_ready),
    )


def desired_label(auth: AuthorizedFacts) -> str | None:
    return format_vehicle_label(auth.desired_vehicle)


def customer_label(auth: AuthorizedFacts) -> str | None:
    return format_vehicle_label(auth.customer_vehicle)
