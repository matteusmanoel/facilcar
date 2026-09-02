"""Tests for tool executor — planned tools must execute exactly once.

Invariants:
- execute_tool_calls runs each tool in plan.tool_calls.
- Failures produce error entries, NOT greetings.
- tool_results_to_context correctly maps results to composer context.
- Unknown tools produce error entries (not exceptions).
- Pool=None produces error entries for DB-requiring tools.
"""

from __future__ import annotations

import pytest

from sdr.application.tool_executor import execute_tool_calls, tool_results_to_context
from sdr.domain.types import (
    Action,
    ActionPlan,
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    TurnFacts,
)


def _state(**kwargs) -> ConversationCanonicalState:
    s = ConversationCanonicalState(
        thread_id="t1",
        customer=CustomerState(phone="5511999999999"),
    )
    for k, v in kwargs.items():
        setattr(s, k, v)
    return s


def _plan(tool_names: list[str]) -> ActionPlan:
    return ActionPlan(
        action=Action.SHOW_OFFERS,
        tool_calls=[{"tool": t} for t in tool_names],
    )


@pytest.mark.asyncio
async def test_empty_tool_calls_returns_empty_list() -> None:
    state = _state()
    plan = _plan([])
    results = await execute_tool_calls(plan, state, pool=None)
    assert results == []


@pytest.mark.asyncio
async def test_unknown_tool_produces_error_not_exception() -> None:
    """Unknown tool must not raise; must produce an error entry."""
    state = _state()
    plan = _plan(["nonexistent_tool_xyz"])
    results = await execute_tool_calls(plan, state, pool=None)
    assert len(results) == 1
    assert results[0]["tool"] == "nonexistent_tool_xyz"
    assert "error" in results[0]


@pytest.mark.asyncio
async def test_inventory_without_pool_produces_error_entry() -> None:
    """inventory_search with pool=None must produce error entry, not crash."""
    state = _state(intent=BusinessIntent.PURCHASE, facts={"desired_model": "Hilux"})
    plan = _plan(["inventory_search"])
    results = await execute_tool_calls(plan, state, pool=None)
    assert len(results) == 1
    assert results[0]["tool"] == "inventory_search"
    assert "error" in results[0]


@pytest.mark.asyncio
async def test_send_location_works_without_pool() -> None:
    """send_location does not need DB."""
    state = _state()
    plan = _plan(["send_location"])
    results = await execute_tool_calls(plan, state, pool=None)
    assert len(results) == 1
    assert results[0]["tool"] == "send_location"
    assert "error" not in results[0]


@pytest.mark.asyncio
async def test_register_visit_interest_works_without_pool() -> None:
    """register_visit_interest does not need DB."""
    state = _state()
    plan = _plan(["register_visit_interest"])
    results = await execute_tool_calls(plan, state, pool=None)
    assert len(results) == 1
    assert results[0]["registered"] is True


def test_tool_results_to_context_inventory_found() -> None:
    results = [
        {
            "tool": "inventory_search",
            "found": True,
            "count": 2,
            "vehicles": [
                {"title": "Honda CG 160 2023", "priceCash": 18000.0},
                {"title": "Honda CG 125 2022", "priceCash": 14000.0},
            ],
        }
    ]
    ctx = tool_results_to_context(results)
    assert ctx["inventory_found"] is True
    assert ctx["inventory_count"] == 2
    assert len(ctx["offers"]) == 2


def test_tool_results_to_context_inventory_not_found() -> None:
    results = [
        {
            "tool": "inventory_search",
            "found": False,
            "count": 0,
            "vehicles": [],
            "search_params": {"brand": "Honda", "model": "CG"},
        }
    ]
    ctx = tool_results_to_context(results)
    assert ctx["inventory_found"] is False
    assert ctx["inventory_count"] == 0


def test_tool_results_to_context_with_error() -> None:
    results = [{"tool": "inventory_search", "error": "no_db_pool"}]
    ctx = tool_results_to_context(results)
    assert ctx.get("inventory_outcome") == "FAILED_RETRYABLE"
    assert ctx.get("inventory_search_error") == "no_db_pool"
    assert ctx.get("inventory_found") is None


@pytest.mark.asyncio
async def test_process_turn_executes_tools_from_plan(monkeypatch) -> None:
    """process_turn must actually execute tool_calls from the ActionPlan."""
    from sdr.application.process_turn import process_turn
    from sdr.domain.types import BusinessIntent, TurnFacts

    executed: list[str] = []

    async def _mock_understand(text: str, state: ConversationCanonicalState) -> TurnFacts:
        return TurnFacts(
            intent=BusinessIntent.PURCHASE,
            facts={"desired_model": "CG", "brand": "Honda"},
        )

    # Monkeypatch execute_tool_calls to track calls.
    # NOTE: sdr/application/__init__.py exports `process_turn` as an attribute,
    # shadowing the module reference. Access the real module via sys.modules.
    import sys

    pt_module = sys.modules["sdr.application.process_turn"]

    original_execute = pt_module.execute_tool_calls  # noqa: F841

    async def _tracking_execute(plan, state, pool=None):
        for tc in plan.tool_calls:
            executed.append(tc.get("tool", ""))
        return [{"tool": t, "error": "no_db_pool"} for t in executed]

    monkeypatch.setattr(pt_module, "execute_tool_calls", _tracking_execute)

    state = ConversationCanonicalState(
        thread_id="test-tool-exec",
        customer=CustomerState(phone="5511999999999"),
        intent=BusinessIntent.UNKNOWN,
    )

    result = await process_turn(
        state=state,
        inbound_text="Tem Honda CG?",
        understand=_mock_understand,
        pool=None,
    )

    # The decision engine should have planned inventory_search for known model.
    # Verify tools were actually called (tracked by monkeypatch).
    assert "inventory_search" in executed, (
        f"inventory_search was not executed. Executed: {executed}. "
        f"Plan action: {result.action_plan.action}, "
        f"Plan tool_calls: {result.action_plan.tool_calls}"
    )
