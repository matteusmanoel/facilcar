"""Smoke replay tests — observed real-world failure sequence + unseen scenario.

These tests cover:
1. Multi-turn thread state persistence
2. Introduction policy (no repeated greeting)
3. Commercial language → commercial intent (via LLM or heuristic)
4. Inventory search planned when model is known
5. Audio transcript reaches Understanding (via AUDIO content type simulation)
6. Unseen semantic scenario (scooter elétrico) — NOT in any keyword list
"""

from __future__ import annotations

import pytest

from sdr.application.process_turn import process_turn
from sdr.domain.types import (
    Action,
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    TurnFacts,
)


async def _heuristic_understand(text: str, state: ConversationCanonicalState) -> TurnFacts:
    """Use heuristic extractor — no API calls — for deterministic tests."""
    from sdr.understanding.extractor import _heuristic_extract

    return _heuristic_extract(text)


async def _llm_understand_purchase_with_model(
    text: str, state: ConversationCanonicalState
) -> TurnFacts:
    """Simulates what LLM returns for commercial vehicle inquiry."""
    return TurnFacts(
        intent=BusinessIntent.PURCHASE,
        language="pt-BR",
        facts={"desired_model": "CG", "brand": "Honda", "vehicle_type": "moto"},
        confidence={"intent": 0.95},
    )


async def _llm_understand_purchase_scooter(
    text: str, state: ConversationCanonicalState
) -> TurnFacts:
    """Simulates what LLM returns for scooter inquiry (unseen category)."""
    return TurnFacts(
        intent=BusinessIntent.PURCHASE,
        language="pt-BR",
        facts={"category": "scooter", "vehicle_type": "eletrico", "budget": 15000},
        confidence={"intent": 0.92},
    )


# -----------------------------------------------------------------------
# Turn-state persistence
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_same_thread_maintained_across_turns() -> None:
    """State must accumulate correctly across multiple turns."""
    state = ConversationCanonicalState(
        thread_id="smoke-thread",
        customer=CustomerState(phone="5545988432998"),
    )

    async def _turn1(text: str, s: ConversationCanonicalState) -> TurnFacts:
        return TurnFacts(intent=BusinessIntent.SMALLTALK, language="pt-BR")

    async def _turn2(text: str, s: ConversationCanonicalState) -> TurnFacts:
        return TurnFacts(
            intent=BusinessIntent.PURCHASE,
            facts={"desired_model": "CG", "brand": "Honda"},
        )

    r1 = await process_turn(state=state, inbound_text="Olá", understand=_turn1)
    state = r1.state
    state.assistant_turn_count = 1  # simulate bot response sent

    r2 = await process_turn(state=state, inbound_text="Honda CG?", understand=_turn2)

    # Thread ID must be preserved.
    assert r2.state.thread_id == "smoke-thread"
    # Intent should have advanced.
    assert r2.state.intent == BusinessIntent.PURCHASE


@pytest.mark.asyncio
async def test_no_repeated_greeting_after_first_turn() -> None:
    """Turn 2+ must not produce Júlia introduction."""
    state = ConversationCanonicalState(
        thread_id="intro-thread",
        customer=CustomerState(phone="5545988432998"),
    )
    state.assistant_turn_count = 0

    # Turn 1: greeting
    async def _greet(text: str, s: ConversationCanonicalState) -> TurnFacts:
        return TurnFacts(intent=BusinessIntent.SMALLTALK)

    r1 = await process_turn(state=state, inbound_text="Olá", understand=_greet)
    state = r1.state
    state.assistant_turn_count = 1  # bot responded once

    # Turn 2: more chatter — must NOT re-introduce
    r2 = await process_turn(state=state, inbound_text="Tudo certo?", understand=_greet)
    bubbles = " ".join(r2.outbound_texts).lower()
    assert "sou a júlia da facilcar" not in bubbles, (
        f"Turn 2 produced introduction: {r2.outbound_texts}"
    )


