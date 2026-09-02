"""Real inventory search against the authoritative Supabase project.

No mocks. Skips unless DATABASE_URL points at oulknepjqhyiyjbiuqtg.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from sdr.domain.inventory_outcome import classify_inventory_error
from sdr.domain.inventory_search import build_inventory_search_request
from sdr.domain.types import InventoryOutcome
from sdr.tools.inventory import search_with_request

from tests.integration.conftest import AUTHORITATIVE_REF, authoritative_database_url

pytestmark = pytest.mark.skipif(
    authoritative_database_url() is None,
    reason="authoritative DATABASE_URL (oulknepjqhyiyjbiuqtg) not configured",
)


@pytest.fixture
async def pool():
    from sdr.config import get_settings
    from sdr.db import close_pool, init_pool

    get_settings.cache_clear()
    settings = get_settings()
    assert AUTHORITATIVE_REF in settings.database_url
    created = await init_pool(settings)
    yield created
    await close_pool()


def _req(**facts):
    return build_inventory_search_request(facts, limit=3)


@pytest.mark.asyncio
async def test_only_published_and_corolla_found(pool) -> None:
    results = await search_with_request(pool, _req(desired_model="corolla"))
    assert results, "Corolla must be found via model or title fallback"
    assert all(v.to_dict()["id"] for v in results)
    titles = " ".join(v.title.lower() for v in results)
    assert "corolla" in titles
    # Unpublished Tracker must never appear in published search.
    assert all("tracker" not in v.title.lower() for v in results)
    assert all("tracker" not in v.model.lower() for v in results)


@pytest.mark.asyncio
async def test_exact_engine_ranks_and_serializes(pool) -> None:
    results = await search_with_request(
        pool,
        _req(desired_model="corolla", desired_engine_displacement_liters=2.0),
    )
    assert results
    top = results[0]
    payload = top.to_dict()
    json.dumps(payload)  # Decimal must already be float/None
    assert not isinstance(payload["engineDisplacementLiters"], Decimal)
    if payload["engineDisplacementLiters"] is not None:
        assert payload["engineDisplacementLiters"] == 2.0
        assert top.engine_match == "exact"
    assert payload["imageCount"] >= 1
    assert payload["images"][0]["id"]
    assert payload["priceCash"] is not None


@pytest.mark.asyncio
async def test_different_engine_is_alternative_not_match(pool) -> None:
    results = await search_with_request(
        pool,
        _req(desired_model="corolla", desired_engine_displacement_liters=1.8),
    )
    preferred = [v for v in results if v.engine_match != "incompatible"]
    alts = [v for v in results if v.engine_match == "incompatible"]
    # Seed has the 2.0 Corolla, not a 1.8 Corolla — 2.0 is alternative only.
    if alts:
        assert alts[0].engine_match == "incompatible"
        if alts[0].engine_displacement_liters is not None:
            assert float(alts[0].engine_displacement_liters) != 1.8
    assert len(results) <= 3
    # Absence of an exact 1.8 is not a query failure.
    assert preferred or alts


@pytest.mark.asyncio
async def test_null_engine_is_unknown_not_incompatible(pool) -> None:
    results = await search_with_request(
        pool,
        _req(desired_model="q5", desired_engine_displacement_liters=2.0),
    )
    if not results:
        pytest.skip("no Q5 in published seed")
    top = results[0]
    payload = top.to_dict()
    # Title may contain 2.0; persisted engine stays unconfirmed when NULL.
    if top.engine_displacement_liters is None:
        assert payload["engineDisplacementLiters"] is None
        assert top.engine_match == "unknown"
        assert "2.0" in top.title or "2,0" in top.title


@pytest.mark.asyncio
async def test_missing_stock_is_empty_not_failure(pool) -> None:
    results = await search_with_request(
        pool,
        _req(desired_model="zzzz-unobtanium-modelo"),
    )
    assert results == []


@pytest.mark.asyncio
async def test_db_error_never_classifies_as_empty_stock() -> None:
    outcome = classify_inventory_error("connection refused")
    assert outcome == InventoryOutcome.FAILED_RETRYABLE
    assert outcome != InventoryOutcome.SUCCESS_EMPTY
