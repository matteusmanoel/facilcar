"""Pending alternatives + budget status + scope widening contracts."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from sdr.application.process_turn import process_turn
from sdr.domain.budget_status import BudgetStatus
from sdr.domain.decision import decide
from sdr.domain.merge import deterministic_merge
from sdr.domain.pending_interaction import (
    AlternativeScope,
    PendingInteraction,
    PendingResolution,
)
from sdr.domain.types import (
    Action,
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    TurnFacts,
)
from sdr.tools.inventory import InventoryVehicle


def _state(**kwargs) -> ConversationCanonicalState:
    base = ConversationCanonicalState(
        thread_id="t1",
        customer=CustomerState(phone="5511999999999"),
        intent=BusinessIntent.PURCHASE,
        facts={"desired_model": "corolla"},
        assistant_turn_count=1,
        last_inventory_search_key="oldkey01",
        last_inventory_outcome="SUCCESS_EMPTY",
        pending_interaction=PendingInteraction.OFFER_ALTERNATIVES,
    )
    for k, v in kwargs.items():
        setattr(base, k, v)
    return base


def test_accept_pending_sets_similar_and_clears() -> None:
    prev = _state()
    facts = TurnFacts(
        intent=BusinessIntent.PURCHASE,
        pending_resolution=PendingResolution.ACCEPT,
    )
    merged = deterministic_merge(prev, facts)
    assert merged.pending_interaction == PendingInteraction.NONE
    assert merged.alternative_scope == AlternativeScope.SIMILAR
    assert merged.facts.get("desired_model") == "corolla"


def test_any_vehicle_explicit_clears_pending_preserves_model() -> None:
    prev = _state()
    facts = TurnFacts(
        intent=BusinessIntent.PURCHASE,
        alternative_scope=AlternativeScope.ANY_VEHICLE,
        pending_resolution=PendingResolution.ACCEPT,
    )
    merged = deterministic_merge(prev, facts)
    assert merged.alternative_scope == AlternativeScope.ANY_VEHICLE
    assert merged.pending_interaction == PendingInteraction.NONE
    assert merged.facts["desired_model"] == "corolla"


def test_reject_pending_clears_without_widening() -> None:
    prev = _state()
    facts = TurnFacts(
        intent=BusinessIntent.PURCHASE,
        pending_resolution=PendingResolution.REJECT,
    )
    merged = deterministic_merge(prev, facts)
    assert merged.pending_interaction == PendingInteraction.NONE
    assert merged.alternative_scope == AlternativeScope.NONE


def test_ambiguous_keeps_pending_and_decide_clarifies() -> None:
    prev = _state()
    facts = TurnFacts(
        intent=BusinessIntent.PURCHASE,
        pending_resolution=PendingResolution.AMBIGUOUS,
    )
    merged = deterministic_merge(prev, facts)
    assert merged.pending_interaction == PendingInteraction.OFFER_ALTERNATIVES
    plan = decide(merged)
    assert plan.action == Action.ASK_INFO
    assert plan.reason_code == "pending_alternatives_clarify"


def test_short_sim_without_pending_does_not_widen() -> None:
    prev = _state(
        pending_interaction=PendingInteraction.NONE,
        last_inventory_outcome=None,
        last_inventory_search_key=None,
    )
    facts = TurnFacts(intent=BusinessIntent.SMALLTALK, facts={})
    merged = deterministic_merge(prev, facts)
    assert merged.alternative_scope == AlternativeScope.NONE
    assert merged.pending_interaction == PendingInteraction.NONE


def test_budget_undefined_skips_reask() -> None:
    prev = _state(
        pending_interaction=PendingInteraction.NONE,
        alternative_scope=AlternativeScope.ANY_VEHICLE,
        budget_status=BudgetStatus.UNDEFINED,
        last_inventory_search_key="abc",
    )
    # Same search key would skip inventory; change nothing else.
    plan = decide(prev)
    assert plan.ask_field != "budget"
    assert plan.reason_code != "need_field" or plan.ask_field != "budget"


def test_budget_undefined_from_turnfacts() -> None:
    prev = _state(pending_interaction=PendingInteraction.NONE)
    facts = TurnFacts(
        intent=BusinessIntent.PURCHASE,
        budget_status=BudgetStatus.UNDEFINED,
    )
    merged = deterministic_merge(prev, facts)
    assert merged.budget_status == BudgetStatus.UNDEFINED
    assert "budget" not in merged.facts or merged.facts.get("budget") is None


def test_later_budget_upgrades_undefined_to_provided() -> None:
    prev = _state(
        pending_interaction=PendingInteraction.NONE,
        budget_status=BudgetStatus.UNDEFINED,
    )
    facts = TurnFacts(
        intent=BusinessIntent.PURCHASE,
        facts={"budget": 80000},
        budget_status=BudgetStatus.PROVIDED,
    )
    merged = deterministic_merge(prev, facts)
    assert merged.budget_status == BudgetStatus.PROVIDED
    assert merged.facts["budget"] == 80000


@pytest.mark.asyncio
async def test_success_empty_sets_pending_affordance(monkeypatch) -> None:
    async def fake_search(pool, req):
        return []

    monkeypatch.setattr("sdr.tools.inventory.search_with_request", fake_search)

    async def understand(text, state):
        return TurnFacts(
            intent=BusinessIntent.PURCHASE,
            facts={"desired_model": "corolla"},
            language="pt-BR",
        )

    state = ConversationCanonicalState(
        thread_id="t",
        customer=CustomerState(phone="1"),
        assistant_turn_count=1,
    )
    result = await process_turn(
        state=state,
        inbound_text="quero ver um corolla",
        understand=understand,
        pool=AsyncMock(),
    )
    assert result.tool_results[0]["outcome"] == "SUCCESS_EMPTY"
    assert result.state.pending_interaction == PendingInteraction.OFFER_ALTERNATIVES
    assert result.response_directive is not None
    assert result.response_directive.conversational_affordance == PendingInteraction.OFFER_ALTERNATIVES
    joined = " ".join(result.outbound_texts).lower()
    assert "alternativ" in joined


@pytest.mark.asyncio
async def test_title_fallback_success_found_then_any_vehicle(monkeypatch) -> None:
    corolla = InventoryVehicle(
        id="1",
        slug="corolla",
        title="TOYOTA COROLLA GLI",
        brand_name="Toyota",
        model="View",
        type="CAR",
        price_cash=Decimal("90000"),
        mileage=None,
        color=None,
        year_model=2016,
        year_manufacture=2015,
        version=None,
    )
    others = [
        InventoryVehicle(
            id=f"c{i}",
            slug=f"c{i}",
            title=f"Car {i}",
            brand_name="X",
            model=f"M{i}",
            type="CAR",
            price_cash=Decimal("50000"),
            mileage=None,
            color=None,
            year_model=2018,
            year_manufacture=2017,
            version=None,
        )
        for i in range(3)
    ]

    async def fake_search(pool, req):
        from sdr.tools.inventory import select_ranked_vehicles

        return select_ranked_vehicles([corolla, *others], req)

    monkeypatch.setattr("sdr.tools.inventory.search_with_request", fake_search)

    state = ConversationCanonicalState(
        thread_id="t",
        customer=CustomerState(phone="1"),
        assistant_turn_count=1,
    )

    async def u1(text, st):
        return TurnFacts(
            intent=BusinessIntent.PURCHASE,
            facts={"desired_model": "corolla"},
            language="pt-BR",
        )

    r1 = await process_turn(state=state, inbound_text="corolla", understand=u1, pool=AsyncMock())
    assert r1.tool_results[0]["outcome"] == "SUCCESS_FOUND"
    assert r1.state.facts["desired_model"] == "corolla"
    key1 = r1.state.last_inventory_search_key

    # Simulate empty path: force pending + empty outcome for acceptance flow.
    state2 = r1.state
    state2.last_inventory_outcome = "SUCCESS_EMPTY"
    state2.pending_interaction = PendingInteraction.OFFER_ALTERNATIVES

    async def u2(text, st):
        return TurnFacts(
            intent=BusinessIntent.PURCHASE,
            alternative_scope=AlternativeScope.ANY_VEHICLE,
            pending_resolution=PendingResolution.ACCEPT,
            language="pt-BR",
        )

    r2 = await process_turn(
        state=state2,
        inbound_text="pode mandar qualquer opcao de carro",
        understand=u2,
        pool=AsyncMock(),
    )
    assert r2.state.alternative_scope == AlternativeScope.ANY_VEHICLE
    assert r2.state.facts["desired_model"] == "corolla"
    assert r2.state.pending_interaction == PendingInteraction.NONE
    assert r2.state.last_inventory_search_key != key1
    assert r2.tool_results[0]["outcome"] == "SUCCESS_FOUND"
    joined = " ".join(r2.outbound_texts).lower()
    assert "que legal que você quer um corolla" not in joined
