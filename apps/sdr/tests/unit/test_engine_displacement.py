"""Engine displacement normalization and TurnFacts preservation."""

from __future__ import annotations

import os
from decimal import Decimal

import pytest

from sdr.config import get_settings

from sdr.domain.engine_displacement import (
    extract_engine_displacements_from_text,
    normalize_engine_displacement,
)
from sdr.domain.facts_schema import normalize_facts
from sdr.domain.inventory_search import (
    build_inventory_search_request,
    inventory_search_key,
)
from sdr.domain.merge import deterministic_merge
from sdr.domain.types import (
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
)
from sdr.tools.inventory import ENGINE_UNINFORMED_LABEL, InventoryVehicle
from sdr.understanding.extractor import extract_turn_facts


@pytest.fixture(autouse=True)
def _clear_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    os.environ["OPENAI_API_KEY"] = ""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _state(**kwargs) -> ConversationCanonicalState:
    base = ConversationCanonicalState(
        thread_id="t1",
        customer=CustomerState(phone="5511999999999"),
    )
    for key, value in kwargs.items():
        setattr(base, key, value)
    return base


def test_normalize_accepts_commercial_liters() -> None:
    assert normalize_engine_displacement("1.4") == Decimal("1.4")
    assert normalize_engine_displacement("2.0") == Decimal("2.0")
    assert normalize_engine_displacement(1.8) == Decimal("1.8")


def test_normalize_rejects_compound_and_out_of_range() -> None:
    assert normalize_engine_displacement("1.0 TSI") is None
    assert normalize_engine_displacement("2.0 Turbo") is None
    assert normalize_engine_displacement("1.4 Fire Flex") is None
    assert normalize_engine_displacement("0.5") is None
    assert normalize_engine_displacement("9.0") is None
    assert normalize_engine_displacement(2) is None


def test_ate_80_mil_is_not_displacement() -> None:
    assert extract_engine_displacements_from_text("quero um carro até 80 mil") == []
    facts, _ = normalize_facts(
        {"desired_engine_displacement_liters": "80"},
        source_text="quero um carro até 80 mil",
    )
    assert "desired_engine_displacement_liters" not in facts


def test_taxa_1_8_percent_is_not_displacement() -> None:
    text = "a taxa de 1.8% ao mês"
    assert extract_engine_displacements_from_text(text) == []
    facts, rejected = normalize_facts(
        {"desired_engine_displacement_liters": "1.8"},
        source_text=text,
    )
    assert "desired_engine_displacement_liters" not in facts
    assert any("invalid_engine" in r for r in rejected)


@pytest.mark.asyncio
async def test_corolla_2_0_extracts_engine_and_vehicle_text() -> None:
    facts = await extract_turn_facts("quero um Corolla 2.0", "")
    assert facts.facts.get("desired_model", "").lower() == "corolla"
    assert facts.facts.get("desired_engine_displacement_liters") == 2.0
    assert "2.0" in str(facts.facts.get("desired_vehicle_text", ""))


@pytest.mark.asyncio
async def test_engine_preserved_on_follow_up_turn() -> None:
    first = await extract_turn_facts("quero um Corolla 2.0", "")
    prev = _state(intent=BusinessIntent.PURCHASE, facts=dict(first.facts))
    second = await extract_turn_facts("tem automático?", "")
    merged = deterministic_merge(prev, second)
    assert merged.facts.get("desired_engine_displacement_liters") == 2.0
    assert merged.facts.get("desired_model", "").lower() == "corolla"


@pytest.mark.asyncio
async def test_pode_ser_1_8_tambem_flexibilizes_engine() -> None:
    first = await extract_turn_facts("quero um Corolla 2.0", "")
    prev = _state(intent=BusinessIntent.PURCHASE, facts=dict(first.facts))
    second = await extract_turn_facts("pode ser 1.8 também", "")
    merged = deterministic_merge(prev, second)
    engines = merged.facts.get("desired_engine_displacement_liters")
    assert merged.facts.get("desired_engine_flexible") is True
    as_list = engines if isinstance(engines, list) else [engines]
    assert 2.0 in as_list
    assert 1.8 in as_list
    key_before = inventory_search_key(first.facts)
    key_after = inventory_search_key(merged.facts)
    assert key_before != key_after


