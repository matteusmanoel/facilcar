"""Deterministic synthetic images for golden replay — never real WhatsApp media."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw


def png_bytes(*, color: tuple[int, int, int], label: str, size: tuple[int, int] = (96, 64)) -> bytes:
    img = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, size[0], 18), fill=(20, 20, 20))
    draw.text((4, 3), label[:28], fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


FIXTURES = {
    "synthetic_fox": lambda: png_bytes(color=(90, 90, 110), label="VW FOX"),
    "synthetic_strada": lambda: png_bytes(color=(40, 80, 140), label="STRADA 2018"),
}


def load_image_fixture(name: str | None) -> bytes | None:
    if not name:
        return None
    factory = FIXTURES.get(str(name).strip())
    if factory is None:
        return None
    return factory()
