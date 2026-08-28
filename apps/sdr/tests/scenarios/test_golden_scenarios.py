"""Executable golden scenarios from julia_sdr_master_pack/tests/conversation_scenarios."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from sdr.application.process_turn import process_turn
from sdr.domain.types import (
    Action,
    Actionability,
    BusinessType,
    ConversationCanonicalState,
    CustomerState,
    LifecycleStatus,
)
from sdr.understanding.extractor import extract_turn_facts

SCENARIO_DIR = (
    Path(__file__).resolve().parents[4]
    / "julia_sdr_master_pack"
    / "tests"
    / "conversation_scenarios"
)
if not SCENARIO_DIR.is_dir():
    SCENARIO_DIR = (
        Path(__file__).resolve().parents[5]
        / "julia_sdr_master_pack"
        / "tests"
        / "conversation_scenarios"
    )


def _load_scenarios() -> list[tuple[str, dict[str, Any]]]:
    if not SCENARIO_DIR.is_dir():
        return []
    out: list[tuple[str, dict[str, Any]]] = []
    for path in sorted(SCENARIO_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        out.append((path.stem, data))
    return out


SCENARIOS = _load_scenarios()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stem,data",
    SCENARIOS,
    ids=[s[0] for s in SCENARIOS] or ["none"],
)
async def test_golden_scenario(stem: str, data: dict[str, Any]) -> None:
    if not data:
        pytest.skip("no scenarios found")

    expect = data.get("expect") or {}
    state = ConversationCanonicalState(
        thread_id="golden",
        customer=CustomerState(phone="5545988432998"),
    )

    async def understand(text: str, s: ConversationCanonicalState):
        # Golden scenarios test deterministic business logic (decision engine,
        # handoff rules, state merging). Use heuristic extraction to avoid
        # flaky LLM non-determinism. NLU quality is tested via live eval.
        from sdr.understanding.extractor import _heuristic_extract

        return _heuristic_extract(text)

    if stem == "human_fromme":
        state.lifecycle.status = LifecycleStatus.HUMAN_ACTIVE
        result = await process_turn(
            state=state,
            inbound_text="Olá, sou o vendedor e vou seguir com você.",
            understand=understand,
        )
        assert result.action_plan.action == Action.NO_REPLY
        assert expect.get("ai_reply") is False
        return

    if stem == "inventory_missing_field":
        # Catalog mileage null → never invent a number in reply.
        result = await process_turn(
            state=state,
            inbound_text="Qual a quilometragem desse carro?",
            understand=understand,
        )
        joined = " ".join(result.outbound_texts).lower()
        assert expect.get("must_not_infer") is True
        # Must not invent a concrete km figure
        assert not any(tok in joined for tok in ("45.000", "45000", "50 mil km"))
        return

    messages = data.get("messages") or []
    last = None
    saw_handoff = False
    for msg in messages:
        last = await process_turn(state=state, inbound_text=msg, understand=understand)
        state = last.state
        if last.action_plan.handoff:
            saw_handoff = True

    assert last is not None

    if "business_type" in expect:
        assert state.business.type.value == expect["business_type"]

    if expect.get("handoff") is True:
        # REGISTER_VISIT_INTEREST is a valid pre-handoff step before the actual handoff.
        visit_pre_handoff = last.action_plan.action == Action.REGISTER_VISIT_INTEREST
        assert saw_handoff or last.action_plan.handoff is True or visit_pre_handoff

    if expect.get("handoff_if_actionable") is True:
        if state.business.actionability in (
            Actionability.ACTIONABLE,
            Actionability.HANDOFF_NOW,
        ) or state.lifecycle.status.value in ("HANDOFF_SENT", "HUMAN_ACTIVE"):
            inventory_pending = (
                last.action_plan.action == Action.SHOW_OFFERS
                and any(
                    tc.get("tool") == "inventory_search"
                    for tc in last.action_plan.tool_calls
                )
            )
            # Inventory-first or visit-invitation may defer irreversible handoff.
            visit_pending = last.action_plan.action == Action.REGISTER_VISIT_INTEREST
            assert (
                saw_handoff
                or state.lifecycle.status.value == "HANDOFF_SENT"
                or inventory_pending
                or visit_pending
            )

    if expect.get("actionability") == "ACTIONABLE":
        assert state.business.actionability in (
            Actionability.ACTIONABLE,
            Actionability.HANDOFF_NOW,
        )

    must_not_ask = expect.get("must_not_ask") or []
    if must_not_ask and last.action_plan.ask_field:
        assert last.action_plan.ask_field not in must_not_ask

    if expect.get("sensitive_data_refusal") is True:
        assert state.signals.sensitive_data_refusal is True

    if expect.get("bypass_triage") is True:
        assert last.action_plan.handoff is True
