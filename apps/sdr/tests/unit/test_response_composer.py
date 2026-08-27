"""Unit tests for response composer + bubble validator (no live OpenAI)."""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

from sdr.config import get_settings
from sdr.understanding.persona_prompts import HANDOFF_CONFIRMATION_PT
from sdr.understanding.response_composer import compose_response
from sdr.understanding.validator import validate_bubbles


@pytest.fixture(autouse=True)
def _clear_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    os.environ["OPENAI_API_KEY"] = ""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_handoff_returns_one_confirmation() -> None:
    state = {"language": "pt-BR", "thread_id": "t1"}
    action_plan = {
        "action": "handoff_vendor",
        "handoff": True,
        "tool_calls": [],
    }
    bubbles = await compose_response(state, action_plan, {})
    assert len(bubbles) == 1
    assert bubbles[0] == HANDOFF_CONFIRMATION_PT


@pytest.mark.asyncio
async def test_no_reply_returns_empty() -> None:
    bubbles = await compose_response(
        {"language": "pt-BR"},
        {"action": "no_reply", "handoff": False, "tool_calls": []},
        {},
    )
    assert bubbles == []


@pytest.mark.asyncio
async def test_ask_info_known_field() -> None:
    bubbles = await compose_response(
        {"language": "pt-BR", "missing_fields": ["budget"]},
        {
            "action": "ask_info",
            "handoff": False,
            "tool_calls": [],
            "next_question": "budget",
        },
        {},
    )
    assert len(bubbles) == 1
    assert "valor" in bubbles[0].lower() or "investir" in bubbles[0].lower()


@pytest.mark.asyncio
async def test_send_location_from_site_settings_stub() -> None:
    tool_context = {
        "site_settings": {
            "address": "Av. Brasil, 1000",
            "city": "Foz do Iguaçu",
            "state": "PR",
        }
    }
    bubbles = await compose_response(
        {"language": "pt-BR"},
        {"action": "send_location", "handoff": False, "tool_calls": []},
        tool_context,
    )
    assert len(bubbles) == 1
    assert "Av. Brasil" in bubbles[0]
    assert "Foz do Iguaçu" in bubbles[0]


@pytest.mark.asyncio
async def test_mock_client_does_not_call_openai() -> None:
    mock_client = MagicMock()
    bubbles = await compose_response(
        {"language": "pt-BR"},
        {"action": "handoff_vendor", "handoff": True, "tool_calls": []},
        {},
        client=mock_client,
    )
    assert len(bubbles) == 1
    mock_client.chat.completions.create.assert_not_called()


def test_validator_flags_promise_language() -> None:
    bubbles = validate_bubbles(
        [
            "Taxa de 1,49% ao mês e você já está aprovado!",
            "Dá pra ficar 100% financiado.",
        ]
    )
    joined = " ".join(bubbles).lower()
    assert "1,49%" not in joined
    assert "aprovado" not in joined
    assert "100% financiado" not in joined
    assert "análise" in joined or "sujeito" in joined
