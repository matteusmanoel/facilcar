"""Tests for deterministic introduction / continuation policy.

Invariants:
- First bot turn may introduce.
- Subsequent SMALLTALK must not reopen as first contact (Oi / Olá / Sou a Júlia).
- Composer receives inbound_text so it can answer the current turn.
- Technical failures do NOT produce greeting templates.
"""

from __future__ import annotations

import os

import pytest

from sdr.application.process_turn import process_turn
from sdr.config import get_settings
from sdr.domain.introduction import is_first_contact_reopen
from sdr.domain.types import (
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    TurnFacts,
)
from sdr.understanding.validator import validate_introduction_policy


@pytest.fixture(autouse=True)
def _clear_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    os.environ["OPENAI_API_KEY"] = ""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _state(*, turn_count: int = 0, intent: BusinessIntent = BusinessIntent.UNKNOWN) -> ConversationCanonicalState:
    s = ConversationCanonicalState(
        thread_id="intro-test",
        customer=CustomerState(phone="5511999999999"),
        intent=intent,
    )
    s.assistant_turn_count = turn_count
    return s


async def _fixed_smalltalk(_text: str, _state: ConversationCanonicalState) -> TurnFacts:
    return TurnFacts(intent=BusinessIntent.SMALLTALK)


async def _fixed_unknown(_text: str, _state: ConversationCanonicalState) -> TurnFacts:
    return TurnFacts(intent=BusinessIntent.UNKNOWN)


def _assert_not_first_contact_reopen(outbound: list[str]) -> None:
    assert outbound, "expected a continuation response"
    assert not is_first_contact_reopen(outbound), (
        f"continuation turn reopened as first contact: {outbound}"
    )
    joined = " ".join(outbound).lower()
    assert "sou a júlia" not in joined
    assert "como posso ajudar você hoje" not in joined


@pytest.mark.asyncio
async def test_first_turn_may_introduce() -> None:
    """Turn 0: should_introduce=True → introduction greeting expected."""
    state = _state(turn_count=0)
    result = await process_turn(state=state, inbound_text="Olá", understand=_fixed_smalltalk)
    bubbles = " ".join(result.outbound_texts).lower()
    assert len(result.outbound_texts) > 0
    assert result.response_directive is not None
    assert result.response_directive.should_introduce is True
    assert result.response_directive.inbound_text == "Olá"
    assert "júlia" in bubbles or "julia" in bubbles or "oi" in bubbles
    assert "compra" in bubbles
    assert "troca" in bubbles
    assert "financiamento" in bubbles or "refinanciamento" in bubbles


@pytest.mark.asyncio
async def test_first_commercial_turn_introduces_with_photos(monkeypatch) -> None:
    from decimal import Decimal

    from sdr.domain.types import Action
    from sdr.tools.inventory import InventoryVehicle

    car = InventoryVehicle(
        id="v1",
        slug="sedan",
        title="HONDA CIVIC EXL",
        brand_name="Honda",
        model="Civic",
        type="CAR",
        price_cash=Decimal("79900"),
        mileage=None,
        color=None,
        year_model=2019,
        year_manufacture=2018,
        version="EXL",
        images=(
            {"id": "c1", "url": "https://cdn.example/cover.jpg", "sortOrder": 0, "isCover": True},
            {"id": "c2", "url": "https://cdn.example/side.jpg", "sortOrder": 1, "isCover": False},
        ),
    )

    async def fake_search(pool, req):
        return [car]

    monkeypatch.setattr("sdr.tools.inventory.search_with_request", fake_search)

    async def understand(text, state):
        return TurnFacts(
            intent=BusinessIntent.PURCHASE,
            language="pt-BR",
            facts={"desired_model": "Civic"},
        )

    result = await process_turn(
        state=_state(turn_count=0),
        inbound_text="Gostaria de mais informações sobre o Civic, está disponível?",
        understand=understand,
        pool=object(),
    )
    assert result.action_plan.action == Action.SHOW_OFFERS
    assert result.response_directive is not None
    assert result.response_directive.should_introduce is True
    joined = " ".join(result.outbound_texts).lower()
    assert "júlia" in joined or "julia" in joined
    assert "excelente opção" in joined
    assert "compra ou troca" in joined
    assert result.outbound_media
    assert result.outbound_media[-1].url.endswith("cover.jpg")
    assert "*" in result.outbound_media[-1].caption


@pytest.mark.asyncio
async def test_second_turn_does_not_reintroduce() -> None:
    """Turn 1+: should_introduce=False → no first-contact greeting."""
    state = _state(turn_count=1)
    result = await process_turn(
        state=state, inbound_text="Oi de novo", understand=_fixed_smalltalk
    )
    _assert_not_first_contact_reopen(result.outbound_texts)


