"""Brand/model catalog for enrichment and compatibility — not for intent.

Understanding must not use this list to guess commercial intent. It only:
- splits 'Ford Ka' into brand+model;
- fills a missing brand from a known model;
- rejects impossible pairs such as Honda+Corolla.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

# Models that appear in FacilCar stock or in golden conversations.
# Intent classification must never depend on this map.
_MODEL_TO_BRAND: dict[str, str] = {
    "ka": "Ford",
    "ford ka": "Ford",
    "civic": "Honda",
    "corolla": "Toyota",
    "gol": "Volkswagen",
    "fox": "Volkswagen",
    "hb20": "Hyundai",
    "onix": "Chevrolet",
    "onix plus": "Chevrolet",
    "argo": "Fiat",
    "cronos": "Fiat",
    "polo": "Volkswagen",
    "compass": "Jeep",
    "2008": "Peugeot",
    "peugeot 2008": "Peugeot",
}

_KNOWN_BRANDS: tuple[str, ...] = (
    "chevrolet",
    "fiat",
    "ford",
    "honda",
    "hyundai",
    "jeep",
    "peugeot",
    "toyota",
    "volkswagen",
    "vw",
)

_BRAND_CANON = {
    "vw": "Volkswagen",
    "volkswagen": "Volkswagen",
    "chevrolet": "Chevrolet",
    "fiat": "Fiat",
    "ford": "Ford",
    "honda": "Honda",
    "hyundai": "Hyundai",
    "jeep": "Jeep",
    "peugeot": "Peugeot",
    "toyota": "Toyota",
}

# Cadastral snapshot by inventory id — never inferred from list position.
_VEHICLES_BY_ID: dict[str, dict[str, Any]] = {}


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", (text or "").strip().lower())
    return "".join(ch for ch in raw if not unicodedata.combining(ch))


def _norm_key(text: str) -> str:
    return re.sub(r"\s+", " ", _fold(text)).strip()


def _cadastral_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    vid = str(row.get("id") or "").strip()
    brand = str(row.get("brand") or row.get("brand_name") or "").strip()
    model = str(row.get("model") or "").strip()
    version = str(row.get("version") or "").strip()
    year = row.get("year") if row.get("year") not in (None, "") else (
        row.get("yearModel") if row.get("yearModel") not in (None, "") else row.get("year_model")
    )
    title = str(row.get("title") or "").strip()
    snapshot = {
        "id": vid,
        "brand": brand or None,
        "model": model or None,
        "version": version or None,
        "year": year,
        "title": title or None,
    }
    return snapshot


def conversational_label_from_record(row: dict[str, Any] | None) -> str | None:
    """Model + version + year from a catalog record. Never invent missing fields."""
    if not row:
        return None
    model = str(row.get("model") or "").strip()
    version = str(row.get("version") or "").strip()
    year_raw = row.get("year") if row.get("year") not in (None, "") else (
        row.get("yearModel") if row.get("yearModel") not in (None, "") else row.get("year_model")
    )
    year = ""
    if year_raw not in (None, ""):
        try:
            year = str(int(year_raw))
        except (TypeError, ValueError):
            year = str(year_raw).strip()
    parts: list[str] = []
    if model:
        parts.append(model)
    if version:
        existing = " ".join(parts).lower()
        if version.lower() not in existing:
            parts.append(version)
    if year:
        existing = " ".join(parts)
        if year not in existing:
            parts.append(year)
    return " ".join(parts) or None


def catalog_summary_label(vehicle_id: str | None, *, presented: dict[str, Any] | None = None) -> str | None:
    """Brand + model + version + year from the cadastral record when present."""
    row = catalog_vehicle(vehicle_id, presented=presented)
    if not row:
        return None
    brand = str(row.get("brand") or "").strip()
    conversational = conversational_label_from_record(row)
    if brand and conversational and brand.lower() not in conversational.lower():
        return f"{brand} {conversational}".strip()
    return conversational or brand or None


def catalog_vehicle(
    vehicle_id: str | None,
    *,
    presented: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not vehicle_id:
        return None
    row = _VEHICLES_BY_ID.get(str(vehicle_id))
    if row:
        return row
    if isinstance(presented, dict):
        extra = presented.get(str(vehicle_id))
        if isinstance(extra, dict):
            return extra
    return None


def conversational_label_for_id(
    vehicle_id: str | None,
    *,
    presented: dict[str, Any] | None = None,
) -> str | None:
    return conversational_label_from_record(catalog_vehicle(vehicle_id, presented=presented))


def register_catalog_vehicles(vehicles: list[dict[str, Any]]) -> None:
    """Merge published/sold seed vehicles into the enrichment index."""
    for row in vehicles or []:
        if not isinstance(row, dict):
            continue
        snapshot = _cadastral_snapshot(row)
        vid = snapshot.get("id")
        if vid:
            _VEHICLES_BY_ID[str(vid)] = snapshot
        model = _norm_key(str(row.get("model") or ""))
        brand = str(row.get("brand") or row.get("brand_name") or "").strip()
        if model and brand:
            _MODEL_TO_BRAND.setdefault(model, brand)
            combined = _norm_key(f"{brand} {model}")
            if combined:
                _MODEL_TO_BRAND.setdefault(combined, brand)


def lookup_brand_for_model(model: str | None) -> str | None:
    if not model:
        return None
    key = _norm_key(str(model))
    if key in _MODEL_TO_BRAND:
        return _MODEL_TO_BRAND[key]
    # Prefer the longest matching model token (onix plus before onix).
    matches = [m for m in _MODEL_TO_BRAND if m in key]
    if not matches:
        return None
    best = max(matches, key=len)
    return _MODEL_TO_BRAND[best]


def split_brand_model(raw: str | None) -> tuple[str | None, str | None]:
    """Return (brand, model) from 'Ford Ka' / 'Ka' / 'Peugeot 2008'."""
    if not raw or not str(raw).strip():
        return None, None
    text = str(raw).strip()
    folded = _norm_key(text)
    for brand_key in sorted(_KNOWN_BRANDS, key=len, reverse=True):
        if folded == brand_key:
            return _BRAND_CANON.get(brand_key, text), None
        prefix = brand_key + " "
        if folded.startswith(prefix):
            rest = text[len(brand_key):].strip()
            canon_brand = _BRAND_CANON.get(brand_key, brand_key.title())
            return canon_brand, rest or None
    catalog_brand = lookup_brand_for_model(text)
    return catalog_brand, text


def brands_compatible(brand: str | None, model: str | None) -> bool:
    """False when catalog knows the model and the stated brand disagrees."""
    if not brand or not model:
        return True
    expected = lookup_brand_for_model(model)
    if not expected:
        expected = lookup_brand_for_model(f"{brand} {model}")
    if not expected:
        return True
    return _norm_key(brand) == _norm_key(expected) or _norm_key(brand) in {
        "vw",
        "volkswagen",
    } and _norm_key(expected) == "volkswagen"


def enrich_vehicle(vehicle: dict[str, Any]) -> dict[str, Any]:
    """Fill brand from catalog; split a branded model string. Never invent a model."""
    if not vehicle:
        return vehicle
    out = dict(vehicle)
    raw_model = out.get("model")
    raw_brand = out.get("brand")
    split_brand, split_model = split_brand_model(str(raw_model) if raw_model else None)
    if split_brand and split_model:
        out["brand"] = split_brand
        out["model"] = split_model
        provenance = dict(out.get("_provenance") or {})
        provenance.setdefault("brand", "catalog")
        provenance.setdefault("model", provenance.get("model") or "customer")
        out["_provenance"] = provenance
    elif not raw_brand:
        catalog_brand = lookup_brand_for_model(str(raw_model) if raw_model else None)
        if catalog_brand:
            out["brand"] = catalog_brand
            provenance = dict(out.get("_provenance") or {})
            provenance["brand"] = "catalog"
            out["_provenance"] = provenance
    elif raw_brand and raw_model and not brands_compatible(str(raw_brand), str(raw_model)):
        catalog_brand = lookup_brand_for_model(str(raw_model))
        if catalog_brand:
            out["brand"] = catalog_brand
            provenance = dict(out.get("_provenance") or {})
            provenance["brand"] = "catalog"
            out["_provenance"] = provenance
        else:
            out.pop("brand", None)
    return out


def model_identity(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"[^a-z0-9]", "", _fold(str(value)))
