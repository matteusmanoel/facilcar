"""SUCCESS_SOLD requires unequivocal listing identity."""

from __future__ import annotations

from tests.golden.fixtures.seed_inventory_adapter import search_seed


def test_sold_civic_requires_listing_id() -> None:
    by_model = search_seed(model="Honda Civic", brand="Honda")
    assert by_model["outcome"] != "SUCCESS_SOLD"

    by_id = search_seed(
        model="Honda Civic",
        brand="Honda",
        vehicle_hint_id="VH-SOLD-CIVIC-001",
    )
    assert by_id["outcome"] == "SUCCESS_SOLD"
    assert by_id["listing_reference_resolved"] == "VH-SOLD-CIVIC-001"
    assert by_id["matched_inventory_id"] == "VH-SOLD-CIVIC-001"
    assert by_id["matched_status"] == "SOLD"


def test_unknown_listing_is_unspecified_unavailability() -> None:
    result = search_seed(
        model="Honda Civic",
        vehicle_hint_id="VH-UNKNOWN-999",
    )
    assert result["outcome"] == "SUCCESS_EMPTY"
    assert result["listing_reference_resolved"] is None
