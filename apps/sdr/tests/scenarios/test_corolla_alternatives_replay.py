"""Replay: Corolla alternatives + undefined budget (mocked inventory)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from sdr.application.process_turn import process_turn
from sdr.domain.pending_interaction import PendingInteraction
from sdr.domain.types import ConversationCanonicalState, CustomerState
from sdr.replay import _check_turn_assertions, _make_deterministic_understand
from sdr.tools.inventory import InventoryVehicle, select_ranked_vehicles


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.mark.asyncio
async def test_corolla_alternatives_budget_replay(monkeypatch) -> None:
    stock = [
        InventoryVehicle(
            id="corolla",
            slug="corolla",
            title="TOYOTA COROLLA GLI 2.0 AUTOMÁTICO • 2016",
            brand_name="Toyota",
            model="\u200eView",
            type="CAR",
            price_cash=Decimal("90000"),
            mileage=None,
            color=None,
            year_model=2016,
            year_manufacture=2015,
            version=None,
        ),
        InventoryVehicle(
            id="tracker",
            slug="tracker",
            title="CHEVROLET TRACKER LTZ 2014",
            brand_name="Chevrolet",
            model="Tracker",
            type="CAR",
            price_cash=Decimal("55000"),
            mileage=None,
            color=None,
            year_model=2014,
            year_manufacture=2013,
            version=None,
        ),
        InventoryVehicle(
            id="civic",
            slug="civic",
            title="Honda Civic",
            brand_name="Honda",
            model="Civic",
            type="CAR",
            price_cash=Decimal("70000"),
            mileage=None,
            color=None,
            year_model=2019,
            year_manufacture=2018,
            version=None,
        ),
    ]

    async def fake_search(pool, req):
        return select_ranked_vehicles(stock, req)

    monkeypatch.setattr("sdr.tools.inventory.search_with_request", fake_search)

    data = yaml.safe_load((FIXTURES / "corolla_alternatives_budget.yaml").read_text())
    turns = data["turns"]
    understand, _ = _make_deterministic_understand(turns)
    state = ConversationCanonicalState(
        thread_id="corolla-replay",
        customer=CustomerState(phone="554588230845"),
    )

    turn_assertions = {int(ta["turn"]): ta for ta in data.get("turn_assertions") or []}
    customer_turn = 0
    history = []

    for turn in turns:
        if turn.get("role") != "customer":
            continue
        if turn.get("command") == "reset_memory":
            state = ConversationCanonicalState(
                thread_id=state.thread_id,
                customer=state.customer,
            )
            continue

        customer_turn += 1
        coalesce = turn.get("coalesce")
        if isinstance(coalesce, list) and coalesce:
            text = "\n".join(str(p.get("text") or "") for p in coalesce)
        else:
            text = str(turn.get("text") or "")

        before = state
        result = await process_turn(
            state=state,
            inbound_text=text,
            understand=understand,
            pool=object(),  # truthy pool
        )
        if result.outbound_texts:
            result.state.assistant_turn_count = state.assistant_turn_count + 1
        state = result.state

        # Coalesced batch → exactly one ActionPlan / outbound batch (not per bubble).
        if coalesce:
            assert len(result.outbound_texts) >= 1
            assert result.action_plan is not None

        ta = turn_assertions.get(customer_turn)
        if ta:
            failures = _check_turn_assertions(customer_turn, ta, result, before)
            assert not failures, failures

        history.append(result)

    # Coalesce turn found Corolla via title fallback.
    coalesce_result = history[1]
    assert coalesce_result.tool_results[0]["outcome"] == "SUCCESS_FOUND"
    assert any(
        "COROLLA" in (v.get("title") or "").upper()
        for v in coalesce_result.tool_results[0]["vehicles"]
    )

    # After ANY_VEHICLE + UNDEFINED — preference preserved, no pending left hanging.
    assert state.facts.get("desired_model") == "corolla"
    assert state.alternative_scope.value == "ANY_VEHICLE"
    assert state.budget_status.value == "UNDEFINED"
    assert state.pending_interaction == PendingInteraction.NONE
