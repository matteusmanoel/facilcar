"""Tests for deterministic introduction / greeting policy.

Invariants:
- First bot turn may introduce.
- Subsequent turns do NOT introduce.
- Technical failures do NOT produce greeting templates.
- SMALLTALK on turn 2+ uses a non-intro response.
"""

from __future__ import annotations

import pytest

from sdr.application.process_turn import process_turn
from sdr.domain.types import (
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    TurnFacts,
)


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


@pytest.mark.asyncio
async def test_first_turn_may_introduce() -> None:
    """Turn 0: should_introduce=True → introduction greeting expected."""
    state = _state(turn_count=0)
    result = await process_turn(state=state, inbound_text="Olá", understand=_fixed_smalltalk)
    bubbles = " ".join(result.outbound_texts).lower()
    # Either LLM or template — should be some form of greeting.
    assert len(result.outbound_texts) > 0


@pytest.mark.asyncio
async def test_second_turn_does_not_reintroduce() -> None:
    """Turn 1+: should_introduce=False → no 'Sou a Júlia' introduction."""
    state = _state(turn_count=1)  # already had one bot response
    result = await process_turn(state=state, inbound_text="Oi de novo", understand=_fixed_smalltalk)
    bubbles = " ".join(result.outbound_texts).lower()
    # Must NOT contain introduction phrase.
    assert "sou a júlia" not in bubbles
    assert "soy júlia" not in bubbles


@pytest.mark.asyncio
async def test_third_turn_does_not_reintroduce() -> None:
    """Subsequent turns with any intent must not re-introduce."""
    state = _state(turn_count=3)
    result = await process_turn(state=state, inbound_text="Como assim?", understand=_fixed_unknown)
    bubbles = " ".join(result.outbound_texts).lower()
    assert "sou a júlia" not in bubbles
    assert "soy júlia" not in bubbles


@pytest.mark.asyncio
async def test_template_smalltalk_turn1_no_intro() -> None:
    """Template path (no OpenAI): SMALLTALK on turn 1+ must not re-introduce."""
    state = _state(turn_count=2)
    result = await process_turn(state=state, inbound_text="tá bom", understand=_fixed_smalltalk)
    bubbles = " ".join(result.outbound_texts).lower()
    assert "sou a júlia da facilcar" not in bubbles


@pytest.mark.asyncio
async def test_smalltalk_template_turn0_may_introduce() -> None:
    """Template path: SMALLTALK on turn 0 MAY include introduction."""
    state = _state(turn_count=0)
    result = await process_turn(state=state, inbound_text="Olá", understand=_fixed_smalltalk)
    # Must have some response.
    assert len(result.outbound_texts) > 0
    # First turn: introduction is allowed (but not required to contain the exact phrase
    # since the composer may choose any appropriate greeting).


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
    directive0 = _build_response_directive(merged0, plan0, [])
    assert directive0.should_introduce is True

    state1 = _state(turn_count=1)
    merged1 = deterministic_merge(state1, facts)
    plan1 = decide(merged1)
    directive1 = _build_response_directive(merged1, plan1, [])
    assert directive1.should_introduce is False
