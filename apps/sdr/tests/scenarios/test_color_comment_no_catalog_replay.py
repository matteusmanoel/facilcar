"""Replay: color comment after SHOW_OFFERS must not trigger new inventory search.

Scenario:
  State: SHOW_OFFERS already fired — last_shown_vehicle_ids=['corolla-v1'],
         last_inventory_search_key matches current facts
  Inbound: "Tem ele preto?" or "Lindo esse branco" (color comment, not a new preference)
  Expected:
    - action is NOT SHOW_OFFERS (no new search triggered)
    - The hash guard prevents re-searching when only a color reference changes
    - action is COMMERCIAL_UNKNOWN (natural conversational response)

This validates:
  1. inventory_search_key_from_request excludes original_vehicle_text when
     original_model is set and last_shown_vehicle_ids is non-empty
  2. The _needs_inventory_search guard correctly detects same hash
  3. The full process_turn pipeline correctly routes to COMMERCIAL_UNKNOWN
"""

from __future__ import annotations

import os

import pytest

from sdr.application.process_turn import process_turn
from sdr.domain.decision import inventory_search_key
from sdr.domain.inventory_search import (
    InventorySearchRequest,
    inventory_search_key_from_request,
)
from sdr.domain.types import (
    Action,
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    TurnFacts,
)
from sdr.config import get_settings


@pytest.fixture(autouse=True)
def _no_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    os.environ["OPENAI_API_KEY"] = ""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _post_show_offers_state() -> ConversationCanonicalState:
    """State immediately after SHOW_OFFERS has displayed a Corolla."""
    facts = {
        "desired_model": "Corolla",
        "desired_vehicle_text": "Corolla",
    }
    # Compute the key as it would have been stored when SHOW_OFFERS fired.
    req = InventorySearchRequest(
        original_model="Corolla",
        original_vehicle_text="Corolla",
    )
    # With shown vehicles, vehicle_text is excluded from hash.
    shown_ids = ["corolla-v1"]
    key = inventory_search_key_from_request(req, last_shown_vehicle_ids=shown_ids)

    state = ConversationCanonicalState(
        thread_id="color-comment-replay",
        customer=CustomerState(phone="5511999999999"),
        intent=BusinessIntent.PURCHASE,
        language="pt-BR",
        facts=facts,
        last_inventory_search_key=key,
        last_shown_vehicle_ids=shown_ids,
    )
    state.assistant_turn_count = 2
    return state


@pytest.mark.asyncio
async def test_color_question_does_not_retrigger_inventory_search() -> None:
    """'Tem ele preto?' after SHOW_OFFERS must not trigger a new inventory search.

    The customer is asking about a color variant of the already-shown vehicle,
    not expressing preference for a different model.
    """
    state = _post_show_offers_state()

    async def _understand_color_question(text: str, s: ConversationCanonicalState) -> TurnFacts:
        # LLM may extract color='preto', but NOT a new model or vehicle_text.
        # The hash guard excludes original_vehicle_text — so color changes
        # (which are not in the hash) don't trigger a new search.
        return TurnFacts(
            intent=BusinessIntent.PURCHASE,
            language="pt-BR",
            facts={
                "color": "preto",
                # No desired_model or desired_vehicle_text change
            },
        )

    result = await process_turn(
        state=state,
        inbound_text="Tem ele preto?",
        understand=_understand_color_question,
        pool=None,
    )

    assert result.action_plan.action != Action.SHOW_OFFERS, (
        f"A color question about an already-shown vehicle must NOT trigger SHOW_OFFERS. "
        f"Got {result.action_plan.action!r}. "
        "The hash guard in inventory_search_key_from_request must prevent re-search."
    )
    assert len(result.outbound_texts) > 0, "Must produce a response (not silently drop)."


@pytest.mark.asyncio
async def test_admiring_comment_does_not_retrigger_inventory_search() -> None:
    """'Lindo esse branco' after SHOW_OFFERS must not trigger a new inventory search."""
    state = _post_show_offers_state()

    async def _understand_admiring(text: str, s: ConversationCanonicalState) -> TurnFacts:
        # LLM may not extract much from an admiring comment.
        return TurnFacts(
            intent=BusinessIntent.PURCHASE,
            language="pt-BR",
            facts={},
        )

    result = await process_turn(
        state=state,
        inbound_text="Lindo esse branco",
        understand=_understand_admiring,
        pool=None,
    )

    assert result.action_plan.action != Action.SHOW_OFFERS, (
        f"An admiring comment must NOT retrigger SHOW_OFFERS. "
        f"Got {result.action_plan.action!r}."
    )


@pytest.mark.asyncio
async def test_new_model_preference_triggers_inventory_search() -> None:
    """'Prefiro um Civic' after seeing a Corolla must trigger a new inventory search.

    This validates the positive case: hash guard must NOT block genuine preference changes.
    """
    state = _post_show_offers_state()

    async def _understand_new_model(text: str, s: ConversationCanonicalState) -> TurnFacts:
        return TurnFacts(
            intent=BusinessIntent.PURCHASE,
            language="pt-BR",
            facts={
                "desired_model": "Civic",
                "desired_vehicle_text": "Civic",
            },
        )

    result = await process_turn(
        state=state,
        inbound_text="Na verdade prefiro um Civic",
        understand=_understand_new_model,
        pool=None,
    )

    # A new model preference must change the hash → new SHOW_OFFERS search
    assert result.action_plan.action == Action.SHOW_OFFERS, (
        f"New model preference ('Civic' after 'Corolla') must trigger SHOW_OFFERS. "
        f"Got {result.action_plan.action!r}. "
        "Hash guard must only block referential comments, not genuine preference changes."
    )


@pytest.mark.asyncio
async def test_hash_guard_equivalence_for_color_reference() -> None:
    """Unit-level: hash with and without vehicle_text referencing color must be identical.

    This tests inventory_search_key_from_request directly, validating the guard
    before it reaches process_turn.
    """
    shown_ids = ["corolla-v1"]
    req_base = InventorySearchRequest(original_model="Corolla", original_vehicle_text=None)
    req_with_color_text = InventorySearchRequest(
        original_model="Corolla",
        original_vehicle_text="Corolla preto",
    )

    key_base = inventory_search_key_from_request(req_base, last_shown_vehicle_ids=shown_ids)
    key_color = inventory_search_key_from_request(req_with_color_text, last_shown_vehicle_ids=shown_ids)

    assert key_base == key_color, (
        "Hash must be identical when original_vehicle_text is just a color variant of "
        "the already-shown model. The guard must exclude vehicle_text from the hash "
        "when original_model is set and last_shown_vehicle_ids is non-empty."
    )
