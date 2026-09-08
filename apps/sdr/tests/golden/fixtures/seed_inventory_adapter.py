"""Deterministic seed inventory adapter for golden scenarios."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

_SEED_FILE = Path(__file__).parent / "seed_inventory.json"
SEED_VERSION = "2026-09-08-v3-phase8"


def seed_sha256() -> str:
    return hashlib.sha256(_SEED_FILE.read_bytes()).hexdigest()


def load_seed() -> list[dict[str, Any]]:
    vehicles = json.loads(_SEED_FILE.read_text())
    try:
        from sdr.domain.vehicle_catalog import register_catalog_vehicles

        register_catalog_vehicles(vehicles)
    except Exception:
        pass
    return vehicles


def _normalize(text: str) -> str:
    return text.lower().strip()


def _vehicle_matches(vehicle: dict[str, Any], model: str, brand: str) -> bool:
    if str(vehicle.get("match_policy") or "") == "id_only":
        return False
    v_model = _normalize(vehicle.get("model") or "")
    v_brand = _normalize(vehicle.get("brand") or "")
    combined = f"{v_brand} {v_model}"
    if model:
        return model in combined
    if brand and brand in v_brand:
        return True
    return False


def get_seed_by_id(vehicle_id: str | None) -> dict[str, Any] | None:
    vid = (vehicle_id or "").strip()
    if not vid:
        return None
    for vehicle in load_seed():
        if vehicle.get("id") == vid:
            return vehicle
    return None


def _resolve_listing(
    vehicles: list[dict[str, Any]],
    *,
    listing_id: str | None,
    listing_url: str | None,
) -> dict[str, Any] | None:
    lid = (listing_id or "").strip()
    url = (listing_url or "").strip()
    if not lid and not url:
        return None
    for v in vehicles:
        if lid and v.get("id") == lid:
            return v
        if url and (v.get("listing_url") == url or lid in url):
            return v
    return None


def search_seed(
    model: str | None = None,
    brand: str | None = None,
    vehicle_hint_id: str | None = None,
    listing_url: str | None = None,
) -> dict[str, Any]:
    """Search seed inventory.

    SUCCESS_SOLD is returned only when an unequivocal listing identity
    (id or URL) resolves to a SOLD row. Brand/model of a silver Civic is
    not enough to claim that specific listing was sold.
    """
    vehicles = load_seed()
    model_q = _normalize(model or "")
    brand_q = _normalize(brand or "")

    listing = _resolve_listing(
        vehicles,
        listing_id=vehicle_hint_id,
        listing_url=listing_url,
    )
    listing_meta = {
        "listing_reference_received": vehicle_hint_id or listing_url,
        "listing_reference_resolved": listing.get("id") if listing else None,
        "matched_inventory_id": listing.get("id") if listing else None,
        "matched_status": listing.get("status") if listing else None,
    }

    if listing is not None:
        if listing.get("status") == "SOLD":
            return {
                "outcome": "SUCCESS_SOLD",
                "vehicle": listing,
                "listing_id": listing.get("id"),
                **listing_meta,
                "inventory_outcome": "SUCCESS_SOLD",
            }
        if listing.get("status") == "PUBLISHED":
            return {
                "outcome": "SUCCESS_FOUND",
                "vehicles": [listing],
                **listing_meta,
                "inventory_outcome": "SUCCESS_FOUND",
            }

    if not model_q and not brand_q:
        published = [
            v
            for v in vehicles
            if v.get("status") == "PUBLISHED" and v.get("match_policy") != "id_only"
        ]
        if published:
            return {
                "outcome": "SUCCESS_FOUND",
                "vehicles": published[:3],
                **listing_meta,
                "inventory_outcome": "SUCCESS_FOUND",
            }
        return {
            "outcome": "SUCCESS_EMPTY",
            "vehicles": [],
            **listing_meta,
            "inventory_outcome": "SUCCESS_EMPTY",
        }

    published = [v for v in vehicles if v.get("status") == "PUBLISHED"]
    published_matches = [v for v in published if _vehicle_matches(v, model_q, brand_q)]
    if published_matches:
        return {
            "outcome": "SUCCESS_FOUND",
            "vehicles": published_matches[:3],
            **listing_meta,
            "inventory_outcome": "SUCCESS_FOUND",
        }

    return {
        "outcome": "SUCCESS_EMPTY",
        "vehicles": [],
        **listing_meta,
        "inventory_outcome": "SUCCESS_EMPTY",
    }


_SYNTHETIC_FIXTURE_BY_ID = {
    "VH-FOX-2014-001": "synthetic_fox",
    "VH-STRADA-2018": "synthetic_strada",
}


def seed_catalog_image_index() -> list[dict[str, Any]]:
    """Exact-match fingerprints for isolated visual lookup (no live pool)."""
    from sdr.domain.image_fingerprint import dhash64, dhash_hex, sha256_hex
    from tests.golden.fixtures.synthetic_media import load_image_fixture

    index: list[dict[str, Any]] = []
    for vehicle_id, fixture in _SYNTHETIC_FIXTURE_BY_ID.items():
        data = load_image_fixture(fixture)
        if not data:
            continue
        vehicle = get_seed_by_id(vehicle_id) or {}
        index.append(
            {
                "vehicle_id": vehicle_id,
                "conversation_id": "catalog",
                "sha256": sha256_hex(data),
                "dhash": dhash_hex(dhash64(data)),
                "model": vehicle.get("model"),
                "brand": vehicle.get("brand"),
                "status": vehicle.get("status") or "PUBLISHED",
            }
        )
    return index


def visual_candidates_from_seed(
    model: str | None = None,
    brand: str | None = None,
) -> list[dict[str, Any]]:
    """Visual candidate set — includes id_only listings (photo is identity)."""
    vehicles = load_seed()
    model_q = _normalize(model or "")
    brand_q = _normalize(brand or "")
    matches: list[dict[str, Any]] = []
    for vehicle in vehicles:
        if str(vehicle.get("status") or "").upper() != "PUBLISHED":
            continue
        v_model = _normalize(vehicle.get("model") or "")
        v_brand = _normalize(vehicle.get("brand") or "")
        combined = f"{v_brand} {v_model}"
        if model_q:
            if model_q in combined:
                matches.append(vehicle)
        elif brand_q and brand_q in v_brand:
            matches.append(vehicle)
    return matches


def inventory_vehicles_from_seed_request(req: Any) -> list[Any]:
    """Adapter for ``search_with_request`` — never calls pool.acquire()."""
    from decimal import Decimal

    from sdr.tools.inventory import InventoryVehicle

    model = getattr(req, "original_model", None) or getattr(req, "original_vehicle_text", None)
    brand = getattr(req, "original_brand", None)
    rows = visual_candidates_from_seed(model=model, brand=brand)
    out: list[Any] = []
    for vehicle in rows:
        price = vehicle.get("priceCash")
        year = vehicle.get("yearModel") or vehicle.get("year_model") or vehicle.get("year")
        out.append(
            InventoryVehicle(
                id=str(vehicle.get("id")),
                slug=str(vehicle.get("slug") or vehicle.get("id") or ""),
                title=str(vehicle.get("title") or ""),
                brand_name=str(vehicle.get("brand") or ""),
                model=str(vehicle.get("model") or ""),
                type=str(vehicle.get("type") or "CAR"),
                price_cash=Decimal(str(price)) if price is not None else None,
                mileage=vehicle.get("mileage"),
                color=vehicle.get("color"),
                year_model=int(year) if year is not None else None,
                year_manufacture=int(year) if year is not None else None,
                version=vehicle.get("version"),
                status=str(vehicle.get("status") or "PUBLISHED"),
            )
        )
    return out


def make_seed_inventory_result(query: dict[str, Any]) -> list[dict[str, Any]]:
    model = query.get("model") or query.get("desired_model") or ""
    brand = query.get("brand") or ""
    vehicle_hint_id = query.get("vehicle_hint_id") or query.get("vehicle_id") or query.get("listing_id") or ""
    listing_url = query.get("listing_url") or ""

    result = search_seed(
        model=model,
        brand=brand,
        vehicle_hint_id=vehicle_hint_id or None,
        listing_url=listing_url or None,
    )
    outcome = result.get("outcome", "SUCCESS_EMPTY")
    tool_result: dict[str, Any] = {
        "tool": "inventory_search",
        "outcome": outcome,
        "listing_reference_received": result.get("listing_reference_received"),
        "listing_reference_resolved": result.get("listing_reference_resolved"),
        "matched_inventory_id": result.get("matched_inventory_id"),
        "matched_status": result.get("matched_status"),
        "inventory_outcome": result.get("inventory_outcome"),
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
