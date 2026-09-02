"""Unit tests for TurnFacts heuristic extractor (no live OpenAI)."""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

from sdr.config import get_settings
from sdr.domain.types import BusinessIntent
from sdr.understanding.extractor import extract_turn_facts


@pytest.fixture(autouse=True)
def _clear_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    os.environ["OPENAI_API_KEY"] = ""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "expected_intent"),
    [
        ("Quero comprar um Onix", BusinessIntent.PURCHASE),
        ("Preciso financiar um carro", BusinessIntent.PURCHASE_FINANCING),
        ("Quero dar meu Fox na troca", BusinessIntent.TRADE),
        ("Quero vender meu Civic", BusinessIntent.SALE),
        ("Aceitam consignação do meu carro?", BusinessIntent.CONSIGNMENT),
        ("Quero refinanciar meu veículo", BusinessIntent.REFINANCING),
    ],
)
async def test_heuristic_intents(text: str, expected_intent: BusinessIntent) -> None:
    facts = await extract_turn_facts(text, "")
    assert facts.intent == expected_intent
    assert isinstance(facts.facts, dict)


@pytest.mark.asyncio
async def test_vendedor_sets_explicit_handoff_signal() -> None:
    facts = await extract_turn_facts("Quero falar com um vendedor agora", "")
    assert facts.signals.explicit_handoff is True


@pytest.mark.asyncio
async def test_unittest_mock_client_uses_heuristic_not_api() -> None:
    mock_client = MagicMock()
    facts = await extract_turn_facts("Quero comprar um HB20", "", client=mock_client)
    assert facts.intent == BusinessIntent.PURCHASE
    mock_client.chat.completions.create.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_intent_when_no_keywords() -> None:
    facts = await extract_turn_facts("blablabla xyz", "")
    assert facts.intent == BusinessIntent.UNKNOWN


@pytest.mark.asyncio
async def test_purchase_actionable_extracts_model_and_budget() -> None:
    text = (
        "Quero uma Hilux até 250 mil, dou 80 mil de entrada e "
        "quero comprar nos próximos 30 dias."
    )
    facts = await extract_turn_facts(text, "")
    assert facts.intent == BusinessIntent.PURCHASE
    assert facts.facts.get("desired_model", "").lower() == "hilux"
    assert facts.facts.get("budget") == 250000 or facts.facts.get("max_price") == 250000
