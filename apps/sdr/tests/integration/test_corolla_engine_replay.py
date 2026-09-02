"""Conversational replay against authoritative published stock."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.integration.conftest import authoritative_database_url

pytestmark = pytest.mark.skipif(
    authoritative_database_url() is None,
    reason="authoritative DATABASE_URL (oulknepjqhyiyjbiuqtg) not configured",
)

FIXTURE = "corolla_engine_displacement"


@pytest.mark.asyncio
async def test_corolla_engine_replay_with_remote_stock() -> None:
    from sdr.replay import run_replay

    ok = await run_replay(FIXTURE, mode="deterministic", with_db=True)
    assert ok, "corolla engine displacement replay failed against remote stock"


def test_fixture_exists() -> None:
    path = Path(__file__).resolve().parents[1] / "fixtures" / f"{FIXTURE}.yaml"
    assert path.is_file()