def test_engine_is_never_a_triage_question() -> None:
    from sdr.domain.qualifications import next_ask_field

    state = _state(
        intent=BusinessIntent.PURCHASE,
        facts={"desired_model": "Corolla"},
    )
    assert next_ask_field(state) != "desired_engine_displacement_liters"
    assert next_ask_field(state) != "desired_engine_flexible"
    assert next_ask_field(state) != "desired_engine_any"


def test_search_request_carries_canonical_engine_without_reparse() -> None:
    req = build_inventory_search_request(
        {
            "desired_model": "Corolla",
            "desired_engine_displacement_liters": 2.0,
            "desired_vehicle_text": "texto livre sem número",
        }
    )
    assert req.engine_displacement_liters == [Decimal("2.0")]


def test_missing_engine_on_card_is_nao_informado_not_negation() -> None:
    v = InventoryVehicle(
        id="1",
        slug="x",
        title="TOYOTA COROLLA GLI 2.0",
        brand_name="Toyota",
        model="Corolla",
        type="CAR",
        price_cash=None,
        mileage=None,
        color=None,
        year_model=2016,
        year_manufacture=2015,
        version="GLI",
        engine_displacement_liters=None,
    )
    assert v.to_dict()["engineDisplacementLiters"] is None
    assert v.format_field("engine_displacement_liters") == ENGINE_UNINFORMED_LABEL
    assert v.format_field("engine_displacement_liters") == "não informado"
    assert "não é" not in v.format_field("engine_displacement_liters")
    # Title still has 2.0; must not become a confirmed fact.
    assert v.engine_displacement_liters is None


def _engines(facts: dict) -> list[float]:
    raw = facts.get("desired_engine_displacement_liters")
    if raw is None:
        return []
    if isinstance(raw, list):
        return sorted(float(x) for x in raw)
    return [float(raw)]


@pytest.mark.asyncio
async def test_multi_displacement_states_are_distinct() -> None:
    """Exact vs accepted set vs exclusive correction vs unconstrained engine."""
    first = await extract_turn_facts("Quero um Corolla 2.0", "")
    s1 = deterministic_merge(_state(), first)
    req1 = build_inventory_search_request(s1.facts)
    assert _engines(first.facts) == [2.0]
    assert _engines(s1.facts) == [2.0]
    assert s1.facts.get("desired_engine_flexible") is not True
    assert s1.facts.get("desired_engine_any") is not True
    assert [float(x) for x in req1.engine_displacement_liters] == [2.0]
    assert req1.engine_any is False
    key1 = inventory_search_key(s1.facts)

    second = await extract_turn_facts("Pode ser 1.8 também", "")
    s2 = deterministic_merge(s1, second)
    req2 = build_inventory_search_request(s2.facts)
    assert _engines(s2.facts) == [1.8, 2.0]
    assert s2.facts.get("desired_engine_flexible") is True
    assert s2.facts.get("desired_engine_any") is not True
    assert sorted(float(x) for x in req2.engine_displacement_liters) == [1.8, 2.0]
    key2 = inventory_search_key(s2.facts)
    assert key2 != key1

    third = await extract_turn_facts("Na verdade quero só o 1.8", "")
    s3 = deterministic_merge(s2, third)
    req3 = build_inventory_search_request(s3.facts)
    assert _engines(s3.facts) == [1.8]
    assert s3.facts.get("desired_engine_flexible") is not True
    assert s3.facts.get("desired_engine_any") is not True
    assert [float(x) for x in req3.engine_displacement_liters] == [1.8]
    key3 = inventory_search_key(s3.facts)
    assert key3 != key2

    fourth = await extract_turn_facts("Pode ser qualquer motor", "")
    s4 = deterministic_merge(s3, fourth)
    req4 = build_inventory_search_request(s4.facts)
    assert fourth.facts.get("desired_engine_any") is True
    assert "desired_engine_displacement_liters" not in s4.facts
    assert s4.facts.get("desired_engine_any") is True
    assert s4.facts.get("desired_model", "").lower() == "corolla"
    assert req4.engine_displacement_liters == []
    assert req4.engine_any is True
    key4 = inventory_search_key(s4.facts)
    assert key4 != key3
    # Unconstrained search is not the same as an exact 2.0 preference.
    assert key4 != key1
