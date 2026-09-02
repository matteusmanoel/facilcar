"""Resilient inventory ranking — title fallback, PUBLISHED-only, no false empty."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from sdr.domain.budget_status import BudgetStatus
from sdr.domain.inventory_search import (
    build_inventory_search_request,
    inventory_search_key_from_request,
    is_suspicious_model,
)
from sdr.domain.pending_interaction import AlternativeScope
from sdr.tools.inventory import (
    MatchTier,
    InventoryVehicle,
    _SEARCH_SQL,
    select_ranked_vehicles,
    search_published_vehicles,
)


def _v(**overrides: Any) -> InventoryVehicle:
    base = dict(
        id="v1",
        slug="x",
        title="TOYOTA COROLLA GLI 2.0",
        brand_name="Toyota",
        model="Corolla",
        type="CAR",
        price_cash=Decimal("90000"),
        mileage=None,
        color=None,
        year_model=2016,
        year_manufacture=2015,
        version=None,
    )
    base.update(overrides)
    return InventoryVehicle(**base)


def test_suspicious_model_view() -> None:
    assert is_suspicious_model("View") is True
    assert is_suspicious_model("\u200eView") is True
    assert is_suspicious_model("Corolla") is False


# ---------------------------------------------------------------------------
# Accent-fold: normalize_search_token must strip combining marks (NFD)
# ---------------------------------------------------------------------------

def test_normalize_search_token_strips_accents() -> None:
    """normalize_search_token must produce the same token regardless of accents.

    Root contract: user input and DB model field may differ only in diacritics.
    Any mismatch must not fail silently with zero results.
    """
    from sdr.domain.inventory_search import normalize_search_token

    assert normalize_search_token("Santa Fé") == normalize_search_token("Santa Fe")
    assert normalize_search_token("Gol") == normalize_search_token("Gól")
    assert normalize_search_token("Celta") == normalize_search_token("Celtã")
    assert normalize_search_token("HB20") == normalize_search_token("HB20")  # no accent change
    assert normalize_search_token("São Paulo") == normalize_search_token("Sao Paulo")


def test_accent_insensitive_match_santa_fe() -> None:
    """Vehicle with 'Santa Fe' in model matches query 'Santa Fé' (user input with accent)."""
    santa_fe = _v(
        id="santafe",
        brand_name="Hyundai",
        model="Santa Fe",
        title="HYUNDAI SANTA FE 3.3 V6 2019",
    )
    req = build_inventory_search_request({"desired_model": "Santa Fé"})
    ranked = select_ranked_vehicles([santa_fe], req)
    assert len(ranked) == 1, (
        "Santa Fé (with accent) must match Santa Fe (without accent) in the DB. "
        "normalize_search_token must strip combining marks."
    )
    assert ranked[0].id == "santafe"


def test_accent_insensitive_match_inverse() -> None:
    """Vehicle with 'Santa Fé' in model matches query 'Santa Fe' (user input without accent)."""
    santa_fe = _v(
        id="santafe2",
        brand_name="Hyundai",
        model="Santa Fé",  # DB stored with accent
        title="HYUNDAI SANTA FÉ 3.3 V6 2019",
    )
    req = build_inventory_search_request({"desired_model": "Santa Fe"})
    ranked = select_ranked_vehicles([santa_fe], req)
    assert len(ranked) == 1, (
        "DB model 'Santa Fé' must match user query 'Santa Fe'. "
        "normalize_search_token must strip combining marks in both directions."
    )
    assert ranked[0].id == "santafe2"


def test_search_sql_still_requires_published() -> None:
    assert "'PUBLISHED'" in _SEARCH_SQL
    assert 'v."type"::text = $5' in _SEARCH_SQL
    assert 'v."title" ILIKE' in _SEARCH_SQL


def test_title_fallback_finds_corolla_with_bad_model() -> None:
    """Published Corolla with model=View must match via title."""
    bad = _v(id="corolla", model="\u200eView", title="TOYOTA COROLLA GLI 2.0 AUTOMÁTICO • 2016")
    other = _v(id="civic", title="Honda Civic", brand_name="Honda", model="Civic")
    req = build_inventory_search_request(
        {"desired_model": "corolla"},
        alternative_scope=AlternativeScope.NONE,
        budget_status=BudgetStatus.UNKNOWN,
    )
    ranked = select_ranked_vehicles([bad, other], req)
    assert len(ranked) >= 1
    assert ranked[0].id == "corolla"
    assert ranked[0].match_tier == MatchTier.TITLE_MODEL_ONLY


def test_unpublished_never_in_candidates() -> None:
    """select_ranked operates only on already-PUBLISHED candidate rows."""
    # Caller must filter PUBLISHED in SQL; ranking must not invent unpublished.
    published = _v(id="pub", title="TOYOTA COROLLA", model="View")
    req = build_inventory_search_request({"desired_model": "corolla"})
    ranked = select_ranked_vehicles([published], req)
    assert all(v.id == "pub" for v in ranked)


def test_similar_title_token_does_not_outrank_exact() -> None:
    """'Colorado' must not beat a real Corolla title match for query corolla."""
    corolla = _v(id="corolla", model="View", title="TOYOTA COROLLA 2016")
    colorado = _v(
        id="colorado",
        brand_name="Chevrolet",
        model="Colorado",
        title="CHEVROLET COLORADO 2020",
    )
    req = build_inventory_search_request({"desired_model": "corolla"})
    ranked = select_ranked_vehicles([colorado, corolla], req)
    assert ranked[0].id == "corolla"


def test_brand_search_ranks_toyota() -> None:
    toyota = _v(id="t", brand_name="Toyota", model="Corolla", title="TOYOTA COROLLA")
    honda = _v(id="h", brand_name="Honda", model="Civic", title="Honda Civic")
    req = build_inventory_search_request({"brand": "Toyota", "desired_model": "corolla"})
    ranked = select_ranked_vehicles([honda, toyota], req)
    assert ranked[0].id == "t"


def test_true_zero_results() -> None:
    civic = _v(id="h", brand_name="Honda", model="Civic", title="Honda Civic EX")
    req = build_inventory_search_request({"desired_model": "corolla"})
    ranked = select_ranked_vehicles([civic], req)
    assert ranked == []


def test_any_vehicle_scope_returns_alternatives() -> None:
    cars = [
        _v(id=f"c{i}", title=f"Car {i}", model=f"M{i}", price_cash=Decimal(str(50000 + i)))
        for i in range(5)
    ]
    req = build_inventory_search_request(
        {"desired_model": "corolla"},
        alternative_scope=AlternativeScope.ANY_VEHICLE,
        budget_status=BudgetStatus.UNDEFINED,
    )
    ranked = select_ranked_vehicles(cars, req)
    assert 1 <= len(ranked) <= 3


def test_widened_scope_changes_search_key() -> None:
    facts = {"desired_model": "corolla"}
    k1 = inventory_search_key_from_request(
        build_inventory_search_request(facts, alternative_scope=AlternativeScope.NONE)
    )
    k2 = inventory_search_key_from_request(
        build_inventory_search_request(facts, alternative_scope=AlternativeScope.ANY_VEHICLE)
    )
    assert k1 != k2


@pytest.mark.asyncio
async def test_search_published_uses_candidate_sql_published_only() -> None:
    row = {
        "id": "pub1",
        "slug": "toyota-corolla",
        "title": "TOYOTA COROLLA GLI",
        "model": "View",
        "version": None,
        "type": "CAR",
        "priceCash": Decimal("90000"),
        "mileage": None,
        "color": None,
        "yearModel": 2016,
        "yearManufacture": 2015,
        "brandName": "Toyota",
    }
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[row])
    pool = MagicMock()
    pool.acquire = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(),
        )
    )
    results = await search_published_vehicles(pool, model="corolla")
    assert len(results) == 1
    assert results[0].id == "pub1"
    sql_arg = conn.fetch.await_args.args[0]
    assert "'PUBLISHED'" in sql_arg
    assert "DRAFT" not in sql_arg
