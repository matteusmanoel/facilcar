"""Canonical desired_vehicle vs customer_vehicle roles."""

from __future__ import annotations

from sdr.domain.qualifications import next_ask_field, refresh_actionability
from sdr.domain.types import BusinessIntent, ConversationCanonicalState, CustomerState
from sdr.domain.vehicle_roles import (
    canonicalize_vehicle_roles,
    get_customer_vehicle,
    get_desired_vehicle,
)


def _state(intent: BusinessIntent, facts: dict) -> ConversationCanonicalState:
    return ConversationCanonicalState(
        thread_id="t",
        customer=CustomerState(phone="5541999999999"),
        intent=intent,
        facts=facts,
    )


def test_consignment_packed_civic_fills_customer_vehicle_not_desired() -> None:
    facts = canonicalize_vehicle_roles(
        {"vehicle_model": "Civic 2021 preto 30000 km"},
        BusinessIntent.CONSIGNMENT,
    )
    cv = get_customer_vehicle(facts)
    dv = get_desired_vehicle(facts)
    assert cv.get("year") == "2021"
    assert cv.get("color") == "preto"
    assert cv.get("mileage") == 30000
    assert not dv.get("model")
    state = _state(BusinessIntent.CONSIGNMENT, facts)
    refresh_actionability(state)
    assert next_ask_field(state) != "trade_color"


def test_sale_packed_corolla_fills_customer_vehicle() -> None:
    facts = canonicalize_vehicle_roles(
        {"sell_model": "Corolla", "vehicle_year": "2020", "color": "prata", "mileage": 50000},
        BusinessIntent.SALE,
    )
    cv = get_customer_vehicle(facts)
    assert cv.get("model", "").lower() == "corolla"
    assert str(cv.get("year")) == "2020"
    assert cv.get("color") == "prata"
    assert cv.get("mileage") == 50000
    assert not get_desired_vehicle(facts).get("model")
    state = _state(BusinessIntent.SALE, facts)
    refresh_actionability(state)
    assert next_ask_field(state) != "trade_color"


def test_trade_keeps_both_vehicles_without_crossover() -> None:
    facts = canonicalize_vehicle_roles(
        {"desired_model": "HB20", "trade_model": "Ford Ka", "trade_year": "2019", "color": "prata"},
        BusinessIntent.TRADE,
    )
    dv = get_desired_vehicle(facts)
    cv = get_customer_vehicle(facts)
    assert "hb20" in str(dv.get("model")).lower()
    assert "ka" in str(cv.get("model")).lower()
    assert str(cv.get("year")) == "2019"
    assert cv.get("color") == "prata"
    assert dv.get("year") != "2019" or dv.get("model") != cv.get("model")
    assert cv.get("model") != dv.get("model")


def test_purchase_does_not_copy_customer_vehicle_from_color() -> None:
    facts = canonicalize_vehicle_roles(
        {"desired_model": "Onix Plus", "color": "branco", "year": "2022"},
        BusinessIntent.PURCHASE,
    )
    dv = get_desired_vehicle(facts)
    cv = get_customer_vehicle(facts)
    assert "onix" in str(dv.get("model")).lower()
    assert not cv.get("model")
    assert dv.get("color") == "branco"
