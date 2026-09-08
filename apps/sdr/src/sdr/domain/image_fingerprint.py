"""Content and perceptual fingerprints for inventory images.

No network I/O. Bytes are never logged here.
"""

from __future__ import annotations

import hashlib
import io
from typing import Any

# 64-bit difference-hash: empirically stable under WhatsApp recompress/resize.
DHASH_MAX_DISTANCE = 10
DHASH_MIN_MARGIN = 4
RESOLVER_VERSION = "v1"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data or b"").hexdigest()


def dhash64(data: bytes) -> int | None:
    """Return a 64-bit difference hash, or None if the bytes are not an image."""
    if not data:
        return None
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as img:
            gray = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
            if hasattr(gray, "get_flattened_data"):
                pixels = list(gray.get_flattened_data())
            else:
                pixels = list(gray.getdata())
    except Exception:
        return None
    bits = 0
    for row in range(8):
        for col in range(8):
            left = pixels[row * 9 + col]
            right = pixels[row * 9 + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return bits


def hamming_distance(a: int, b: int) -> int:
    return (int(a) ^ int(b)).bit_count()


def dhash_hex(value: int | None) -> str | None:
    if value is None:
        return None
    return f"{int(value) & ((1 << 64) - 1):016x}"


def parse_dhash(raw: Any) -> int | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, int):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    try:
        if text.startswith("0x"):
            return int(text, 16)
        if all(ch in "0123456789abcdefABCDEF" for ch in text) and len(text) <= 16:
            return int(text, 16)
        return int(text)
    except (TypeError, ValueError):
        return None
