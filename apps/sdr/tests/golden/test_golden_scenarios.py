"""Pytest integration for golden scenarios.

Runs each scenario JSON as a single test, exercising the full pipeline
(without a real DB pool — inventory calls return FAILED_RETRYABLE or
use a pre-configured mock).

Live LLM runs belong to `python -m sdr.replay --llm-real`, not pytest.

To run: uv run pytest tests/golden/ -v
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from sdr.config import get_settings

_SCENARIOS_DIR = Path(__file__).parent / "scenarios"


@pytest.fixture(autouse=True)
def _deterministic_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    os.environ["OPENAI_API_KEY"] = ""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


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
