"""Tests for canonical facts schema and monetary normalization."""

from __future__ import annotations

from sdr.domain.facts_schema import (
    is_pure_greeting,
    normalize_facts,
    normalize_money_value,
    resolve_fact_key,
)
from sdr.understanding.extractor import gate_handoff_signals, has_immediate_closing_evidence
from sdr.domain.types import HandoffSignals


def test_pure_greeting_exact_match() -> None:
    assert is_pure_greeting("Olá") is True
    assert is_pure_greeting("Oi!") is True
    assert is_pure_greeting("Bom dia") is True
    assert is_pure_greeting("  boa tarde.  ") is True


def test_greeting_prefix_with_commercial_is_not_pure() -> None:
    assert is_pure_greeting("Oi, gostaria de saber se vocês têm um veículo disponível") is False
    assert is_pure_greeting("Olá, quero um carro") is False
    assert is_pure_greeting("Bom dia, tem estoque?") is False


def test_unknown_keys_rejected() -> None:
    facts, rejected = normalize_facts(
        {"budget_max": "15 mil", "foobar": "x", "usage": "urbano"}
    )
    assert "foobar" in rejected
    assert "budget" in facts
    assert facts["budget"] == 15000
    assert facts["use_type"] == "urbano"
    assert "budget_max" not in facts
    assert "usage" not in facts


def test_money_normalization_variants() -> None:
    assert normalize_money_value("15 mil") == 15000
    assert normalize_money_value("R$ 15.000") == 15000
    assert normalize_money_value("15000") == 15000
    assert normalize_money_value("15.000") == 15000
    assert normalize_money_value(15000) == 15000
    assert normalize_money_value("até 2000") == 2000


def test_desired_installment_alias() -> None:
    facts, rejected = normalize_facts({"parcela": "2000"})
    assert facts.get("desired_installment") == 2000
    assert not any("malformed" in r for r in rejected)


def test_malformed_money_rejected_not_poison() -> None:
    facts, rejected = normalize_facts({"budget": "barato"})
    assert "budget" not in facts
    assert any("malformed_money" in r for r in rejected)


def test_vehicle_type_free_text_becomes_desired_vehicle_text() -> None:
    facts, rejected = normalize_facts({"vehicle_type": "scooter elétrico"})
    assert facts.get("desired_vehicle_text") == "scooter elétrico"
    assert "vehicle_type" not in facts


def test_vehicle_type_propulsion_token_kept() -> None:
    facts, _ = normalize_facts({"vehicle_type": "eletrico"})
    assert facts.get("vehicle_type") == "eletrico"


def test_alias_resolution() -> None:
    assert resolve_fact_key("budget_max") == "budget"
    assert resolve_fact_key("usage") == "use_type"
    assert resolve_fact_key("desired_vehicle_text") == "desired_vehicle_text"
    assert resolve_fact_key("desired_engine_displacement_liters") == (
        "desired_engine_displacement_liters"
    )
    assert resolve_fact_key("motorizacao") == "desired_engine_displacement_liters"


def test_engine_fact_normalized() -> None:
    facts, _ = normalize_facts(
        {"desired_engine_displacement_liters": "2.0", "desired_model": "Corolla"},
        source_text="quero um Corolla 2.0",
    )
    assert facts["desired_engine_displacement_liters"] == 2.0


def test_high_purchase_gated_without_closing_evidence() -> None:
    gated = gate_handoff_signals(
        "É pra uso urbano mesmo, até uns 15 mil",
        HandoffSignals(high_purchase_intent=True),
    )
    assert gated.high_purchase_intent is None


def test_high_purchase_kept_with_closing_evidence() -> None:
    text = "Quero fechar agora, compro hoje"
    assert has_immediate_closing_evidence(text) is True
    gated = gate_handoff_signals(text, HandoffSignals(high_purchase_intent=True))
    assert gated.high_purchase_intent is True


def test_availability_request_not_closing_evidence() -> None:
    assert has_immediate_closing_evidence("Vocês têm algum scooter elétrico?") is False
    assert has_immediate_closing_evidence("Quero ver opções até 50 mil") is False
