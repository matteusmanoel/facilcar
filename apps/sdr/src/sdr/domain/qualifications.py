"""Triage sufficiency — actionable for next commercial step (not full form)."""

from __future__ import annotations

from typing import Any

from sdr.domain.debts import debts_are_resolved
from sdr.domain.types import (
    Actionability,
    BusinessIntent,
    ConversationCanonicalState,
)
from sdr.domain.vehicle_roles import (
    canonicalize_vehicle_roles,
    customer_has,
    customer_identity,
    desired_identity,
    get_customer_vehicle,
)


def _has(facts: dict[str, Any], *keys: str) -> bool:
    for key in keys:
        value = facts.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, dict) and not value:
            continue
        return True
    return False


def _desired_vehicle(facts: dict[str, Any]) -> bool:
    if desired_identity(facts):
        return True
    return _has(
        facts,
        "desired_model",
        "desired_vehicle_text",
        "vehicle_interest",
        "category",
        "brand_model",
    )


def _own_vehicle_identity(facts: dict[str, Any]) -> bool:
    if customer_identity(facts):
        return True
    has_model = _has(facts, "trade_model", "sell_model", "vehicle_model")
    has_year = _has(facts, "trade_year", "sell_year", "vehicle_year", "year", "year_model")
    return has_model and has_year


def _has_name(state: ConversationCanonicalState) -> bool:
    """True when customer name is known from facts or WhatsApp profile."""
    from sdr.domain.vendor_summary import is_placeholder_display_name

    if _has(state.facts, "name"):
        return True
    if state.customer.name and not is_placeholder_display_name(state.customer.name):
        return True
    return False


def _trade_financing_detail(facts: dict[str, Any]) -> bool:
    """Trade financing detail is satisfied when: no financing, OR details provided."""
    cv = get_customer_vehicle(facts)
    if cv.get("financing_status") == "paid_off":
        return True
    if cv.get("financing_status") == "financed":
        return customer_has(facts, "installment_value") and customer_has(
            facts, "installments_remaining"
        )
    has_fin = facts.get("trade_has_financing")
    if has_fin is False:
        return True
    if has_fin is True:
        return _has(facts, "trade_installment_value") and _has(facts, "trade_installments_remaining")
    return False


def _documents_collected(state: ConversationCanonicalState) -> bool:
    if state.document_received:
        return True
    if state.facts.get("documents_received") is True:
        return True
    return False


def _documents_step_handled(state: ConversationCanonicalState) -> bool:
    """True when the documents step was asked, deferred, or actually received."""
    if _documents_collected(state):
        return True
    deferred = set(state.deferred_fields or [])
    if deferred & {"documents", "cnh", "proof_of_residence", "proof_of_income"}:
        return True
    if state.facts.get("documents_deferred") is True:
        return True
    return bool(state.documents_asked)


def _debts_answered(facts: dict[str, Any]) -> bool:
    cv = get_customer_vehicle(facts)
    status = cv.get("debt_status")
    checks = cv.get("debt_checks") if isinstance(cv.get("debt_checks"), dict) else None
    if debts_are_resolved(checks, status if isinstance(status, str) else None):
        return True
    if status in {"partial", "unknown"}:
        return False
    has_flag = facts.get("trade_has_debts")
    return has_flag is True or has_flag is False


