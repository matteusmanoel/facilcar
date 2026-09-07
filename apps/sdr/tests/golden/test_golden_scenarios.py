"""Pytest integration for golden scenarios.

Runs each scenario JSON as a single test, exercising the full pipeline
(without a real DB pool — inventory calls return FAILED_RETRYABLE or
use a pre-configured mock).

To run: uv run pytest tests/golden/ -v
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.golden.invariants import check_turn

_SCENARIOS_DIR = Path(__file__).parent / "scenarios"


def _scenario_ids():
    return [p.stem for p in sorted(_SCENARIOS_DIR.glob("*.json"))]


def _load(name: str) -> dict:
    return json.loads((_SCENARIOS_DIR / f"{name}.json").read_text())


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario_name", _scenario_ids())
async def test_golden_scenario(scenario_name: str) -> None:
    """Run golden scenario through the full pipeline (no real DB pool)."""
    from sdr.replay.runner import run_scenario

    scenario = _load(scenario_name)
    ok, errors = await run_scenario(scenario, show_trace=False, pool=None)
    assert ok, "\n".join(errors)
