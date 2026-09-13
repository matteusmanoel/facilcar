"""Inventory truth contract — tool failure must never become stock absence."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from sdr.application.process_turn import process_turn
from sdr.application.tool_executor import execute_tool_calls, tool_results_to_context
from sdr.domain.decision import decide, inventory_search_key
from sdr.domain.inventory_outcome import (
    contains_absence_claim,
    inventory_fallback_bubbles,
    inventory_result,
)
from sdr.domain.types import (
    Action,
    ActionPlan,
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    InventoryOutcome,
    TurnFacts,
)
from sdr.understanding.validator import validate_inventory_policy


def _state(**kwargs) -> ConversationCanonicalState:
    base = ConversationCanonicalState(
        thread_id="t1",
        customer=CustomerState(phone="5511999999999"),
        intent=BusinessIntent.PURCHASE,
        facts={"desired_vehicle_text": "qualquer veículo", "budget": 15000},
        assistant_turn_count=1,
    )
    for k, v in kwargs.items():
        setattr(base, k, v)
    return base


async def _fixed_understand(text: str, state: ConversationCanonicalState) -> TurnFacts:
    return TurnFacts(
        intent=BusinessIntent.PURCHASE,
        facts={"desired_vehicle_text": "qualquer veículo", "budget": 15000},
    )


@pytest.mark.asyncio
async def test_no_db_pool_is_failed_retryable_not_empty() -> None:
    plan = ActionPlan(
        action=Action.SHOW_OFFERS,
        tool_calls=[{"tool": "inventory_search"}],
    )
    results = await execute_tool_calls(plan, _state(), pool=None)
    assert len(results) == 1
    assert results[0]["outcome"] == InventoryOutcome.FAILED_RETRYABLE.value
    assert results[0]["error_code"] == "no_db_pool"
    assert results[0]["found"] is False
    ctx = tool_results_to_context(results)
    assert ctx["inventory_outcome"] == "FAILED_RETRYABLE"
    assert ctx["inventory_found"] is None  # must NOT be False (empty)


@pytest.mark.asyncio
async def test_process_turn_no_db_pool_does_not_claim_absence() -> None:
    result = await process_turn(
        state=_state(facts={"desired_vehicle_text": "qualquer"}, intent=BusinessIntent.PURCHASE),
        inbound_text="tem disponível?",
        understand=_fixed_understand,
        pool=None,
    )
    assert result.tool_results
    assert result.tool_results[0]["outcome"] == "FAILED_RETRYABLE"
    assert result.response_directive is not None
    assert result.response_directive.inventory_outcome == InventoryOutcome.FAILED_RETRYABLE
    joined = " ".join(result.outbound_texts).lower()
    assert contains_absence_claim(joined) is False
    assert "não consegui consultar" in joined or "estoque agora" in joined
    assert result.state.last_inventory_search_key is None
    assert result.validator_result is not None
    assert result.validator_result.get("pass") is True or result.validator_result.get("fallback_used")


@pytest.mark.asyncio
async def test_validator_rejects_false_absence_after_failure() -> None:
    fake = ["No momento, não temos scooters elétricos disponíveis no estoque."]
    bubbles, meta = validate_inventory_policy(
        fake,
        inventory_outcome=InventoryOutcome.FAILED_RETRYABLE,
    )
    assert meta["pass"] is False
    assert "absence_claim_on_failure" in meta["violations"]
    assert contains_absence_claim(" ".join(bubbles)) is False
    assert "não consegui consultar" in " ".join(bubbles).lower()


@pytest.mark.asyncio
async def test_success_empty_allows_current_stock_absence_not_policy() -> None:
    ok = ["Não encontrei uma opção com esse perfil no estoque atual."]
    bubbles, meta = validate_inventory_policy(ok, inventory_outcome=InventoryOutcome.SUCCESS_EMPTY)
    assert meta["pass"] is True

    bad = ["A FacilCar não trabalha com esse tipo de veículo."]
    bubbles2, meta2 = validate_inventory_policy(
        bad, inventory_outcome=InventoryOutcome.SUCCESS_EMPTY
    )
    assert meta2["pass"] is False
    assert "permanent_policy_claim_on_empty" in meta2["violations"]


@pytest.mark.asyncio
async def test_success_found_updates_search_key(monkeypatch) -> None:
    from sdr.application import tool_executor as te
    from sdr.tools.inventory import InventoryVehicle
    from decimal import Decimal

    vehicle = InventoryVehicle(
        id="1",
        slug="x",
        title="Test Car",
        brand_name="Test",
        model="Model",
        type="CAR",
        price_cash=Decimal("10000"),
        mileage=None,
        color=None,
        year_model=2020,
        year_manufacture=2020,
        version=None,
    )

    async def fake_search(pool, req):
        return [vehicle]

    monkeypatch.setattr("sdr.tools.inventory.search_with_request", fake_search)

    state = _state()
    result = await process_turn(
        state=state,
        inbound_text="quero ver",
        understand=_fixed_understand,
        pool=AsyncMock(),  # truthy pool
    )
    assert result.tool_results[0]["outcome"] == "SUCCESS_FOUND"
    assert result.state.last_inventory_search_key is not None
    assert result.state.last_inventory_outcome == "SUCCESS_FOUND"
    joined = " ".join(result.outbound_texts).lower()
    assert "encontrei" not in joined
    assert "olha o que" not in joined
    assert "orçamento" not in joined and "orcamento" not in joined


@pytest.mark.asyncio
async def test_success_empty_updates_key_and_distinct_message(monkeypatch) -> None:
    async def fake_search(pool, req):
        return []

    monkeypatch.setattr("sdr.tools.inventory.search_with_request", fake_search)

    result = await process_turn(
        state=_state(),
        inbound_text="tem?",
        understand=_fixed_understand,
        pool=AsyncMock(),
    )
    assert result.tool_results[0]["outcome"] == "SUCCESS_EMPTY"
    assert result.state.last_inventory_search_key is not None
    assert result.state.last_inventory_outcome == "SUCCESS_EMPTY"
    joined = " ".join(result.outbound_texts).lower()
    assert "estoque" in joined  # new copy uses "em estoque" / "estoque atual"
    assert "não consegui consultar" not in joined
    assert "não trabalhamos" not in joined
    # New contract: directly asks for alternatives, no yes/no gate
    assert "quer que eu veja" not in joined
    assert "quer ver alternativas" not in joined


@pytest.mark.asyncio
async def test_timeout_is_failed_retryable_no_key_update(monkeypatch) -> None:
    async def boom(pool, req):
        raise TimeoutError("timed out")

    monkeypatch.setattr("sdr.tools.inventory.search_with_request", boom)

    result = await process_turn(
        state=_state(),
        inbound_text="tem?",
        understand=_fixed_understand,
        pool=AsyncMock(),
    )
    assert result.tool_results[0]["outcome"] == "FAILED_RETRYABLE"
    assert result.state.last_inventory_search_key is None
    assert contains_absence_claim(" ".join(result.outbound_texts)) is False


@pytest.mark.asyncio
async def test_malformed_result_is_failed_terminal(monkeypatch) -> None:
    async def bad(pool, req):
        return "not-a-list"  # type: ignore[return-value]

    monkeypatch.setattr("sdr.tools.inventory.search_with_request", bad)

    result = await process_turn(
        state=_state(),
        inbound_text="tem?",
        understand=_fixed_understand,
        pool=AsyncMock(),
    )
    assert result.tool_results[0]["outcome"] == "FAILED_TERMINAL"
    assert result.state.last_inventory_search_key is None


def test_same_key_prevents_research_after_success() -> None:
    facts = {"desired_vehicle_text": "x", "budget": 10000}
    key = inventory_search_key(facts)
    state = _state(facts=facts, last_inventory_search_key=key, last_inventory_outcome="SUCCESS_EMPTY")
    plan = decide(state)
    assert not any(tc.get("tool") == "inventory_search" for tc in plan.tool_calls)


def test_changed_criteria_allow_research() -> None:
    old_key = inventory_search_key({"desired_vehicle_text": "a", "budget": 10000})
    state = _state(
        facts={"desired_vehicle_text": "b", "budget": 20000},
        last_inventory_search_key=old_key,
    )
    plan = decide(state)
    assert plan.action == Action.SHOW_OFFERS
    assert any(tc.get("tool") == "inventory_search" for tc in plan.tool_calls)


def test_fallback_bubbles_never_claim_absence() -> None:
    for outcome in (
        InventoryOutcome.FAILED_RETRYABLE,
        InventoryOutcome.FAILED_TERMINAL,
    ):
        text = " ".join(inventory_fallback_bubbles(outcome))
        assert contains_absence_claim(text) is False
