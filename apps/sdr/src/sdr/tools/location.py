"""Store location from SiteSettings (for ``send_location`` action)."""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import quote

import asyncpg

logger = logging.getLogger(__name__)

SCHEMA = "facilcar"


def extract_coords_from_maps_url(url: str) -> tuple[float, float] | None:
    """Extract (latitude, longitude) from a Google Maps URL.

    Supports:
      - @lat,lng,zoom patterns (share links, place links)
      - !3dlat!4dlng parameter pairs
    """
    if not url:
        return None

    # Pattern 1: @lat,lng (e.g. @-24.9378419,-53.420055,17z)
    m = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", url)
    if m:
        return (float(m.group(1)), float(m.group(2)))

    # Pattern 2: !3dlat!4dlng (embedded in data= parameters)
    m = re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", url)
    if m:
        return (float(m.group(1)), float(m.group(2)))

    return None


async def fetch_site_settings(pool: asyncpg.Pool) -> dict[str, Any] | None:
    """Load the singleton SiteSettings row (address + coordinate fields).

    Falls back to the legacy column set when googleMapsUrl / coords are missing.
    """
    full_sql = f'''
SELECT
  "siteName",
  "addressLine",
  "city",
  "state",
  "zipCode",
  "phoneNumber",
  "defaultWhatsappNumber",
  "googleMapsUrl",
  "latitude",
  "longitude"
FROM "{SCHEMA}"."SiteSettings"
LIMIT 1
'''
    legacy_sql = f'''
SELECT
  "siteName",
  "addressLine",
  "city",
  "state",
  "zipCode",
  "phoneNumber",
  "defaultWhatsappNumber"
FROM "{SCHEMA}"."SiteSettings"
LIMIT 1
'''
    row = None
    used_legacy = False
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(full_sql)
        except Exception:
            logger.warning(
                "fetch_site_settings: coord columns unavailable; using address-only query"
            )
            used_legacy = True
    if used_legacy:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(legacy_sql)
    if row is None:
        return None
    data = {
        "siteName": row["siteName"],
        "addressLine": row["addressLine"],
        "city": row["city"],
        "state": row["state"],
        "zipCode": row["zipCode"],
        "phoneNumber": row["phoneNumber"],
        "defaultWhatsappNumber": row["defaultWhatsappNumber"],
        "googleMapsUrl": row.get("googleMapsUrl") if hasattr(row, "get") else None,
        "latitude": _as_float(row.get("latitude") if hasattr(row, "get") else None),
        "longitude": _as_float(row.get("longitude") if hasattr(row, "get") else None),
    }
    maps_url = data.get("googleMapsUrl")
    if data.get("latitude") is None and isinstance(maps_url, str):
        coords = extract_coords_from_maps_url(maps_url)
        if coords:
            data["latitude"], data["longitude"] = coords
    return data


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_maps_link(settings: dict[str, Any]) -> str | None:
    """Build a Google Maps link from coordinates or address string."""
    lat = settings.get("latitude")
    lng = settings.get("longitude")
    if lat is not None and lng is not None:
        return f"https://maps.google.com/?q={lat},{lng}"

    # Fall back to address-based URL (works without coordinates).
    parts: list[str] = []
    address = settings.get("addressLine")
    if isinstance(address, str) and address.strip():
        parts.append(address.strip())
    city = settings.get("city")
    if isinstance(city, str) and city.strip():
        parts.append(city.strip())
    state = settings.get("state")
    if isinstance(state, str) and state.strip():
        parts.append(state.strip())
    if parts:
        query = quote(" ".join(parts))
        return f"https://maps.google.com/?q={query}"
    return None


def format_location_text(
    settings: dict[str, Any] | None,
    *,
    include_maps_link: bool = True,
) -> str:
    """Build a WhatsApp-ready location text from SiteSettings fields."""
    if not settings:
        return "Posso te passar o endereço da loja — um instante que confirmo aqui."

    parts: list[str] = []
    address = settings.get("addressLine")
    if isinstance(address, str) and address.strip():
        parts.append(address.strip())

    city = settings.get("city")
    state_uf = settings.get("state")
    zip_code = settings.get("zipCode")
    city_line_bits: list[str] = []
    if isinstance(city, str) and city.strip():
        city_line_bits.append(city.strip())
    if isinstance(state_uf, str) and state_uf.strip():
        city_line_bits.append(state_uf.strip())
    if city_line_bits:
        line = " - ".join(city_line_bits)
        if isinstance(zip_code, str) and zip_code.strip():
            line = f"{line}, CEP {zip_code.strip()}"
        parts.append(line)
    elif isinstance(zip_code, str) and zip_code.strip():
        parts.append(f"CEP {zip_code.strip()}")

    maps_link = build_maps_link(settings) if include_maps_link else None

    site_name = settings.get("siteName")
    prefix = (
        f"{site_name.strip()}: "
        if isinstance(site_name, str) and site_name.strip()
        else "Nossa loja fica em: "
    )

    if parts:
        text = prefix + " | ".join(parts)
        if maps_link:
            text = f"{text}\n{maps_link}"
        return text

    if maps_link:
        return f"{prefix}{maps_link}"

    return "Posso te passar o endereço da loja — um instante que confirmo aqui."


def get_location_pin(settings: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return pin data for Evolution API if coordinates are available."""
    if not settings:
        return None
    lat = _as_float(settings.get("latitude"))
    lng = _as_float(settings.get("longitude"))
    if lat is None or lng is None:
        maps_url = settings.get("googleMapsUrl")
        if isinstance(maps_url, str):
            coords = extract_coords_from_maps_url(maps_url)
            if coords:
                lat, lng = coords
    if lat is None or lng is None:
        return None
    site_name = settings.get("siteName") or "FacilCar"
    address = settings.get("addressLine") or ""
    return {
        "latitude": float(lat),
        "longitude": float(lng),
        "name": site_name,
        "address": address,
    }


async def get_store_location(pool: asyncpg.Pool) -> dict[str, Any]:
    """Return full location data for the send_location action."""
    settings = await fetch_site_settings(pool)
    pin = get_location_pin(settings)
    return {
        "text": "" if pin else format_location_text(settings, include_maps_link=True),
        "pin": pin,
        "site_settings": settings or {},
    }
