"""Send vehicle photos via Evolution (VehicleImage URLs ordered by sortOrder)."""

from __future__ import annotations

from typing import Any

import asyncpg

from sdr.infrastructure.evolution_client import EvolutionClient

from sdr.domain.vehicle_presentation import (
    DEFAULT_MAX_PHOTOS,
    select_images_for_send,
)

SCHEMA = "facilcar"


async def fetch_vehicle_image_urls(
    pool: asyncpg.Pool,
    vehicle_id: str,
    *,
    limit: int = DEFAULT_MAX_PHOTOS,
) -> list[dict[str, Any]]:
    """Return image rows for a vehicle; cover is always in the sent set and last."""
    sql = f'''
SELECT "id", "url", "alt", "sortOrder", "isCover"
FROM "{SCHEMA}"."VehicleImage"
WHERE "vehicleId" = $1
ORDER BY "sortOrder" ASC
'''
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, vehicle_id)
    mapped = [
        {
            "id": str(r["id"]),
            "url": str(r["url"]),
            "alt": r["alt"],
            "sortOrder": int(r["sortOrder"]),
            "isCover": bool(r["isCover"]),
        }
        for r in rows
    ]
    return select_images_for_send(mapped, limit=limit)


def _mimetype_from_url(url: str) -> str:
    path = url.split("?", 1)[0].lower()
    if path.endswith(".png"):
        return "image/png"
    if path.endswith(".webp"):
        return "image/webp"
    if path.endswith(".gif"):
        return "image/gif"
    return "image/jpeg"


async def send_vehicle_photos(
    pool: asyncpg.Pool,
    evolution: EvolutionClient,
    *,
    vehicle_id: str,
    number: str,
    max_photos: int = DEFAULT_MAX_PHOTOS,
    caption: str | None = None,
) -> list[str | None]:
    """Fetch up to ``max_photos`` VehicleImage URLs and send each via Evolution.

    Returns provider message ids (or None) in send order. Orchestrator
    persists reserved ``isBotSent`` rows before send; this helper only
    talks to Evolution.
    """
    images = await fetch_vehicle_image_urls(pool, vehicle_id, limit=max_photos)
    images = select_images_for_send(images, limit=max_photos)
    message_ids: list[str | None] = []
    for index, image in enumerate(images):
        cap = caption if index == len(images) - 1 and caption else ""
        mid = await evolution.send_media(
            number,
            "image",
            image["url"],
            _mimetype_from_url(image["url"]),
            cap,
        )
        message_ids.append(mid)
    return message_ids
