"""Tests for field applicability rules per intent.

Verifies the contract:
  - SALE/CONSIGNMENT/REFINANCING never ask for desired vehicle
  - TRADE never asks 'deal_type' when intent is already determined
  - PURCHASE never asks trade-specific fields
  - deal_type is never asked proactively when intent is known
"""

from __future__ import annotations

import pytest

from sdr.domain.qualifications import INAPPLICABLE_FIELDS, next_ask_field
from sdr.domain.types import BusinessIntent, ConversationCanonicalState, CustomerState


def _state(intent: BusinessIntent, facts: dict | None = None) -> ConversationCanonicalState:
    st = ConversationCanonicalState(
        thread_id="test",
        customer=CustomerState(phone="5541999999999"),
        intent=intent,
        facts=facts or {},
    )
    return st


def _collect_all_fields(state: ConversationCanonicalState, max_steps: int = 30) -> list[str]:
    """Walk next_ask_field exhaustively, returning all fields in priority order."""
    fields: list[str] = []
    for _ in range(max_steps):
        f = next_ask_field(state)
        if f is None:
            break
        fields.append(f)
        state.facts[f] = "test_value"
    return fields


# ---------------------------------------------------------------------------
# SALE
# ---------------------------------------------------------------------------

def test_sale_never_asks_desired_model():
    """SALE intent must never ask for desired_model."""
    state = _state(BusinessIntent.SALE)
    fields = _collect_all_fields(state)
    assert "desired_model" not in fields, f"SALE asked desired_model: {fields}"
    assert "desired_vehicle_text" not in fields, f"SALE asked desired_vehicle_text: {fields}"
    assert "vehicle_interest" not in fields, f"SALE asked vehicle_interest: {fields}"


def test_sale_never_asks_deal_type():
    """SALE intent must not ask deal_type."""
    state = _state(BusinessIntent.SALE)
    fields = _collect_all_fields(state)
    assert "deal_type" not in fields, f"SALE asked deal_type: {fields}"


def test_sale_asks_trade_model_first():
    """SALE intent should ask for trade_model (the vehicle to sell) first."""
    state = _state(BusinessIntent.SALE)
    first = next_ask_field(state)
    assert first == "trade_model", f"SALE first field should be trade_model, got {first!r}"


# ---------------------------------------------------------------------------
# CONSIGNMENT
# ---------------------------------------------------------------------------

def test_consignment_never_asks_desired_model():
    """CONSIGNMENT intent must never ask for desired_model."""
    state = _state(BusinessIntent.CONSIGNMENT)
    fields = _collect_all_fields(state)
    assert "desired_model" not in fields, f"CONSIGNMENT asked desired_model: {fields}"
    assert "desired_vehicle_text" not in fields
    assert "vehicle_interest" not in fields


def test_consignment_never_asks_deal_type():
    """CONSIGNMENT intent must not ask deal_type."""
    state = _state(BusinessIntent.CONSIGNMENT)
    fields = _collect_all_fields(state)
    assert "deal_type" not in fields, f"CONSIGNMENT asked deal_type: {fields}"


# ---------------------------------------------------------------------------
# REFINANCING
# ---------------------------------------------------------------------------

def test_refinancing_never_asks_desired_model():
    """REFINANCING intent must never ask for desired_model."""
    state = _state(BusinessIntent.REFINANCING)
    fields = _collect_all_fields(state)
    assert "desired_model" not in fields, f"REFINANCING asked desired_model: {fields}"


def test_refinancing_never_asks_deal_type():
    """REFINANCING intent must not ask deal_type."""
    state = _state(BusinessIntent.REFINANCING)
    fields = _collect_all_fields(state)
    assert "deal_type" not in fields, f"REFINANCING asked deal_type: {fields}"


def test_refinancing_asks_amount_needed():
    """REFINANCING must ask amount_needed at some point."""
    state = _state(BusinessIntent.REFINANCING, {"trade_model": "Compass", "trade_year": "2022"})
    fields = _collect_all_fields(state)
    assert "amount_needed" in fields, f"REFINANCING should ask amount_needed: {fields}"


