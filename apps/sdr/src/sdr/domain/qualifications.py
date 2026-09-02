"""Triage sufficiency — actionable for next commercial step (not full form)."""

from __future__ import annotations

from typing import Any

from sdr.domain.types import (
    Actionability,
    BusinessIntent,
    ConversationCanonicalState,
)


def _has(facts: dict[str, Any], *keys: str) -> bool:
    for key in keys:
        value = facts.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return True
    return False


def _desired_vehicle(facts: dict[str, Any]) -> bool:
    return _has(
        facts,
        "desired_model",
        "desired_vehicle_text",
        "desired_vehicle",
        "vehicle_interest",
        "category",
        "model",
        "brand_model",
        "brand",
    )


def _own_vehicle_identity(facts: dict[str, Any]) -> bool:
    has_model = _has(facts, "trade_model", "sell_model", "vehicle_model", "model", "brand")
    has_year = _has(facts, "trade_year", "sell_year", "vehicle_year", "year", "year_model")
    return has_model and has_year


def is_seller_actionable(state: ConversationCanonicalState) -> bool:
    """Return True when a vendor can continue without restarting triage.

    Triage complete ≠ financing/sell form complete. Only fields needed to
    unlock the next commercial action matter.
    """
    facts = state.facts
    intent = state.intent

    if intent in (BusinessIntent.UNKNOWN, BusinessIntent.SMALLTALK):
        return False

    if intent == BusinessIntent.PURCHASE:
        # Model + commercial mode + cash vs financing. Budget is never required.
        return (
            _desired_vehicle(facts)
            and _has(facts, "deal_type")
            and _has(facts, "payment_method")
        )

    if intent == BusinessIntent.PURCHASE_FINANCING:
        # Vehicle + deal type + down payment (0 = sem entrada). Documents are
        # requested once, then visit — they do not block a commercial handoff.
        has_vehicle = _desired_vehicle(facts)
        has_mode = _has(facts, "deal_type")
        has_down = _has(facts, "down_payment")
        return has_vehicle and has_mode and has_down and state.documents_asked

    if intent == BusinessIntent.TRADE:
        # Desired + trade-in identity (brand/model + year) is enough.
        return _desired_vehicle(facts) and _own_vehicle_identity(facts)

    if intent == BusinessIntent.SALE:
        # Brand/model + year + intent/value or km.
        identity = _own_vehicle_identity(facts)
        commercial = _has(
            facts,
            "asking_price",
            "desired_price",
            "mileage",
            "km",
            "timeline",
            "urgency",
        )
        return identity and commercial

    if intent == BusinessIntent.CONSIGNMENT:
        identity = _own_vehicle_identity(facts)
        terms = _has(facts, "asking_price", "desired_price", "leave_at_store", "consign_ok")
        return identity and terms

    if intent == BusinessIntent.REFINANCING:
        # Vehicle + amount to raise; term is nice-to-have (playbook).
        identity = _own_vehicle_identity(facts) or _has(facts, "vehicle_model", "model")
        amount = _has(facts, "amount_needed", "raise_amount", "valor_levantar")
        return bool(identity and amount)

    return False


def refresh_actionability(state: ConversationCanonicalState) -> ConversationCanonicalState:
    """Update business.actionability from triage rules + handoff-now signals."""
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
    elif is_seller_actionable(state):
        state.business.actionability = Actionability.ACTIONABLE
    else:
        state.business.actionability = Actionability.INSUFFICIENT
    return state


# Preferential ask order per intent (one question at a time).
ASK_FIELD_PRIORITY: dict[BusinessIntent, list[str]] = {
    BusinessIntent.PURCHASE: [
        "desired_model",
        "deal_type",
        "payment_method",
    ],
    BusinessIntent.PURCHASE_FINANCING: [
        "desired_model",
        "deal_type",
        "down_payment",
        "desired_installment",
        "documents",
    ],
    BusinessIntent.TRADE: [
        "desired_model",
        "deal_type",
        "trade_model",
        "trade_year",
        "mileage",
    ],
    BusinessIntent.SALE: [
        "model",
        "year",
        "mileage",
        "asking_price",
        "city",
    ],
    BusinessIntent.CONSIGNMENT: [
        "model",
        "year",
        "mileage",
        "asking_price",
        "leave_at_store",
    ],
    BusinessIntent.REFINANCING: [
        "model",
        "year",
        "amount_needed",
        "vehicle_value",
    ],
    BusinessIntent.SMALLTALK: ["intent"],
    BusinessIntent.UNKNOWN: ["intent"],
}


def next_ask_field(state: ConversationCanonicalState) -> str | None:
    """Single missing field to ask next, or None if nothing useful."""
    facts = state.facts
    order = ASK_FIELD_PRIORITY.get(state.intent, ["intent"])
    aliases: dict[str, tuple[str, ...]] = {
        "desired_model": (
            "desired_model",
            "desired_vehicle_text",
            "desired_vehicle",
            "vehicle_interest",
            "model",
            "category",
            "brand",
        ),
        "deal_type": ("deal_type",),
        "budget": ("budget", "max_price", "price_range", "valor"),
        "trade_model": ("trade_model", "vehicle_model", "model", "brand"),
        "trade_year": ("trade_year", "vehicle_year", "year", "year_model"),
        "model": ("model", "sell_model", "vehicle_model", "brand", "trade_model"),
        "year": ("year", "sell_year", "vehicle_year", "year_model", "trade_year"),
        "mileage": ("mileage", "km"),
        "asking_price": ("asking_price", "desired_price"),
        "amount_needed": ("amount_needed", "raise_amount", "valor_levantar"),
        "down_payment": ("down_payment", "entrada"),
        "desired_installment": ("desired_installment", "parcela"),
        "payment_method": ("payment_method", "payment_type"),
        "timeline": ("timeline", "urgency", "purchase_timeline"),
        "city": ("city", "location"),
        "leave_at_store": ("leave_at_store", "consign_ok"),
        "vehicle_value": ("vehicle_value", "approx_value"),
        "intent": (),
    }
    for field in order:
        if field == "intent":
            if state.intent in (BusinessIntent.UNKNOWN, BusinessIntent.SMALLTALK):
                return "intent"
            continue
        if field == "budget":
            # Budget is sensitive — extract if volunteered, never solicit.
            continue
        if field == "documents":
            if state.documents_asked:
                continue
            return "documents"
        if field == "desired_installment":
            if state.installment_asked:
                continue
            return "desired_installment"
        keys = aliases.get(field, (field,))
        if not _has(facts, *keys):
            return field
    return None
