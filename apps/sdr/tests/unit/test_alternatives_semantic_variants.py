"""Semantic variants: similar accept, any+budget, flexible budget, reject, short sim."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from sdr.application.process_turn import process_turn
from sdr.domain.budget_status import BudgetStatus
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
from sdr.tools.inventory import InventoryVehicle, select_ranked_vehicles


def _cars() -> list[InventoryVehicle]:
    return [
        InventoryVehicle(
            id="corolla",
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
        ),
        InventoryVehicle(
            id="a",
            slug="a",
            title="Honda Civic",
            brand_name="Honda",
            model="Civic",
            type="CAR",
            price_cash=Decimal("70000"),
            mileage=None,
            color=None,
            year_model=2018,
            year_manufacture=2017,
            version=None,
        ),
        InventoryVehicle(
            id="b",
            slug="b",
            title="VW Golf",
            brand_name="Volkswagen",
            model="Golf",
            type="CAR",
            price_cash=Decimal("65000"),
            mileage=None,
            color=None,
            year_model=2017,
            year_manufacture=2016,
            version=None,
        ),
    ]


@pytest.fixture
def pool_and_search(monkeypatch):
    async def fake_search(pool, req):
        return select_ranked_vehicles(_cars(), req)

    monkeypatch.setattr("sdr.tools.inventory.search_with_request", fake_search)
    return AsyncMock()


def _base(**kwargs) -> ConversationCanonicalState:
    s = ConversationCanonicalState(
        thread_id="t",
        customer=CustomerState(phone="1"),
        intent=BusinessIntent.PURCHASE,
        facts={"desired_model": "corolla"},
        assistant_turn_count=2,
        last_inventory_search_key="keynone1",
        last_inventory_outcome="SUCCESS_EMPTY",
        pending_interaction=PendingInteraction.OFFER_ALTERNATIVES,
    )
    for k, v in kwargs.items():
        setattr(s, k, v)
    return s


@pytest.mark.asyncio
async def test_accept_similar_model(pool_and_search) -> None:
    async def understand(text, state):
        return TurnFacts(
            intent=BusinessIntent.PURCHASE,
            pending_resolution=PendingResolution.ACCEPT,
            alternative_scope=AlternativeScope.SIMILAR,
        )

    r = await process_turn(
        state=_base(),
        inbound_text="pode ser um modelo parecido",
        understand=understand,
        pool=pool_and_search,
    )
    assert r.state.alternative_scope == AlternativeScope.SIMILAR
    assert r.state.facts["desired_model"] == "corolla"
    assert r.action_plan.action == Action.SHOW_OFFERS
    assert r.tool_results[0]["outcome"] == "SUCCESS_FOUND"


@pytest.mark.asyncio
async def test_any_brand_keeps_budget(pool_and_search) -> None:
    state = _base(
        budget_status=BudgetStatus.PROVIDED,
        facts={"desired_model": "corolla", "budget": 80000},
    )

    async def understand(text, st):
        return TurnFacts(
            intent=BusinessIntent.PURCHASE,
            pending_resolution=PendingResolution.ACCEPT,
            alternative_scope=AlternativeScope.ANY_VEHICLE,
        )

    r = await process_turn(
        state=state,
        inbound_text="qualquer marca serve",
        understand=understand,
        pool=pool_and_search,
    )
    assert r.state.budget_status == BudgetStatus.PROVIDED
    assert r.state.facts["budget"] == 80000
    assert r.state.alternative_scope == AlternativeScope.ANY_VEHICLE


@pytest.mark.asyncio
async def test_keep_model_flexible_budget(pool_and_search) -> None:
    state = _base(
        pending_interaction=PendingInteraction.NONE,
        last_inventory_search_key=None,
        last_inventory_outcome=None,
    )

    async def understand(text, st):
        return TurnFacts(
            intent=BusinessIntent.PURCHASE,
            facts={"desired_model": "corolla"},
            budget_status=BudgetStatus.FLEXIBLE,
        )

    r = await process_turn(
        state=state,
        inbound_text="quero corolla, faixa flexivel",
        understand=understand,
        pool=pool_and_search,
    )
    assert r.state.budget_status == BudgetStatus.FLEXIBLE
    assert r.state.facts["desired_model"] == "corolla"
    assert r.action_plan.action == Action.SHOW_OFFERS


@pytest.mark.asyncio
async def test_reject_alternatives_asks_budget(pool_and_search) -> None:
    from sdr.domain.inventory_search import inventory_search_key

    state = _base()
    state.last_inventory_search_key = inventory_search_key(
        state.facts,
        alternative_scope=state.alternative_scope,
        budget_status=state.budget_status,
    )

    async def understand(text, st):
        return TurnFacts(
            intent=BusinessIntent.PURCHASE,
            pending_resolution=PendingResolution.REJECT,
        )

    r = await process_turn(
        state=state,
        inbound_text="nao, so o corolla mesmo",
        understand=understand,
        pool=pool_and_search,
    )
    assert r.state.pending_interaction == PendingInteraction.NONE
    assert r.state.alternative_scope == AlternativeScope.NONE
    assert r.action_plan.action == Action.ASK_INFO
    assert r.action_plan.ask_field == "payment_method"


@pytest.mark.asyncio
async def test_undefined_budget_no_reask(pool_and_search) -> None:
    from sdr.domain.inventory_search import inventory_search_key

    state = _base(
        pending_interaction=PendingInteraction.NONE,
        alternative_scope=AlternativeScope.ANY_VEHICLE,
    )
    # Pre-set key for UNKNOWN; UNDEFINED will change key → may re-search (OK),
    # but must not ask budget.
    state.last_inventory_search_key = inventory_search_key(
        state.facts,
        alternative_scope=AlternativeScope.ANY_VEHICLE,
        budget_status=BudgetStatus.UNKNOWN,
    )

    async def understand(text, st):
        return TurnFacts(
            intent=BusinessIntent.PURCHASE,
            budget_status=BudgetStatus.UNDEFINED,
        )

    r = await process_turn(
        state=state,
        inbound_text="ainda nao defini orcamento",
        understand=understand,
        pool=pool_and_search,
    )
    assert r.state.budget_status == BudgetStatus.UNDEFINED
    joined = " ".join(r.outbound_texts).lower()
    assert "orçamento" not in joined and "orcamento" not in joined
    assert r.action_plan.ask_field != "budget"


@pytest.mark.asyncio
async def test_declined_budget(pool_and_search) -> None:
    state = _base(
        pending_interaction=PendingInteraction.NONE,
        alternative_scope=AlternativeScope.ANY_VEHICLE,
        last_inventory_search_key="prevkey2",
    )

    async def understand(text, st):
        return TurnFacts(
            intent=BusinessIntent.PURCHASE,
            budget_status=BudgetStatus.DECLINED,
        )

    r = await process_turn(
        state=state,
        inbound_text="prefiro nao informar o valor",
        understand=understand,
        pool=pool_and_search,
    )
    assert r.state.budget_status == BudgetStatus.DECLINED
    assert r.action_plan.ask_field != "budget"


@pytest.mark.asyncio
async def test_later_defines_value(pool_and_search) -> None:
    state = _base(
        pending_interaction=PendingInteraction.NONE,
        alternative_scope=AlternativeScope.ANY_VEHICLE,
        budget_status=BudgetStatus.UNDEFINED,
        last_inventory_search_key="prevkey3",
    )

    async def understand(text, st):
        return TurnFacts(
            intent=BusinessIntent.PURCHASE,
            facts={"budget": 100000},
            budget_status=BudgetStatus.PROVIDED,
        )

    r = await process_turn(
        state=state,
        inbound_text="na verdade ate 100 mil",
        understand=understand,
        pool=pool_and_search,
    )
    assert r.state.budget_status == BudgetStatus.PROVIDED
    assert r.state.facts["budget"] == 100000


@pytest.mark.asyncio
async def test_short_sim_with_pending_accepts(pool_and_search) -> None:
    async def understand(text, st):
        return TurnFacts(
            intent=BusinessIntent.PURCHASE,
            pending_resolution=PendingResolution.ACCEPT,
        )

    r = await process_turn(
        state=_base(),
        inbound_text="sim",
        understand=understand,
        pool=pool_and_search,
    )
    assert r.state.alternative_scope == AlternativeScope.SIMILAR
    assert r.state.pending_interaction == PendingInteraction.NONE
    assert r.action_plan.action == Action.SHOW_OFFERS


@pytest.mark.asyncio
async def test_short_sim_without_pending_does_not_invent_accept(pool_and_search) -> None:
    from sdr.domain.inventory_search import inventory_search_key

    state = _base(
        pending_interaction=PendingInteraction.NONE,
        last_inventory_outcome="SUCCESS_FOUND",
        alternative_scope=AlternativeScope.NONE,
        budget_status=BudgetStatus.UNKNOWN,
    )
    state.last_inventory_search_key = inventory_search_key(
        state.facts,
        alternative_scope=state.alternative_scope,
        budget_status=state.budget_status,
    )
    key_before = state.last_inventory_search_key

    async def understand(text, st):
        # No pending_resolution — short "sim" alone must not widen.
        return TurnFacts(intent=BusinessIntent.PURCHASE)

    r = await process_turn(
        state=state,
        inbound_text="sim",
        understand=understand,
        pool=pool_and_search,
    )
    assert r.state.alternative_scope == AlternativeScope.NONE
    assert r.action_plan.action != Action.SHOW_OFFERS
    assert r.state.last_inventory_search_key == key_before