# ---------------------------------------------------------------------------
# TRADE
# ---------------------------------------------------------------------------

def test_trade_does_not_ask_deal_type_when_intent_known():
    """TRADE intent must not ask deal_type — intent already declares the deal."""
    state = _state(BusinessIntent.TRADE, {"desired_model": "HB20", "trade_model": "Ford Ka"})
    fields = _collect_all_fields(state)
    assert "deal_type" not in fields, f"TRADE asked deal_type: {fields}"


def test_trade_never_asks_leave_at_store():
    """TRADE intent must not ask leave_at_store (consignment-only field)."""
    state = _state(BusinessIntent.TRADE)
    fields = _collect_all_fields(state)
    assert "leave_at_store" not in fields, f"TRADE asked leave_at_store: {fields}"


def test_trade_never_asks_amount_needed():
    """TRADE intent must not ask amount_needed (refinancing-only field)."""
    state = _state(BusinessIntent.TRADE)
    fields = _collect_all_fields(state)
    assert "amount_needed" not in fields, f"TRADE asked amount_needed: {fields}"


# ---------------------------------------------------------------------------
# PURCHASE
# ---------------------------------------------------------------------------

def test_purchase_does_not_ask_trade_fields():
    """PURCHASE intent must not ask trade-specific fields."""
    state = _state(BusinessIntent.PURCHASE, {"desired_model": "Onix"})
    inapplicable = INAPPLICABLE_FIELDS.get(BusinessIntent.PURCHASE, frozenset())
    fields = _collect_all_fields(state)
    for f in fields:
        assert f not in inapplicable, f"PURCHASE asked inapplicable field {f!r}: {fields}"


def test_purchase_does_not_ask_deal_type():
    """PURCHASE intent must not ask deal_type proactively — intent is already PURCHASE."""
    state = _state(BusinessIntent.PURCHASE, {"desired_model": "Onix"})
    fields = _collect_all_fields(state)
    assert "deal_type" not in fields, f"PURCHASE asked deal_type: {fields}"


def test_purchase_financing_does_not_ask_trade_fields():
    """PURCHASE_FINANCING must not ask any trade-specific fields."""
    state = _state(BusinessIntent.PURCHASE_FINANCING, {"desired_model": "HB20"})
    inapplicable = INAPPLICABLE_FIELDS.get(BusinessIntent.PURCHASE_FINANCING, frozenset())
    fields = _collect_all_fields(state)
    for f in fields:
        assert f not in inapplicable, (
            f"PURCHASE_FINANCING asked inapplicable field {f!r}: {fields}"
        )


# ---------------------------------------------------------------------------
# UNKNOWN / SMALLTALK — should ask for intent
# ---------------------------------------------------------------------------

def test_unknown_asks_intent():
    """UNKNOWN intent should ask for 'intent'."""
    state = _state(BusinessIntent.UNKNOWN)
    first = next_ask_field(state)
    assert first == "intent", f"UNKNOWN first field should be 'intent', got {first!r}"


def test_smalltalk_asks_intent():
    """SMALLTALK intent should ask for 'intent'."""
    state = _state(BusinessIntent.SMALLTALK)
    first = next_ask_field(state)
    assert first == "intent", f"SMALLTALK first field should be 'intent', got {first!r}"


# ---------------------------------------------------------------------------
# INAPPLICABLE_FIELDS completeness
# ---------------------------------------------------------------------------

def test_inapplicable_fields_defined_for_all_concrete_intents():
    """All concrete intents (not UNKNOWN/SMALLTALK) should have an INAPPLICABLE_FIELDS entry."""
    concrete = [
        BusinessIntent.PURCHASE,
        BusinessIntent.PURCHASE_FINANCING,
        BusinessIntent.TRADE,
        BusinessIntent.SALE,
        BusinessIntent.CONSIGNMENT,
        BusinessIntent.REFINANCING,
    ]
    for intent in concrete:
        # It's acceptable to have an empty frozenset, but the key should exist.
        assert intent in INAPPLICABLE_FIELDS, (
            f"INAPPLICABLE_FIELDS missing entry for intent {intent.value!r}"
        )