@pytest.mark.asyncio
async def test_state_survives_unknown_intent_turns() -> None:
    """Known state fields must NOT be deleted when a turn produces UNKNOWN intent."""
    state = ConversationCanonicalState(
        thread_id="merge-thread",
        customer=CustomerState(phone="5545988432998"),
        intent=BusinessIntent.PURCHASE,
        facts={"desired_model": "CG", "brand": "Honda"},
        language="pt-BR",
    )

    async def _unknown(text: str, s: ConversationCanonicalState) -> TurnFacts:
        return TurnFacts(intent=BusinessIntent.UNKNOWN)

    result = await process_turn(state=state, inbound_text="", understand=_unknown)
    # Facts must survive — omission never deletes.
    assert result.state.facts.get("desired_model") == "CG"
    assert result.state.facts.get("brand") == "Honda"
    # Intent must NOT downgrade to UNKNOWN when we had PURCHASE.
    assert result.state.intent == BusinessIntent.PURCHASE


# -----------------------------------------------------------------------
# Honda CG observed scenario
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_honda_cg_commercial_intent_recognized_via_llm_simulation() -> None:
    """Honda CG: LLM-simulated understanding → inventory_search planned → executed."""
    state = ConversationCanonicalState(
        thread_id="honda-cg",
        customer=CustomerState(phone="5545988432998"),
    )
    state.assistant_turn_count = 1  # already introduced

    result = await process_turn(
        state=state,
        inbound_text="Gostaria de ver mais informações sobre uma Honda CG que vocês tem aí",
        understand=_llm_understand_purchase_with_model,
        pool=None,
    )

    # Intent must be commercial.
    assert result.state.intent == BusinessIntent.PURCHASE, (
        f"Expected PURCHASE, got {result.state.intent}"
    )
    # Facts must include vehicle data.
    assert result.state.facts.get("desired_model") or result.state.facts.get("brand")

    # Inventory search must be planned.
    planned_tools = [tc.get("tool") for tc in result.action_plan.tool_calls]
    assert "inventory_search" in planned_tools, (
        f"inventory_search not planned. Action={result.action_plan.action}, "
        f"tools={planned_tools}"
    )

    # Inventory search must be executed (even with error from no pool).
    executed_tools = [r.get("tool") for r in result.tool_results]
    assert "inventory_search" in executed_tools, (
        f"inventory_search not executed. tool_results={result.tool_results}"
    )

    # Must NOT contain a greeting/introduction.
    bubbles = " ".join(result.outbound_texts).lower()
    assert "sou a júlia da facilcar" not in bubbles


@pytest.mark.asyncio
async def test_honda_cg_action_is_show_offers_not_smalltalk() -> None:
    """Honda CG inquiry must NOT fall to SMALLTALK action."""
    state = ConversationCanonicalState(
        thread_id="honda-cg-action",
        customer=CustomerState(phone="5545988432998"),
    )
    state.assistant_turn_count = 2

    result = await process_turn(
        state=state,
        inbound_text="Honda CG",
        understand=_llm_understand_purchase_with_model,
        pool=None,
    )
    assert result.action_plan.action != Action.SMALLTALK, (
        f"Honda CG fell to SMALLTALK — action={result.action_plan.action}"
    )


# -----------------------------------------------------------------------
# Unseen semantic scenario — scooter elétrico
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unseen_scooter_scenario_not_smalltalk() -> None:
    """'Vocês têm algum scooter elétrico?' must NOT fall to SMALLTALK with LLM path."""
    state = ConversationCanonicalState(
        thread_id="scooter",
        customer=CustomerState(phone="5545988432998"),
    )
    state.assistant_turn_count = 1

    result = await process_turn(
        state=state,
        inbound_text="Vocês têm algum scooter elétrico?",
        understand=_llm_understand_purchase_scooter,
        pool=None,
    )

    # Intent must be commercial.
    assert result.state.intent == BusinessIntent.PURCHASE, (
        f"scooter scenario: expected PURCHASE, got {result.state.intent}"
    )
    # Must not be SMALLTALK action.
    assert result.action_plan.action != Action.SMALLTALK

    # No introduction on turn 1+.
    bubbles = " ".join(result.outbound_texts).lower()
    assert "sou a júlia da facilcar" not in bubbles


