"""Store location text from SiteSettings (for ``send_location`` action)."""

from __future__ import annotations

from typing import Any

import asyncpg

SCHEMA = "facilcar"


async def fetch_site_settings(pool: asyncpg.Pool) -> dict[str, Any] | None:
    """Load the singleton SiteSettings row (address fields)."""
    sql = f'''
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
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql)
    if row is None:
        return None
    return {
        "siteName": row["siteName"],
        "addressLine": row["addressLine"],
        "city": row["city"],
        "state": row["state"],
        "zipCode": row["zipCode"],
        "phoneNumber": row["phoneNumber"],
        "defaultWhatsappNumber": row["defaultWhatsappNumber"],
    }


def format_location_text(settings: dict[str, Any] | None) -> str:
    """Build a WhatsApp-ready location bubble from SiteSettings fields."""
    if not settings:
        return "Posso te passar o endereço da loja — um instante que confirmo aqui."

    parts: list[str] = []
    address = settings.get("addressLine")
    if isinstance(address, str) and address.strip():
        parts.append(address.strip())

    city = settings.get("city")
    state = settings.get("state")
    zip_code = settings.get("zipCode")
    city_line_bits: list[str] = []
    if isinstance(city, str) and city.strip():
        city_line_bits.append(city.strip())
    if isinstance(state, str) and state.strip():
        city_line_bits.append(state.strip())
    if city_line_bits:
        line = " - ".join(city_line_bits)
        if isinstance(zip_code, str) and zip_code.strip():
            line = f"{line}, CEP {zip_code.strip()}"
        parts.append(line)
    elif isinstance(zip_code, str) and zip_code.strip():
        parts.append(f"CEP {zip_code.strip()}")

    site_name = settings.get("siteName")
    if parts:
        prefix = (
            f"{site_name.strip()}: "
            if isinstance(site_name, str) and site_name.strip()
            else "Nossa loja fica em: "
        )
        return prefix + " | ".join(parts)

    return "Posso te passar o endereço da loja — um instante que confirmo aqui."


async def get_store_location_text(pool: asyncpg.Pool) -> str:
    """Return SiteSettings address as text for the send_location action."""
    settings = await fetch_site_settings(pool)
    return format_location_text(settings)
