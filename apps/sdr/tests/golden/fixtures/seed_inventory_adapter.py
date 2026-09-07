"""Deterministic seed inventory adapter for golden scenarios.

Replaces live DB calls with a controlled, versioned seed fixture.
Implements the same outcome contract as the real inventory tool.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_SEED_FILE = Path(__file__).parent / "seed_inventory.json"


def load_seed() -> list[dict[str, Any]]:
    """Load the seed vehicle list."""
    return json.loads(_SEED_FILE.read_text())


def _normalize(text: str) -> str:
    return text.lower().strip()


def _vehicle_matches(vehicle: dict[str, Any], model: str, brand: str) -> bool:
    """Return True when vehicle matches the query model or brand (partial, case-insensitive).

    Priority rule: if model was provided, model MUST match (checked against
    "brand model" combined string).  Brand-only fallback is only applied when
    no model was specified.  This prevents "Gol" + "Volkswagen" from matching
    a VW Polo because they share the same brand.
    """
    v_model = _normalize(vehicle.get("model") or "")
    v_brand = _normalize(vehicle.get("brand") or "")
    combined = f"{v_brand} {v_model}"
    if model:
        # Model must appear somewhere in "brand model" string.
        return model in combined
    # Brand-only fallback — only when no model was requested.
    if brand and brand in v_brand:
        return True
    return False


def search_seed(
    model: str | None = None,
    brand: str | None = None,
    vehicle_hint_id: str | None = None,
) -> dict[str, Any]:
    """Search seed inventory with the same outcome contract as the real tool.

    Returns:
        {"outcome": "SUCCESS_FOUND", "vehicles": [...]}
        {"outcome": "SUCCESS_SOLD", "vehicle": {...}, "listing_id": "..."}
        {"outcome": "SUCCESS_EMPTY", "vehicles": []}
    """
    vehicles = load_seed()
    model_q = _normalize(model or "")
    brand_q = _normalize(brand or "")

    # Direct hint match (for scenarios that specify a vehicle ID).
    if vehicle_hint_id:
        for v in vehicles:
            if v.get("id") == vehicle_hint_id:
                if v.get("status") == "SOLD":
                    return {
                        "outcome": "SUCCESS_SOLD",
                        "vehicle": v,
                        "listing_id": v.get("id"),
                    }
                elif v.get("status") == "PUBLISHED":
                    return {"outcome": "SUCCESS_FOUND", "vehicles": [v]}

    # If no query terms, return all published.
    if not model_q and not brand_q:
        published = [v for v in vehicles if v.get("status") == "PUBLISHED"]
        if published:
            return {"outcome": "SUCCESS_FOUND", "vehicles": published[:3]}
        return {"outcome": "SUCCESS_EMPTY", "vehicles": []}

    # Split search: PUBLISHED matches first, then SOLD.
    published = [v for v in vehicles if v.get("status") == "PUBLISHED"]
    sold = [v for v in vehicles if v.get("status") == "SOLD"]

    published_matches = [v for v in published if _vehicle_matches(v, model_q, brand_q)]
    if published_matches:
        return {"outcome": "SUCCESS_FOUND", "vehicles": published_matches[:3]}

    # No published match — check if a sold vehicle matches.
    sold_matches = [v for v in sold if _vehicle_matches(v, model_q, brand_q)]
    if sold_matches:
        sold_v = sold_matches[0]
        return {
            "outcome": "SUCCESS_SOLD",
            "vehicle": sold_v,
            "listing_id": sold_v.get("id"),
        }

    return {"outcome": "SUCCESS_EMPTY", "vehicles": []}


def make_seed_inventory_result(query: dict[str, Any]) -> list[dict[str, Any]]:
    """Return a list[dict] compatible with process_turn tool_results format.

    Extracts model/brand/hint from the search request dict and returns
    a tool_results entry that the runner injects instead of calling the real DB.
    """
    model = query.get("model") or query.get("desired_model") or ""
    brand = query.get("brand") or ""
    vehicle_hint_id = query.get("vehicle_hint_id") or query.get("vehicle_id") or ""

    result = search_seed(model=model, brand=brand, vehicle_hint_id=vehicle_hint_id or None)
    outcome = result.get("outcome", "SUCCESS_EMPTY")

    tool_result: dict[str, Any] = {
        "tool": "inventory_search",
        "outcome": outcome,
    }

    if outcome == "SUCCESS_FOUND":
        vehicles = result.get("vehicles") or []
        tool_result["vehicles"] = vehicles
        tool_result["count"] = len(vehicles)
    elif outcome == "SUCCESS_SOLD":
        vehicle = result.get("vehicle") or {}
        tool_result["vehicles"] = [vehicle]
        tool_result["sold_vehicle"] = vehicle
        tool_result["listing_id"] = result.get("listing_id")
        tool_result["count"] = 0
    else:
        tool_result["vehicles"] = []
        tool_result["count"] = 0

    return [tool_result]
