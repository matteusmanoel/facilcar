"""Unit tests for inventory tool (PUBLISHED-only, ranking, no fabrication)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from sdr.tools.inventory import (
    MISSING_FIELD_LABEL,
    InventoryVehicle,
    _SEARCH_SQL,
    rank_alternatives,
    search_published_vehicles,
)


def _vehicle(**overrides: Any) -> InventoryVehicle:
    base = dict(
        id="v1",
        slug="toyota-corolla",
        title="Toyota Corolla",
        brand_name="Toyota",
        model="Corolla",
        type="CAR",
        price_cash=Decimal("90000"),
        mileage=None,
        color=None,
        year_model=2020,
        year_manufacture=2019,
        version=None,
    )
    base.update(overrides)
    return InventoryVehicle(**base)


def test_search_sql_requires_published() -> None:
    assert "status" in _SEARCH_SQL
    assert "'PUBLISHED'" in _SEARCH_SQL
    assert "DRAFT" not in _SEARCH_SQL


def test_search_sql_casts_vehicle_type_enum_to_text() -> None:
    """Postgres enum VehicleType cannot compare directly to text params."""
    assert 'v."type"::text = $5' in _SEARCH_SQL


def test_search_sql_includes_title_fallback() -> None:
    assert 'v."model" ILIKE $2 OR v."title" ILIKE $2' in _SEARCH_SQL


def test_propulsion_token_is_not_sql_vehicle_type() -> None:
    from sdr.tools.inventory import sql_published_vehicle_type

    assert sql_published_vehicle_type("automatico") is None
    assert sql_published_vehicle_type("flex") is None
    assert sql_published_vehicle_type("eletrico") is None
    assert sql_published_vehicle_type("CAR") == "CAR"
    assert sql_published_vehicle_type("motorcycle") == "MOTORCYCLE"


@pytest.mark.asyncio
async def test_published_only() -> None:
    """Query always filters PUBLISHED; mock returns only published rows."""
    published = {
        "id": "pub1",
        "slug": "honda-civic",
        "title": "Honda Civic",
        "model": "Civic",
        "version": None,
        "type": "CAR",
        "priceCash": Decimal("85000"),
        "mileage": 40000,
        "color": "Prata",
        "yearModel": 2019,
        "yearManufacture": 2018,
        "brandName": "Honda",
    }
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[published])
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=conn), __aexit__=AsyncMock()))

    results = await search_published_vehicles(pool, brand="Honda")
    assert len(results) == 1
    assert results[0].id == "pub1"

    sql_arg = conn.fetch.await_args.args[0]
    assert "'PUBLISHED'" in sql_arg
    # Ensure non-published statuses are not accepted by the query itself
    assert "DRAFT" not in sql_arg
    assert "RESERVED" not in sql_arg
    assert "SOLD" not in sql_arg


def test_missing_field_returns_unknown() -> None:
    vehicle = _vehicle(mileage=None, color=None)
    assert vehicle.field("mileage") is None
    assert vehicle.field("color") is None
    assert vehicle.format_field("mileage") == MISSING_FIELD_LABEL
    assert vehicle.format_field("color") == MISSING_FIELD_LABEL
    assert MISSING_FIELD_LABEL == "não consta no anúncio"
    # Must not invent a numeric mileage
    assert vehicle.to_dict()["mileage"] is None
    assert vehicle.to_dict()["color"] is None


def test_max_3_alternatives() -> None:
    vehicles = [
        _vehicle(id=f"v{i}", price_cash=Decimal(str(80000 + i * 1000)))
        for i in range(8)
    ]
    ranked = rank_alternatives(vehicles, budget=82000, limit=10)
    assert len(ranked) == 3


def test_alternative_ranking() -> None:
    """Rank: abs(price−budget), then type match, then brand match."""
    far_price = _vehicle(
        id="far",
        brand_name="Toyota",
        type="CAR",
        price_cash=Decimal("150000"),
    )
    close_wrong_type = _vehicle(
        id="suv",
        brand_name="Toyota",
        type="UTILITY",
        price_cash=Decimal("101000"),
    )
    close_wrong_brand = _vehicle(
        id="honda",
        brand_name="Honda",
        type="CAR",
        price_cash=Decimal("100000"),
    )
    best = _vehicle(
        id="best",
        brand_name="Toyota",
        type="CAR",
        price_cash=Decimal("100000"),
    )
    ranked = rank_alternatives(
        [far_price, close_wrong_type, close_wrong_brand, best],
        budget=100000,
        prefer_type="CAR",
        prefer_brand="Toyota",
    )
    assert [v.id for v in ranked] == ["best", "honda", "suv"]
