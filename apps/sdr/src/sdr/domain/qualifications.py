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
    has_fin = facts.get("trade_has_financing")
    if has_fin is False:
        # Quitado — no further detail needed.
        return True
    if has_fin is True:
        # Financiado — need installment value + remaining count.
        return _has(facts, "trade_installment_value") and _has(facts, "trade_installments_remaining")
    # trade_has_financing not yet answered — not complete.
    return False


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
        # Model + name. À vista is implicit (no financing roteiro needed).
        return _desired_vehicle(facts) and _has_name(state)

    if intent == BusinessIntent.PURCHASE_FINANCING:
        # Vehicle + name + installment preference + documents asked.
        return (
            _desired_vehicle(facts)
            and _has_name(state)
            and _has(facts, "desired_installment")
            and state.documents_asked
        )

    if intent == BusinessIntent.TRADE:
        # Desired vehicle + own vehicle identity + colour + km + financing
        # situation + debts + price expectation + name.
        base = _desired_vehicle(facts) and _own_vehicle_identity(facts)
        color = _has(facts, "trade_color")
        km = _has(facts, "mileage", "km")
        financing_answered = _has(facts, "trade_has_financing")
        financing_detail = _trade_financing_detail(facts)
        debts_answered = _has(facts, "trade_has_debts")
        price_exp = _has(facts, "trade_price_expectation")
        name = _has_name(state)
        return bool(base and color and km and financing_answered and financing_detail and debts_answered and price_exp and name)

    if intent == BusinessIntent.SALE:
        # Own vehicle identity + colour + km + financing + debts + price + name.
        base = _own_vehicle_identity(facts)
        color = _has(facts, "trade_color")
        km = _has(facts, "mileage", "km")
        financing_answered = _has(facts, "trade_has_financing")
        financing_detail = _trade_financing_detail(facts)
        debts_answered = _has(facts, "trade_has_debts")
        price_exp = _has(facts, "trade_price_expectation", "asking_price", "desired_price")
        name = _has_name(state)
        return bool(base and color and km and financing_answered and financing_detail and debts_answered and price_exp and name)

    if intent == BusinessIntent.CONSIGNMENT:
        # Same as SALE + explicit consignment terms.
        base = _own_vehicle_identity(facts)
        color = _has(facts, "trade_color")
        km = _has(facts, "mileage", "km")
        financing_answered = _has(facts, "trade_has_financing")
        financing_detail = _trade_financing_detail(facts)
        debts_answered = _has(facts, "trade_has_debts")
        price_exp = _has(facts, "trade_price_expectation", "asking_price", "desired_price")
        terms = _has(facts, "leave_at_store", "consign_ok")
        name = _has_name(state)
        return bool(base and color and km and financing_answered and financing_detail and debts_answered and price_exp and terms and name)

    if intent == BusinessIntent.REFINANCING:
        # Vehicle + amount needed + name. No financing detail required (bank does it).
        identity = _own_vehicle_identity(facts) or _has(facts, "vehicle_model", "model")
        amount = _has(facts, "amount_needed", "raise_amount", "valor_levantar")
        return bool(identity and amount and _has_name(state))

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
# Fields marked # COND are only asked when a prerequisite is True.
ASK_FIELD_PRIORITY: dict[BusinessIntent, list[str]] = {
    BusinessIntent.PURCHASE: [
        "desired_model",
        "deal_type",   # "seria compra ou troca?" — helps qualify the lead type
        "name",
    ],
    BusinessIntent.PURCHASE_FINANCING: [
        "desired_model",
        "down_payment",           # copy suave: ideia de negócio / entrada
        "desired_installment",
        "documents",              # ask docs before name (financing flow)
        "name",
    ],
    BusinessIntent.TRADE: [
        "desired_model",
        "deal_type",
        "trade_model",
        "trade_year",
        "trade_color",            # NEW
        "mileage",
        "trade_has_financing",    # NEW
        "trade_installment_value",       # NEW — asked only when trade_has_financing=True
        "trade_installments_remaining",  # NEW — asked only when trade_has_financing=True
        "trade_has_debts",        # NEW
        "trade_price_expectation",       # NEW
        "name",
        "trade_renavam",          # nice-to-have — after handoff-blocking fields
    ],
    BusinessIntent.SALE: [
        "trade_model",            # sell_model aliases to trade_model
        "trade_year",
        "trade_color",
        "mileage",
        "trade_has_financing",
        "trade_installment_value",
        "trade_installments_remaining",
        "trade_has_debts",
        "trade_price_expectation",
        "name",
        "trade_renavam",
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
        "trade_renavam",
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
        "trade_model": ("trade_model", "sell_model", "vehicle_model", "model", "brand"),
        "trade_year": ("trade_year", "sell_year", "vehicle_year", "year", "year_model"),
        "trade_color": ("trade_color",),
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
        "trade_has_financing": ("trade_has_financing",),
        "trade_installment_value": ("trade_installment_value",),
        "trade_installments_remaining": ("trade_installments_remaining",),
        "trade_has_debts": ("trade_has_debts",),
        "trade_debt_type": ("trade_debt_type",),
        "trade_price_expectation": ("trade_price_expectation",),
        "trade_in_owner_is_client": ("trade_in_owner_is_client",),
        "trade_renavam": ("trade_renavam",),
        "name": ("name",),
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
        # Conditional: financing detail only when trade_has_financing=True
        if field in ("trade_installment_value", "trade_installments_remaining"):
            has_fin = facts.get("trade_has_financing")
            if has_fin is not True:
                # Financing not confirmed yet — skip these sub-fields.
                continue
        # name: skip if already known from customer profile
        if field == "name":
            if _has_name(state):
                continue
            return "name"
        # trade_renavam: never block handoff, but ask after other fields done
        if field == "trade_renavam":
            if _has(facts, "trade_renavam"):
                continue
            # Only ask RENAVAM after the blocking fields are answered.
            # Check if handoff-blocking fields for TRADE/SALE are already present.
            if is_seller_actionable(state):
                return "trade_renavam"
            # Not yet actionable — skip RENAVAM for now.
            continue
        keys = aliases.get(field, (field,))
        if not _has(facts, *keys):
            return field
    return None
