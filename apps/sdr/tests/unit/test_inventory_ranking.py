"""Controlled inventory repository — PUBLISHED-only exposure."""

from __future__ import annotations

from decimal import Decimal

from sdr.tools.inventory import InventoryVehicle, rank_alternatives


def _v(
    *,
    id: str,
    brand: str,
    model: str,
    price: float,
    type: str = "CAR",
) -> InventoryVehicle:
    return InventoryVehicle(
        id=id,
        slug=id,
        title=f"{brand} {model}",
        brand_name=brand,
        model=model,
        type=type,
        price_cash=Decimal(str(price)),
        mileage=None,
        color=None,
        year_model=2020,
        year_manufacture=2020,
        version=None,
    )


def test_rank_alternatives_caps_at_three() -> None:
    vehicles = [_v(id=str(i), brand="A", model=f"M{i}", price=10000 + i * 100) for i in range(10)]
    ranked = rank_alternatives(vehicles, budget=10500, limit=3)
    assert len(ranked) == 3


def test_rank_prefers_price_then_type_then_brand() -> None:
    vehicles = [
        _v(id="1", brand="X", model="A", price=50000, type="SUV"),
        _v(id="2", brand="Y", model="B", price=20100, type="CAR"),
        _v(id="3", brand="Pref", model="C", price=20000, type="CAR"),
        _v(id="4", brand="Z", model="D", price=20050, type="SUV"),
    ]
    ranked = rank_alternatives(
        vehicles,
        budget=20000,
        prefer_type="CAR",
        prefer_brand="Pref",
        limit=3,
    )
    assert ranked[0].id == "3"  # closest price + type + brand
    assert len(ranked) == 3


def test_published_filter_contract_documented_in_sql() -> None:
    """search_published_vehicles SQL must filter status=PUBLISHED only."""
    from sdr.tools import inventory as inv

    assert "PUBLISHED" in inv._SEARCH_SQL
    assert 'v."status" = \'PUBLISHED\'' in inv._SEARCH_SQL


def test_inventory_vehicle_missing_fields_not_invented() -> None:
    v = _v(id="1", brand="A", model="B", price=10)
    assert v.mileage is None
    assert v.format_field("mileage") == inv_missing()


def inv_missing() -> str:
    from sdr.tools.inventory import MISSING_FIELD_LABEL

    return MISSING_FIELD_LABEL
