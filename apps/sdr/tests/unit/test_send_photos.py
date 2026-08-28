"""send_vehicle_photos attaches caption to the last image."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from sdr.tools.send_photos import send_vehicle_photos


@pytest.mark.asyncio
async def test_send_vehicle_photos_caption_on_last() -> None:
    images = [
        {"id": "1", "url": "https://cdn.example/a.jpg", "alt": None, "sortOrder": 0, "isCover": True},
        {"id": "2", "url": "https://cdn.example/b.jpg", "alt": None, "sortOrder": 1, "isCover": False},
    ]
    evolution = AsyncMock()
    evolution.send_media = AsyncMock(side_effect=["m1", "m2"])

    async def fake_fetch(pool, vehicle_id, *, limit=5):
        return images

    import sdr.tools.send_photos as mod

    original = mod.fetch_vehicle_image_urls
    mod.fetch_vehicle_image_urls = fake_fetch
    try:
        ids = await send_vehicle_photos(
            AsyncMock(),
            evolution,
            vehicle_id="v1",
            number="5545999999999",
            caption="Corolla • 2016\nPreço: R$ 84.900",
        )
    finally:
        mod.fetch_vehicle_image_urls = original

    assert ids == ["m1", "m2"]
    first_cap = evolution.send_media.await_args_list[0].args[4]
    last_cap = evolution.send_media.await_args_list[1].args[4]
    assert first_cap == ""
    assert "R$ 84.900" in last_cap
