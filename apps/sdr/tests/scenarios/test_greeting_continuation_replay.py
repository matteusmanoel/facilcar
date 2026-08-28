"""Replay: greeting then reciprocal smalltalk must not reopen as first contact."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from sdr.config import get_settings
from sdr.replay import run_replay

FIXTURE = str(
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "greeting_then_reciprocal_smalltalk.yaml"
)


@pytest.fixture(autouse=True)
def _clear_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    os.environ["OPENAI_API_KEY"] = ""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_greeting_then_reciprocal_smalltalk_replay() -> None:
    ok = await run_replay(FIXTURE, mode="deterministic")
    assert ok is True
