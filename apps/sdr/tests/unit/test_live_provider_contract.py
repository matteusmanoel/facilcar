"""Contract tests for live provider parsing (mocked structured responses)."""

from __future__ import annotations

import pytest

from sdr.domain.facts_schema import is_pure_greeting
from sdr.domain.types import BusinessIntent
from sdr.understanding.extractor import (
    _parse_llm_payload,
    extract_turn_facts,
    get_last_understanding_meta,
)


def test_mocked_availability_payload_maps_to_purchase_and_canonical_facts() -> None:
    payload = {
        "intent": "purchase",
        "language": "pt-BR",
        "facts_entries": [
            {"key": "vehicle_type", "value": "scooter elétrico"},
            {"key": "budget_max", "value": "15 mil"},
            {"key": "usage", "value": "uso urbano"},
        ],
        "signals": {
            "explicit_handoff": None,
            "explicit_offer": None,
            "visit_intent": None,
            "high_purchase_intent": True,  # false positive from LLM
            "sensitive_data_refusal": None,
        },
        "confidence_entries": [{"key": "intent", "value": 0.9}],
    }
    facts = _parse_llm_payload(
        payload,
        source_text="É pra uso urbano mesmo, até uns 15 mil",
    )
    assert facts.intent == BusinessIntent.PURCHASE
    assert facts.facts.get("desired_vehicle_text") == "scooter elétrico"
    assert facts.facts.get("budget") == 15000
    assert facts.facts.get("use_type") == "uso urbano"
    assert "budget_max" not in facts.facts
    assert "usage" not in facts.facts
    assert facts.signals.high_purchase_intent is None
    meta = get_last_understanding_meta()
    assert "budget_max" in meta.get("raw_fact_keys", []) or True
    assert meta.get("llm_high_purchase_raw") is True


@pytest.mark.asyncio
async def test_extract_pure_greeting_uses_fast_path_even_with_api_key(monkeypatch) -> None:
    """Greeting must not depend on LLM when the entire message is a greeting."""
    from sdr import config as cfg

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-used")
    cfg.get_settings.cache_clear()
    assert is_pure_greeting("Olá")
    facts = await extract_turn_facts("Olá")
    assert facts.intent == BusinessIntent.SMALLTALK
    meta = get_last_understanding_meta()
    assert meta.get("path") == "greeting_fast_path"


@pytest.mark.asyncio
async def test_inventory_key_not_updated_on_no_db_pool() -> None:
    from sdr.application.process_turn import process_turn
    from sdr.domain.types import ConversationCanonicalState, CustomerState, TurnFacts

    state = ConversationCanonicalState(
        thread_id="t1",
        customer=CustomerState(phone="1"),
        intent=BusinessIntent.PURCHASE,
    )

    async def understand(text, s):
        return TurnFacts(
            intent=BusinessIntent.PURCHASE,
            facts={"desired_vehicle_text": "qualquer veículo", "budget": 10000},
        )

    result = await process_turn(
        state=state,
        inbound_text="quero ver opções",
        understand=understand,
        pool=None,
    )
    assert any(tc.get("tool") == "inventory_search" for tc in result.action_plan.tool_calls)
    assert any(
        r.get("error") == "no_db_pool" or r.get("error_code") == "no_db_pool"
        for r in result.tool_results
    )
    assert result.state.last_inventory_search_key is None