def is_seller_actionable(state: ConversationCanonicalState) -> bool:
    """Return True when the qualification profile is complete for this intent.

    Distinct from is_handoff_ready: a vendor can take an incomplete lead.
    """
    facts = state.facts
    intent = state.intent

    if intent in (BusinessIntent.UNKNOWN, BusinessIntent.SMALLTALK):
        return False

    if intent == BusinessIntent.PURCHASE:
        return _desired_vehicle(facts) and _has_name(state)

    if intent == BusinessIntent.PURCHASE_FINANCING:
        return (
            _desired_vehicle(facts)
            and _has_name(state)
            and _has(facts, "desired_installment")
            and _documents_step_handled(state)
        )

    if intent == BusinessIntent.TRADE:
        base = _desired_vehicle(facts) and _own_vehicle_identity(facts)
        color = customer_has(facts, "color") or _has(facts, "trade_color")
        km = customer_has(facts, "mileage") or _has(facts, "mileage", "km")
        financing_answered = (
            get_customer_vehicle(facts).get("financing_status") is not None
            or _has(facts, "trade_has_financing")
        )
        financing_detail = _trade_financing_detail(facts)
        debts_answered = _debts_answered(facts)
        price_exp = customer_has(facts, "price_expectation") or _has(facts, "trade_price_expectation")
        name = _has_name(state)
        return bool(
            base and color and km and financing_answered and financing_detail
            and debts_answered and price_exp and name
        )

    if intent == BusinessIntent.SALE:
        base = _own_vehicle_identity(facts)
        color = customer_has(facts, "color") or _has(facts, "trade_color")
        km = customer_has(facts, "mileage") or _has(facts, "mileage", "km")
        financing_answered = (
            get_customer_vehicle(facts).get("financing_status") is not None
            or _has(facts, "trade_has_financing")
        )
        financing_detail = _trade_financing_detail(facts)
        debts_answered = _debts_answered(facts)
        price_exp = (
            customer_has(facts, "price_expectation")
            or _has(facts, "trade_price_expectation", "asking_price", "desired_price")
        )
        name = _has_name(state)
        return bool(
            base and color and km and financing_answered and financing_detail
            and debts_answered and price_exp and name
        )

    if intent == BusinessIntent.CONSIGNMENT:
        base = _own_vehicle_identity(facts)
        color = customer_has(facts, "color") or _has(facts, "trade_color")
        km = customer_has(facts, "mileage") or _has(facts, "mileage", "km")
        financing_answered = (
            get_customer_vehicle(facts).get("financing_status") is not None
            or _has(facts, "trade_has_financing")
        )
        financing_detail = _trade_financing_detail(facts)
        debts_answered = _debts_answered(facts)
        price_exp = (
            customer_has(facts, "price_expectation")
            or _has(facts, "trade_price_expectation", "asking_price", "desired_price")
        )
        terms = _has(facts, "leave_at_store", "consign_ok")
        name = _has_name(state)
        return bool(
            base and color and km and financing_answered and financing_detail
            and debts_answered and price_exp and terms and name
        )

    if intent == BusinessIntent.REFINANCING:
        identity = _own_vehicle_identity(facts) or _has(facts, "vehicle_model")
        amount = _has(facts, "amount_needed", "raise_amount", "valor_levantar")
        return bool(identity and amount and _has_name(state))

    return False


def is_handoff_ready(state: ConversationCanonicalState) -> bool:
    """Minimum commercially useful handoff — vendor can start without a full form."""
    facts = state.facts
    intent = state.intent

    sig = state.signals
    if any(
        [
            sig.explicit_handoff is True,
            sig.explicit_offer is True,
            sig.high_purchase_intent is True,
            sig.visit_intent is True,
        ]
    ):
        return True

    if intent in (BusinessIntent.UNKNOWN, BusinessIntent.SMALLTALK):
        return False

    if intent == BusinessIntent.PURCHASE:
        return _desired_vehicle(facts) and _has_name(state)

    if intent == BusinessIntent.PURCHASE_FINANCING:
        return _desired_vehicle(facts) and _has_name(state)

    if intent == BusinessIntent.TRADE:
        return _desired_vehicle(facts) and _own_vehicle_identity(facts) and _has_name(state)

    if intent == BusinessIntent.SALE:
        return _own_vehicle_identity(facts) and _has_name(state)

    if intent == BusinessIntent.CONSIGNMENT:
        return _own_vehicle_identity(facts) and _has_name(state)

    if intent == BusinessIntent.REFINANCING:
        identity = _own_vehicle_identity(facts) or _has(facts, "vehicle_model")
        amount = _has(facts, "amount_needed", "raise_amount", "valor_levantar")
        return bool(identity and amount and _has_name(state))

    return False


def collected_fields(state: ConversationCanonicalState) -> list[str]:
    """Applicable fields that already have a value and were not deferred."""
    found: list[str] = []
    deferred = set(state.deferred_fields or [])
    for field in ASK_FIELD_PRIORITY.get(state.intent, []):
        if field in INAPPLICABLE_FIELDS.get(state.intent, frozenset()):
            continue
        if field in deferred:
            continue
        if field == "documents" and deferred & {"documents", "cnh", "proof_of_residence", "proof_of_income"}:
            continue
        if _field_is_filled(state, field):
            found.append(field)
    return found


