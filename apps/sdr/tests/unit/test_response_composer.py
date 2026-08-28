"""Unit tests for response composer + bubble validator (no live OpenAI)."""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

from sdr.config import get_settings
from sdr.domain.introduction import is_first_contact_reopen
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
async def test_payment_question_is_avista_or_financed_not_both() -> None:
    bubbles = await compose_response(
        {"language": "pt-BR", "ack_kind": "deal_purchase"},
        {
            "action": "ask_info",
            "handoff": False,
            "tool_calls": [],
            "next_question": "payment_method",
        },
        {},
    )
    joined = " ".join(bubbles).lower()
    assert "à vista" in joined or "avista" in joined
    assert "financiado" in joined
    assert "os dois" not in joined
    assert "anotei" not in joined
    assert "então é compra" not in joined
    bubbles = await compose_response(
        {"language": "pt-BR", "missing_fields": ["deal_type"]},
        {
            "action": "ask_info",
            "handoff": False,
            "tool_calls": [],
            "next_question": "deal_type",
        },
        {},
    )
    assert len(bubbles) == 1
    assert "compra" in bubbles[0].lower() and "troca" in bubbles[0].lower()


@pytest.mark.asyncio
async def test_payment_question_is_avista_or_financed_not_both() -> None:
    bubbles = await compose_response(
        {"language": "pt-BR", "ack_kind": "deal_purchase"},
        {
            "action": "ask_info",
            "handoff": False,
            "tool_calls": [],
            "next_question": "payment_method",
        },
        {},
    )
    joined = " ".join(bubbles).lower()
    assert "à vista" in joined or "avista" in joined
    assert "financiado" in joined
    assert "os dois" not in joined
    assert "anotei" not in joined
    assert "então é compra" not in joined


@pytest.mark.asyncio
async def test_document_ack_uses_name_and_ficha_not_financing_echo() -> None:
    bubbles = await compose_response(
        {
            "language": "pt-BR",
            "ack_kind": "document_received",
            "inbound_content_type": "DOCUMENT",
            "customer_name": "Maria Silva",
        },
        {"action": "ask_info", "handoff": False, "tool_calls": []},
        {},
    )
    joined = " ".join(bubbles)
    assert "Maria" in joined
    assert "ficha" in joined.lower()
    assert "anotei" not in joined.lower()


@pytest.mark.asyncio
async def test_send_location_followup_is_visit_cta_not_address() -> None:
    bubbles = await compose_response(
        {"language": "pt-BR", "visit_cta_style": "warm_invite"},
        {"action": "send_location", "handoff": False, "tool_calls": []},
        {
            "site_settings": {
                "address": "Av. Brasil, 1000",
                "city": "Foz do Iguaçu",
                "state": "PR",
            },
            "location_pin": {"latitude": -24.9, "longitude": -53.4},
            "location_text": "Av. Brasil, 1000",
        },
    )
    assert len(bubbles) == 1
    joined = bubbles[0].lower()
    assert "café" in joined or "cafe" in joined
    assert "av. brasil" not in joined
    assert "foz" not in joined


@pytest.mark.asyncio
async def test_send_location_hot_asks_visit_this_week() -> None:
    bubbles = await compose_response(
        {"language": "pt-BR", "visit_cta_style": "hot_schedule"},
        {"action": "send_location", "handoff": False, "tool_calls": []},
        {"location_pin": {"latitude": -24.9, "longitude": -53.4}},
    )
    joined = " ".join(bubbles).lower()
    assert "visita" in joined
    assert "semana" in joined
    assert "ipanema" not in joined


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


def test_validator_strips_os_dois_and_robotic_ack() -> None:
    bubbles = validate_bubbles(
        [
            "Anotei: financiado.",
            "Seria à vista, financiado, ou os dois?",
        ]
    )
    joined = " ".join(bubbles).lower()
    assert "anotei" not in joined
    assert "os dois" not in joined
    assert "à vista" in joined
    assert "financiado" in joined
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


@pytest.mark.asyncio
async def test_smalltalk_continuation_template_does_not_reopen() -> None:
    bubbles = await compose_response(
        {
            "language": "pt-BR",
            "should_introduce": False,
            "inbound_text": "Tudo bem e você?",
            "response_objective": "Continuação: responda ao que o cliente disse.",
        },
        {"action": "smalltalk", "handoff": False, "tool_calls": []},
        {},
    )
    assert bubbles
    assert not is_first_contact_reopen(bubbles)
    joined = " ".join(bubbles).lower()
    assert "sou a júlia" not in joined
    assert "como posso ajudar você hoje" not in joined


@pytest.mark.asyncio
async def test_smalltalk_first_turn_template_may_introduce() -> None:
    bubbles = await compose_response(
        {"language": "pt-BR", "should_introduce": True, "inbound_text": "Olá"},
        {"action": "smalltalk", "handoff": False, "tool_calls": []},
        {},
    )
    joined = " ".join(bubbles).lower()
    assert "júlia" in joined or "julia" in joined
    assert "compra" in joined
