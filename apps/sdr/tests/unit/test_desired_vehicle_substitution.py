"""Desired-vehicle substitution when the customer changes model."""

from __future__ import annotations

from sdr.domain.merge import deterministic_merge
from sdr.domain.types import BusinessIntent, ConversationCanonicalState, CustomerState, TurnFacts
from sdr.domain.vehicle_roles import apply_desired_vehicle_substitution, get_desired_vehicle


def test_corolla_does_not_keep_honda_or_civic_silver() -> None:
    facts = {
        "desired_model": "Civic",
        "desired_vehicle": {"model": "Civic", "brand": "Honda", "color": "Prata"},
        "brand": "Honda",
    }
    out = apply_desired_vehicle_substitution(
        dict(facts),
        facts,
        {"desired_model": "Corolla"},
        inbound_text="Pode ser o Corolla então, à vista.",
    )
    dv = get_desired_vehicle(out)
    assert str(dv.get("model")).lower() == "corolla"
    assert str(dv.get("brand") or "").lower() == "toyota"
    assert str(dv.get("color") or "").lower() != "prata"


def test_corolla_prata_keeps_color_when_said() -> None:
    prev = {"desired_vehicle": {"model": "Civic", "brand": "Honda", "color": "Prata"}}
    out = apply_desired_vehicle_substitution(
        {"desired_vehicle": dict(prev["desired_vehicle"]), "desired_model": "Civic"},
        prev,
        {"desired_model": "Corolla"},
        inbound_text="Pode ser um Corolla prata então.",
    )
    dv = get_desired_vehicle(out)
    assert str(dv.get("model")).lower() == "corolla"
    assert str(dv.get("color") or "").lower() == "prata"
    assert str(dv.get("brand") or "").lower() == "toyota"


def test_merge_replaces_desired_vehicle_identity() -> None:
    prev = ConversationCanonicalState(
        thread_id="t",
        customer=CustomerState(phone="1"),
        intent=BusinessIntent.PURCHASE,
        facts={
            "desired_model": "Civic",
            "desired_vehicle": {"model": "Civic", "brand": "Honda", "color": "Prata"},
            "brand": "Honda",
        },
    )
    incoming = TurnFacts(
        intent=BusinessIntent.PURCHASE,
        facts={"desired_model": "Corolla", "payment_method": "cash"},
    )
    merged = deterministic_merge(prev, incoming, inbound_text="Pode ser o Corolla então, à vista.")
    dv = get_desired_vehicle(merged.facts)
    assert str(dv.get("model")).lower() == "corolla"
    assert str(dv.get("brand") or "").lower() != "honda"
    assert str(dv.get("color") or "").lower() != "prata"