def missing_fields(state: ConversationCanonicalState) -> list[str]:
    """Applicable fields still empty and not deferred."""
    missing: list[str] = []
    deferred = set(state.deferred_fields or [])
    for field in ASK_FIELD_PRIORITY.get(state.intent, []):
        if field in INAPPLICABLE_FIELDS.get(state.intent, frozenset()):
            continue
        if field in deferred:
            continue
        if field == "documents" and deferred & {"documents", "cnh", "proof_of_residence", "proof_of_income"}:
            continue
        if field == "intent":
            continue
        if not _field_is_filled(state, field):
            if field in ("trade_installment_value", "trade_installments_remaining"):
                has_fin = state.facts.get("trade_has_financing")
                cv = get_customer_vehicle(state.facts)
                if has_fin is not True and cv.get("financing_status") != "financed":
                    continue
            missing.append(field)
    return missing


def refresh_actionability(state: ConversationCanonicalState) -> ConversationCanonicalState:
    """Update actionability + completeness projection from canonical state.

    HANDOFF_NOW: explicit customer signal (vendor / offer / visit / close).
    ACTIONABLE: handoff_ready — vendor can take over even if the form is incomplete.
    INSUFFICIENT: still collecting the minimum for this intent.
    """
    state.facts = canonicalize_vehicle_roles(state.facts, state.intent)
    if state.facts.get("documents_deferred") is True and "documents" not in (
        state.deferred_fields or []
    ) and not (set(state.deferred_fields or []) & {"cnh", "proof_of_residence", "proof_of_income"}):
        state.deferred_fields = list(state.deferred_fields) + ["cnh", "proof_of_residence", "proof_of_income"]
        state.documents_asked = True

    state.missing_fields = missing_fields(state)
    state.collected_fields = collected_fields(state)
    state.handoff_ready = is_handoff_ready(state)
    state.profile_complete = (
        is_seller_actionable(state)
        and not state.missing_fields
        and not state.deferred_fields
        and _debts_answered(state.facts)
        if state.intent in (
            BusinessIntent.TRADE,
            BusinessIntent.SALE,
            BusinessIntent.CONSIGNMENT,
        )
        else (
            is_seller_actionable(state)
            and not state.missing_fields
            and not state.deferred_fields
        )
    )
    # Partial debts must never count as a complete profile.
    cv = get_customer_vehicle(state.facts)
    if cv.get("debt_status") == "partial":
        state.profile_complete = False

    signals = state.signals
    if any(
        (
            signals.explicit_handoff is True,
            signals.explicit_offer is True,
            signals.high_purchase_intent is True,
            signals.visit_intent is True,
        )
    ):
        state.business.actionability = Actionability.HANDOFF_NOW
    elif state.handoff_ready:
        state.business.actionability = Actionability.ACTIONABLE
    else:
        state.business.actionability = Actionability.INSUFFICIENT
    return state


INAPPLICABLE_FIELDS: dict[BusinessIntent, frozenset[str]] = {
    BusinessIntent.PURCHASE: frozenset({
        "trade_model", "trade_year", "trade_color",
        "trade_has_financing", "trade_installment_value",
        "trade_installments_remaining", "trade_has_debts",
        "trade_price_expectation", "trade_renavam",
        "leave_at_store", "amount_needed",
    }),
    BusinessIntent.PURCHASE_FINANCING: frozenset({
        "trade_model", "trade_year", "trade_color",
        "trade_has_financing", "trade_installment_value",
        "trade_installments_remaining", "trade_has_debts",
        "trade_price_expectation", "trade_renavam",
        "leave_at_store", "amount_needed",
    }),
    BusinessIntent.TRADE: frozenset({
        "leave_at_store", "amount_needed",
    }),
    BusinessIntent.SALE: frozenset({
        "desired_model", "desired_vehicle_text", "desired_vehicle",
        "vehicle_interest", "down_payment", "desired_installment",
        "leave_at_store", "amount_needed", "payment_method",
    }),
    BusinessIntent.CONSIGNMENT: frozenset({
        "desired_model", "desired_vehicle_text", "desired_vehicle",
        "vehicle_interest", "down_payment", "desired_installment",
        "amount_needed", "payment_method",
    }),
    BusinessIntent.REFINANCING: frozenset({
        "desired_model", "desired_vehicle_text", "desired_vehicle",
        "vehicle_interest", "down_payment", "desired_installment",
        "leave_at_store", "payment_method",
    }),
}


