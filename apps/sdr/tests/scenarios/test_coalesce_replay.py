"""Scenario: coalesce three bubbles into one Understanding turn (replay-level)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from sdr.application.process_turn import process_turn
from sdr.domain.types import ConversationCanonicalState, CustomerState
from sdr.replay import _make_deterministic_understand


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.mark.asyncio
async def test_coalesce_three_bubbles_one_response() -> None:
    data = yaml.safe_load((FIXTURES / "coalesce_three_bubbles.yaml").read_text())
    turns = data["turns"]
    understand, _ = _make_deterministic_understand(turns)
    state = ConversationCanonicalState(
        thread_id="coalesce-test",
        customer=CustomerState(phone="5511999990000"),
    )
    turn = turns[0]
    parts = [str(p["text"]) for p in turn["coalesce"]]
    composed = "\n".join(parts)
    assert composed == "Oi\nquero um Corolla\naté 80 mil"

    result = await process_turn(
        state=state,
        inbound_text=composed,
        understand=understand,
    )
    assert result.state.intent.value == "purchase"
    assert result.action_plan.action.value != "smalltalk"
    assert result.state.facts.get("desired_vehicle_text") == "Corolla"
    assert result.state.facts.get("budget") == 80000
    assert len(result.outbound_texts) >= 1
    joined = " ".join(result.outbound_texts).lower()
    assert joined.count("sou a júlia") <= 1
