"""Commercial CRM snapshot — derived only from consolidated canonical state.

Maps authorized facts onto Lead / FinancingRequest / VisitInterest / interests
without reconstructing from the last inbound bubble. Monthly installment amount
must never be written to FinancingRequest.desiredInstallments (month count).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sdr.domain.authorized_facts import build_authorized_facts, desired_label
from sdr.domain.types import BusinessIntent, ConversationCanonicalState
from sdr.domain.vendor_summary import compose_vendor_summary, is_placeholder_display_name

INTENT_TO_LEAD_TYPE: dict[BusinessIntent, str] = {
    BusinessIntent.PURCHASE: "VEHICLE_INTEREST",
    BusinessIntent.PURCHASE_FINANCING: "FINANCING",
    BusinessIntent.TRADE: "TRADE_IN",
    BusinessIntent.SALE: "SELL_VEHICLE",
    BusinessIntent.CONSIGNMENT: "CONSIGNMENT",
    BusinessIntent.REFINANCING: "REFINANCING",
}

# FinancingRequest.desiredInstallments is prazo (month count 1–84), not R$/mês.
DESIRED_INSTALLMENTS_IS_MONTH_COUNT = True
MAX_PLAUSIBLE_INSTALLMENT_MONTHS = 84


@dataclass
class VisitSnapshot:
    interest: bool = False
    declined: bool = False
    accepted: bool = False
    date: str | None = None
    period: str | None = None
    time: str | None = None
    raw: str | None = None
    display: str | None = None
    location_sent: bool = False


@dataclass
class FinancingSnapshot:
    payment_method: str | None = None
    down_payment: float | None = None
    zero_down: bool = False
    desired_monthly_payment: float | None = None
    desired_installments_count: int | None = None
    cpf: str | None = None
    birth_date: str | None = None
    has_driver_license: bool | None = None
    vehicle_model: str | None = None
    vehicle_year: int | None = None
    vehicle_id: str | None = None
    notes: str | None = None


@dataclass
class DocumentSnapshot:
    component: str
    commercially_received: bool
    storage_status: str
    downloadable: bool


@dataclass
class CommercialSnapshot:
    """What the CRM must persist for one sync of a lead."""

    lead_type: str
    status: str
    julia_summary: str
    original_message: str | None
    name: str | None
    temperature: str | None
    primary_vehicle_id: str | None
    interest_ids: list[str] = field(default_factory=list)
    financing: FinancingSnapshot | None = None
    sell: bool = False
    visit: VisitSnapshot = field(default_factory=VisitSnapshot)
    documents: list[DocumentSnapshot] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    revision: int = 0
    notify_qualified: bool = False
    city: str | None = None
    state: str | None = None


def _as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_year(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        year = int(value)
    except (TypeError, ValueError):
        return None
    if 1900 <= year <= 2100:
        return year
    return None


def original_message_from(
    first_inbound: str | None,
    summary: str,
) -> str | None:
    """Customer first bubble — never a second copy of juliaSummary."""
    text = (first_inbound or "").strip()
    if not text:
        return None
    if text == (summary or "").strip():
        return None
    if text.lower().startswith("intent:"):
        return None
    return text


def monthly_payment_from_facts(facts: dict[str, Any]) -> float | None:
    """R$/mês from canonical desired_installment — never a month count."""
    return _as_float(facts.get("desired_installment"))


def installment_count_from_facts(facts: dict[str, Any]) -> int | None:
    """Only an explicit month-count field — never desired_installment R$."""
    raw = facts.get("desired_installments_count") or facts.get("installment_count")
    try:
        count = int(raw)
    except (TypeError, ValueError):
        return None
    if 1 <= count <= MAX_PLAUSIBLE_INSTALLMENT_MONTHS:
        return count
    return None


def _visit_snapshot(state: ConversationCanonicalState) -> VisitSnapshot:
    return VisitSnapshot(
        interest=bool(getattr(state, "visit_interest", False) or state.visit_preferred_time),
        declined=bool(getattr(state, "visit_declined", False)),
        accepted=bool(getattr(state, "visit_accepted_offered", False)),
        date=getattr(state, "visit_date", None),
        period=getattr(state, "visit_period", None),
        time=getattr(state, "visit_time", None),
        raw=getattr(state, "visit_raw", None),
        display=state.visit_preferred_time,
        location_sent=bool(getattr(state, "location_sent", False)),
    )


def _document_snapshots(state: ConversationCanonicalState) -> list[DocumentSnapshot]:
    status = state.facts.get("document_status") if isinstance(state.facts.get("document_status"), dict) else {}
    storage = state.facts.get("document_storage") if isinstance(state.facts.get("document_storage"), dict) else {}
    out: list[DocumentSnapshot] = []
    for key, value in status.items():
        received = value == "received"
        raw_storage = storage.get(key)
        if isinstance(raw_storage, dict):
            storage_status = str(raw_storage.get("status") or "PENDING")
        elif raw_storage:
            storage_status = str(raw_storage)
        else:
            storage_status = "PENDING"
        downloadable = received and storage_status.upper() == "STORED"
        out.append(
            DocumentSnapshot(
                component=str(key),
                commercially_received=received,
                storage_status=storage_status,
                downloadable=downloadable,
            )
        )
    return out


def financing_snapshot(state: ConversationCanonicalState) -> FinancingSnapshot | None:
    payment = str(state.facts.get("payment_method") or "").strip().lower()
    if state.intent not in (
        BusinessIntent.PURCHASE_FINANCING,
        BusinessIntent.REFINANCING,
    ) and payment != "financing":
        return None
    facts = state.facts
    down = _as_float(facts.get("down_payment"))
    auth = build_authorized_facts(state)
    model = desired_label(auth) or facts.get("desired_model") or facts.get("vehicle_model")
    year = _as_year(
        (auth.desired_vehicle or {}).get("year")
        or facts.get("vehicle_year")
        or facts.get("year")
    )
    cnh = facts.get("document_type") == "CNH" or (
        isinstance(facts.get("document_status"), dict)
        and facts["document_status"].get("cnh") == "received"
    )
    return FinancingSnapshot(
        payment_method=payment or "financing",
        down_payment=down,
        zero_down=down == 0,
        desired_monthly_payment=monthly_payment_from_facts(facts),
        desired_installments_count=installment_count_from_facts(facts),
        cpf=str(facts["cpf"]).strip() if facts.get("cpf") else None,
        birth_date=str(facts["birth_date"]).strip() if facts.get("birth_date") else None,
        has_driver_license=True if cnh else None,
        vehicle_model=str(model).strip() if model else None,
        vehicle_year=year,
        vehicle_id=state.primary_vehicle_id,
        notes=None,
    )


def build_commercial_snapshot(
    state: ConversationCanonicalState,
    *,
    first_inbound: str | None = None,
    qualify: bool = False,
    already_qualified: bool = False,
) -> CommercialSnapshot:
    composed = compose_vendor_summary(state)
    summary = composed.text
    name = (state.customer.name or state.facts.get("name") or "").strip() or None
    if name and is_placeholder_display_name(name):
        name = None
    lead_type = INTENT_TO_LEAD_TYPE.get(state.intent, "CONTACT")
    temperature = state.temperature.value if state.temperature else None
    ids = [str(v).strip() for v in (state.last_shown_vehicle_ids or []) if str(v).strip()]
    primary = (state.primary_vehicle_id or "").strip() or None
    city = str(state.facts.get("birth_city") or state.facts.get("city") or "").strip() or None
    uf = str(state.facts.get("birth_state") or state.facts.get("state") or "").strip() or None
    status = "QUALIFIED" if qualify or already_qualified else "NEW"
    notify = bool(qualify and not already_qualified)
    revision = int(getattr(state, "crm_revision", 0) or 0)
    return CommercialSnapshot(
        lead_type=lead_type,
        status=status,
        julia_summary=summary,
        original_message=original_message_from(first_inbound, summary),
        name=name,
        temperature=temperature,
        primary_vehicle_id=primary,
        interest_ids=ids,
        financing=financing_snapshot(state),
        sell=state.intent in (
            BusinessIntent.SALE,
            BusinessIntent.CONSIGNMENT,
            BusinessIntent.TRADE,
        ),
        visit=_visit_snapshot(state),
        documents=_document_snapshots(state),
        metadata={"intent": state.intent.value, "facts": dict(state.facts or {})},
        revision=revision,
        notify_qualified=notify,
        city=city,
        state=uf,
    )
