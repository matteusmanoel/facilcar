"""Phase 9R Frente A — isolated seed visual lookup and quoted Strada reply.

Harness/protocol contracts. Exact Composer copy is not asserted.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdr.domain.commercial_snapshot import build_commercial_snapshot
from sdr.replay.runner import run_scenario_detailed
from tests.golden.fixtures.seed_inventory_adapter import SEED_VERSION, get_seed_by_id

PHASE9 = Path(__file__).resolve().parent / "phase9"
FOX_ID = "VH-FOX-2014-001"
STRADA_2021 = "VH-STRADA-2021"
STRADA_2017 = "VH-STRADA-2017"
STRADA_2018 = "VH-STRADA-2018"
STRADA_IDS = {STRADA_2021, STRADA_2017, STRADA_2018}


class _AcquireForbiddenPool:
    def acquire(self, *args, **kwargs):
        raise AssertionError("isolated seed must not call pool.acquire()")


def _load_phase9(name: str) -> dict:
    return json.loads((PHASE9 / f"{name}.json").read_text(encoding="utf-8"))


def _p9_03_stubbed() -> dict:
    scenario = _load_phase9("p9_03_cumprimento_seguido_de_imagem")
    scenario["turns"][0]["understand_return"] = {"intent": "SMALLTALK", "facts": {}}
    scenario["turns"][1]["understand_return"] = {
        "intent": "PURCHASE",
        "facts": {"desired_model": "Fox", "desired_vehicle_text": "Fox"},
    }
    return scenario


def _p9_05_stubbed() -> dict:
    scenario = _load_phase9("p9_05_reply_strada_2018")
    scenario["turns"][0]["understand_return"] = {
        "intent": "PURCHASE",
        "facts": {"desired_model": "Strada", "desired_vehicle_text": "Strada"},
    }
    scenario["turns"][1]["understand_return"] = {
        "intent": "PURCHASE",
        "facts": {},
    }
    return scenario


def _visual_match_id(result) -> str | None:
    vis = getattr(result.final_state, "last_visual_resolution", None) or {}
    if vis.get("matched_vehicle_id"):
        return vis.get("matched_vehicle_id")
    return getattr(result.final_state, "primary_vehicle_id", None)


@pytest.mark.asyncio
async def test_a1_exact_fox_image_resolves_via_isolated_seed() -> None:
    assert SEED_VERSION
    assert get_seed_by_id(FOX_ID)["model"] == "Fox"
    result = await run_scenario_detailed(
        _p9_03_stubbed(),
        pool=_AcquireForbiddenPool(),
        llm_real=False,
        use_live_inventory=False,
    )
    assert result.inventory_source == "seed_isolated"
    assert _visual_match_id(result) == FOX_ID
    assert result.visual_turns >= 1


@pytest.mark.asyncio
async def test_a4_strada_reply_turn_reaches_runtime() -> None:
    result = await run_scenario_detailed(
        _p9_05_stubbed(),
        pool=_AcquireForbiddenPool(),
        llm_real=False,
        use_live_inventory=False,
    )
    assert len(result.turns) == 2
    assert result.runtime_calls == 2
    assert result.turns[1]["inbound"] == "Gostei dessa opção"


@pytest.mark.asyncio
async def test_a5_reply_resolves_strada_2018() -> None:
    result = await run_scenario_detailed(
        _p9_05_stubbed(),
        pool=_AcquireForbiddenPool(),
        llm_real=False,
        use_live_inventory=False,
    )
    assert result.final_state.primary_vehicle_id == STRADA_2018


@pytest.mark.asyncio
async def test_a6_no_inventory_search_after_quoted_reply() -> None:
    result = await run_scenario_detailed(
        _p9_05_stubbed(),
        pool=_AcquireForbiddenPool(),
        llm_real=False,
        use_live_inventory=False,
    )
    reply_trace = result.traces[1]
    searches = [
        tr for tr in (reply_trace.get("tool_results") or []) if tr.get("tool") == "inventory_search"
    ]
    assert searches == []
    assert (result.turns[1].get("action") or "").upper() != "SHOW_OFFERS"


@pytest.mark.asyncio
async def test_a7_only_strada_2018_is_primary() -> None:
    result = await run_scenario_detailed(
        _p9_05_stubbed(),
        pool=_AcquireForbiddenPool(),
        llm_real=False,
        use_live_inventory=False,
    )
    assert result.final_state.primary_vehicle_id == STRADA_2018
    snap = build_commercial_snapshot(result.final_state)
    primaries = [vid for vid in snap.interest_ids if vid == snap.primary_vehicle_id]
    assert primaries == [STRADA_2018]


@pytest.mark.asyncio
async def test_a8_other_stradas_remain_non_primary() -> None:
    result = await run_scenario_detailed(
        _p9_05_stubbed(),
        pool=_AcquireForbiddenPool(),
        llm_real=False,
        use_live_inventory=False,
    )
    shown = list(result.final_state.last_shown_vehicle_ids or [])
    assert set(shown) == STRADA_IDS
    snap = build_commercial_snapshot(result.final_state)
    interests = [
        {"vehicleId": vid, "isPrimary": vid == snap.primary_vehicle_id}
        for vid in snap.interest_ids
    ]
    assert {row["vehicleId"] for row in interests} == STRADA_IDS
    assert [row["vehicleId"] for row in interests if row["isPrimary"]] == [STRADA_2018]
    assert [row["vehicleId"] for row in interests if not row["isPrimary"]] == [
        vid for vid in snap.interest_ids if vid != STRADA_2018
    ]


@pytest.mark.asyncio
async def test_a9_skipped_principal_event_is_not_technical_pass() -> None:
    scenario = {
        "name": "a9_skipped_principal",
        "turns": [
            {
                "inbound": "Quero mais informações da Strada",
                "understand_return": {
                    "intent": "PURCHASE",
                    "facts": {
                        "desired_model": "Strada",
                        "desired_vehicle_text": "Strada",
                    },
                },
            },
            {
                "inbound": "depois eu falo",
                "expected_primary_vehicle_id": STRADA_2018,
            },
        ],
    }
    result = await run_scenario_detailed(
        scenario,
        pool=_AcquireForbiddenPool(),
        llm_real=False,
        use_live_inventory=False,
    )
    assert len(result.turns) < 2
    assert result.ok is False
    assert result.technical_status != "TECHNICAL_PASS"


def test_a10_p9_05_fixture_declares_quoted_reply_mode() -> None:
    scenario = _load_phase9("p9_05_reply_strada_2018")
    reply = scenario["turns"][1]
    assert reply["quoted_message_id"] == "replay-img-VH-STRADA-2018"
    mode = str(reply.get("response_mode") or reply.get("responds_to_field") or "")
    assert mode in {"vehicle_choice", "quoted_selection", "voluntary_fact"}