@pytest.mark.asyncio
async def test_reciprocal_smalltalk_after_greeting_does_not_reopen() -> None:
    """Observed: after Olá + intro, 'Tudo bem e você?' must not become a new greeting.

    Class: continuation SMALLTALK is not first contact. No product-term heuristic.
    """
    state = _state(turn_count=0)
    r1 = await process_turn(state=state, inbound_text="Olá", understand=_fixed_smalltalk)
    state = r1.state
    state.assistant_turn_count = 1

    r2 = await process_turn(
        state=state, inbound_text="Tudo bem e você?", understand=_fixed_smalltalk
    )
    assert r2.response_directive is not None
    assert r2.response_directive.should_introduce is False
    assert r2.response_directive.inbound_text == "Tudo bem e você?"
    assert "Continuação" in r2.response_directive.response_objective
    _assert_not_first_contact_reopen(r2.outbound_texts)
    joined = " ".join(r2.outbound_texts).lower()
    assert "procurando" in joined or "buscando" in joined or "certo" in joined


@pytest.mark.asyncio
async def test_reciprocal_smalltalk_semantic_equivalent_does_not_reopen() -> None:
    """Same class with different wording: Bom dia → Tudo ótimo, e aí?"""
    state = _state(turn_count=0)
    r1 = await process_turn(state=state, inbound_text="Bom dia", understand=_fixed_smalltalk)
    state = r1.state
    state.assistant_turn_count = 1

    r2 = await process_turn(
        state=state, inbound_text="Tudo ótimo, e aí?", understand=_fixed_smalltalk
    )
    _assert_not_first_contact_reopen(r2.outbound_texts)


@pytest.mark.asyncio
async def test_third_turn_does_not_reintroduce() -> None:
    """Subsequent turns with any intent must not re-introduce."""
    state = _state(turn_count=3)
    result = await process_turn(state=state, inbound_text="Como assim?", understand=_fixed_unknown)
    bubbles = " ".join(result.outbound_texts).lower()
    assert "sou a júlia" not in bubbles
    assert "soy júlia" not in bubbles
    assert not is_first_contact_reopen(result.outbound_texts)


@pytest.mark.asyncio
async def test_template_smalltalk_turn1_no_intro() -> None:
    """Template path (no OpenAI): SMALLTALK on turn 1+ must not re-introduce."""
    state = _state(turn_count=2)
    result = await process_turn(state=state, inbound_text="tá bom", understand=_fixed_smalltalk)
    _assert_not_first_contact_reopen(result.outbound_texts)


@pytest.mark.asyncio
async def test_smalltalk_template_turn0_may_introduce() -> None:
    """Template path: SMALLTALK on turn 0 MAY include introduction."""
    state = _state(turn_count=0)
    result = await process_turn(state=state, inbound_text="Olá", understand=_fixed_smalltalk)
    assert len(result.outbound_texts) > 0


@pytest.mark.asyncio
async def test_assistant_turn_count_propagated_to_directive() -> None:
    """ResponseDirective receives should_introduce from assistant_turn_count."""
    from sdr.application.process_turn import _build_response_directive
    from sdr.domain.decision import decide
    from sdr.domain.merge import deterministic_merge

    state0 = _state(turn_count=0)
    facts = TurnFacts(intent=BusinessIntent.SMALLTALK)
    merged0 = deterministic_merge(state0, facts)
    plan0 = decide(merged0)
    directive0 = _build_response_directive(merged0, plan0, [], "Olá")
    assert directive0.should_introduce is True
    assert directive0.inbound_text == "Olá"

    state1 = _state(turn_count=1)
    merged1 = deterministic_merge(state1, facts)
    plan1 = decide(merged1)
    directive1 = _build_response_directive(merged1, plan1, [], "Tudo bem e você?")
    assert directive1.should_introduce is False
    assert directive1.inbound_text == "Tudo bem e você?"
    assert "Continuação" in directive1.response_objective


def test_validator_rewrites_observed_first_contact_reopen() -> None:
    """Exact observed outbound on continuation SMALLTALK must be rewritten."""
    bubbles, result = validate_introduction_policy(
        ["Oi! Como posso ajudar você hoje?"],
        should_introduce=False,
        action="smalltalk",
        language="pt-BR",
    )
    assert result["pass"] is False
    assert "first_contact_reopen" in result["violations"]
    assert not is_first_contact_reopen(bubbles)


def test_validator_allows_introduction_on_first_turn() -> None:
    bubbles, result = validate_introduction_policy(
        ["Oi! Sou a Júlia da FacilCar, tudo bem?"],
        should_introduce=True,
        action="smalltalk",
        language="pt-BR",
    )
    assert result["pass"] is True
    assert "júlia" in bubbles[0].lower()
