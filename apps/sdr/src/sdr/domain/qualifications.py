"""Triage sufficiency — actionable for next commercial step (not full form)."""

from __future__ import annotations

from typing import Any

from sdr.domain.budget_status import BUDGET_RESOLVED, BudgetStatus
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


def _budget_or_price(facts: dict[str, Any], budget_status: BudgetStatus) -> bool:
    """Budget question resolved enough for triage / not blocking inventory."""
    if budget_status in (
        BudgetStatus.PROVIDED,
        BudgetStatus.UNDEFINED,
        BudgetStatus.DECLINED,
        BudgetStatus.FLEXIBLE,
    ):
        if budget_status == BudgetStatus.PROVIDED:
            return _has(
                facts,
                "budget",
                "max_price",
                "price_range",
                "valor",
                "faixa_valor",
            )
        # UNDEFINED / DECLINED / FLEXIBLE — resolved without a number.
        return True
    return _has(
        facts,
        "budget",
        "max_price",
        "price_range",
        "valor",
        "faixa_valor",
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
    budget_status = state.budget_status

    if intent in (BusinessIntent.UNKNOWN, BusinessIntent.SMALLTALK):
        return False

    if intent == BusinessIntent.PURCHASE:
        # Model/category + budget band (or resolved non-numeric status) is enough.
        return _desired_vehicle(facts) and _budget_or_price(facts, budget_status)

    if intent == BusinessIntent.PURCHASE_FINANCING:
        # Vehicle + value; down payment helps but income/CPF are not blockers.
        has_vehicle = _desired_vehicle(facts)
        has_value = _budget_or_price(facts, budget_status) or _has(
            facts, "down_payment", "entrada"
        )
        return has_vehicle and has_value

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
        "budget",
        "payment_method",
        "timeline",
    ],
    BusinessIntent.PURCHASE_FINANCING: [
        "desired_model",
        "budget",
        "down_payment",
        "timeline",
    ],
    BusinessIntent.TRADE: [
        "desired_model",
        "budget",
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
        "budget": ("budget", "max_price", "price_range", "valor"),
        "trade_model": ("trade_model", "vehicle_model", "model", "brand"),
        "trade_year": ("trade_year", "vehicle_year", "year", "year_model"),
        "model": ("model", "sell_model", "vehicle_model", "brand", "trade_model"),
        "year": ("year", "sell_year", "vehicle_year", "year_model", "trade_year"),
        "mileage": ("mileage", "km"),
        "asking_price": ("asking_price", "desired_price"),
        "amount_needed": ("amount_needed", "raise_amount", "valor_levantar"),
        "down_payment": ("down_payment", "entrada"),
        "payment_method": ("payment_method", "financing"),
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
            # Do not re-ask when budget status is already resolved.
            if state.budget_status in BUDGET_RESOLVED:
                continue
            if _has(facts, *aliases["budget"]):
                continue
            return "budget"
        keys = aliases.get(field, (field,))
        if not _has(facts, *keys):
            return field
    return None