ASK_FIELD_PRIORITY: dict[BusinessIntent, list[str]] = {
    BusinessIntent.PURCHASE: [
        "desired_model",
        "payment_method",
        "name",
    ],
    BusinessIntent.PURCHASE_FINANCING: [
        "desired_model",
        "down_payment",
        "desired_installment",
        "documents",
        "name",
    ],
    BusinessIntent.TRADE: [
        "desired_model",
        "trade_model",
        "trade_year",
        "trade_color",
        "mileage",
        "trade_has_financing",
        "trade_installment_value",
        "trade_installments_remaining",
        "trade_has_debts",
        "trade_price_expectation",
        "payment_method",
        "name",
    ],
    BusinessIntent.SALE: [
        "trade_model",
        "trade_year",
        "trade_color",
        "mileage",
        "trade_has_financing",
        "trade_installment_value",
        "trade_installments_remaining",
        "trade_has_debts",
        "trade_price_expectation",
        "name",
    ],
    BusinessIntent.CONSIGNMENT: [
        "trade_model",
        "trade_year",
        "trade_color",
        "mileage",
        "trade_has_financing",
        "trade_installment_value",
        "trade_installments_remaining",
        "trade_has_debts",
        "trade_price_expectation",
        "leave_at_store",
        "name",
    ],
    BusinessIntent.REFINANCING: [
        "trade_model",
        "trade_year",
        "amount_needed",
        "name",
    ],
    BusinessIntent.SMALLTALK: ["intent"],
    BusinessIntent.UNKNOWN: ["intent"],
}


def _field_is_filled(state: ConversationCanonicalState, field: str) -> bool:
    facts = state.facts
    cv = get_customer_vehicle(facts)

    if field == "desired_model":
        return desired_identity(facts)
    if field == "trade_model":
        return bool(cv.get("model") or _has(facts, "trade_model", "sell_model", "vehicle_model"))
    if field == "trade_year":
        return bool(cv.get("year") or _has(facts, "trade_year", "sell_year", "vehicle_year", "year"))
    if field == "trade_color":
        return bool(cv.get("color") or _has(facts, "trade_color", "color", "sell_color"))
    if field == "mileage":
        return cv.get("mileage") is not None or _has(facts, "mileage", "km")
    if field == "trade_has_financing":
        return cv.get("financing_status") is not None or _has(facts, "trade_has_financing")
    if field == "trade_installment_value":
        return cv.get("installment_value") is not None or _has(facts, "trade_installment_value")
    if field == "trade_installments_remaining":
        return cv.get("installments_remaining") is not None or _has(
            facts, "trade_installments_remaining"
        )
    if field == "trade_has_debts":
        return _debts_answered(facts)
    if field == "trade_price_expectation":
        return cv.get("price_expectation") is not None or _has(
            facts, "trade_price_expectation", "asking_price"
        )
    if field == "trade_renavam":
        return bool(cv.get("renavam") or _has(facts, "trade_renavam"))
    if field == "name":
        return _has_name(state)
    if field == "documents":
        return _documents_collected(state)
    if field == "desired_installment":
        return state.installment_asked or _has(facts, "desired_installment", "parcela")
    if field == "payment_method":
        return _has(facts, "payment_method", "payment_type")
    if field == "leave_at_store":
        return _has(facts, "leave_at_store", "consign_ok")
    if field == "amount_needed":
        return _has(facts, "amount_needed", "raise_amount", "valor_levantar")
    if field == "down_payment":
        return _has(facts, "down_payment", "entrada")
    return _has(facts, field)


def next_ask_field(state: ConversationCanonicalState) -> str | None:
    """Single missing field to ask next, or None if nothing useful."""
    facts = state.facts
    order = ASK_FIELD_PRIORITY.get(state.intent, ["intent"])
    inapplicable = INAPPLICABLE_FIELDS.get(state.intent, frozenset())
    deferred = set(state.deferred_fields or [])

    for field in order:
        if field == "intent":
            if state.intent in (BusinessIntent.UNKNOWN, BusinessIntent.SMALLTALK):
                return "intent"
            continue
        if field in inapplicable or field in deferred:
            continue
        if field == "documents" and deferred & {"documents", "cnh", "proof_of_residence", "proof_of_income"}:
            continue
        if field == "documents" and _documents_step_handled(state):
            continue
        if field == "budget":
            continue
        if field == "deal_type":
            if state.intent not in (BusinessIntent.UNKNOWN, BusinessIntent.SMALLTALK):
                continue
            if _has(facts, "deal_type"):
                continue
            return "deal_type"
        if field in ("trade_installment_value", "trade_installments_remaining"):
            has_fin = facts.get("trade_has_financing")
            cv = get_customer_vehicle(facts)
            if has_fin is not True and cv.get("financing_status") != "financed":
                continue
        if field == "trade_renavam":
            # Optional document identifier — never blocks handoff.
            continue
        if not _field_is_filled(state, field):
            return field
    return None