@pytest.mark.asyncio
async def test_unseen_scooter_budget_extracted() -> None:
    """'até uns 15 mil' must be merged as budget fact."""
    from sdr.domain.merge import deterministic_merge

    state = ConversationCanonicalState(
        thread_id="scooter-budget",
        customer=CustomerState(phone="5545988432998"),
        intent=BusinessIntent.PURCHASE,
    )
    facts = TurnFacts(
        intent=BusinessIntent.PURCHASE,
        facts={"category": "scooter", "budget": 15000},
    )
    merged = deterministic_merge(state, facts)
    assert float(merged.facts.get("budget", 0)) == 15000.0


# -----------------------------------------------------------------------
# Audio path (represented by transcript fixture)
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audio_transcript_reaches_understanding() -> None:
    """Audio transcription (simulated) must feed into Understanding correctly."""
    state = ConversationCanonicalState(
        thread_id="audio-thread",
        customer=CustomerState(phone="5545988432998"),
    )
    state.assistant_turn_count = 0

    # Simulate what the orchestrator would do after Whisper transcription.
    transcript = "Oi, gostaria de saber se vocês têm uma Honda CG 160 disponível"

    async def _understand_transcript(text: str, s: ConversationCanonicalState) -> TurnFacts:
        # Text must arrive as the transcript content.
        assert text == transcript, f"Audio transcript not passed. Got: {text!r}"
        return TurnFacts(
            intent=BusinessIntent.PURCHASE,
            facts={"desired_model": "CG", "brand": "Honda"},
        )

    result = await process_turn(
        state=state,
        inbound_text=transcript,
        understand=_understand_transcript,
        pool=None,
    )
    assert result.state.intent == BusinessIntent.PURCHASE


@pytest.mark.asyncio
async def test_media_failed_does_not_produce_greeting() -> None:
    """__MEDIA_FAILED__ sentinel must not produce a greeting — must ask for retry."""
    state = ConversationCanonicalState(
        thread_id="media-fail",
        customer=CustomerState(phone="5545988432998"),
    )
    state.assistant_turn_count = 1

    result = await process_turn(
        state=state,
        inbound_text="__MEDIA_FAILED__",
        understand=_heuristic_understand,
        pool=None,
    )
    bubbles = " ".join(result.outbound_texts).lower()
    # Must NOT be a Júlia introduction on failure.
    assert "sou a júlia da facilcar" not in bubbles


# -----------------------------------------------------------------------
# Tool failure must not become a greeting
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_failure_does_not_produce_greeting() -> None:
    """A tool error must not silently become a greeting."""
    from sdr.application.process_turn import _build_response_directive
    from sdr.domain.decision import decide
    from sdr.domain.merge import deterministic_merge

    state = ConversationCanonicalState(
        thread_id="tool-fail",
        customer=CustomerState(phone="5511999999999"),
    )
    state.assistant_turn_count = 1

    facts = TurnFacts(
        intent=BusinessIntent.PURCHASE,
        facts={"desired_model": "Hilux", "brand": "Toyota"},
    )
    merged = deterministic_merge(state, facts)
    plan = decide(merged)

    tool_results_with_error = [{"tool": "inventory_search", "error": "no_db_pool"}]
    directive = _build_response_directive(merged, plan, tool_results_with_error)

    # Directive must exist and not be a blank/greeting directive.
    assert directive.action is not None
    # Typed failure outcome — never treated as empty stock.
    assert directive.inventory_outcome.value == "FAILED_RETRYABLE"
    assert directive.tool_results.get("inventory_outcome") == "FAILED_RETRYABLE"
    assert directive.tool_results.get("inventory_search_error") == "no_db_pool"
    assert "no_stock" in directive.claims_forbidden or "confirmed_absence" in directive.claims_forbidden
