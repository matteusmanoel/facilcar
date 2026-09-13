"""Inbound image safety — size, MIME, decode, decompression bomb.

Does not fetch URLs. Caller must obtain bytes only from Evolution/Storage.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass

from PIL import Image, ImageFile, UnidentifiedImageError

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
ALLOWED_MIMES = frozenset(
    {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
        "image/gif",
    }
)
_MAGIC = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"RIFF", "image/webp"),  # WebP is RIFF....WEBP
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


@dataclass(frozen=True, slots=True)
class MediaSafetyResult:
    ok: bool
    mime_type: str | None = None
    reason: str | None = None
    width: int | None = None
    height: int | None = None


def _sniff_mime(data: bytes) -> str | None:
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    for magic, mime in _MAGIC:
        if magic != b"RIFF" and data.startswith(magic):
            return mime
    return None


def looks_like_arbitrary_url(value: str | None) -> bool:
    text = (value or "").strip().lower()
    return text.startswith("http://") or text.startswith("https://") or text.startswith("file:")


def validate_image_bytes(
    data: bytes | None,
    *,
    declared_mime: str | None = None,
) -> MediaSafetyResult:
    if not data:
        return MediaSafetyResult(ok=False, reason="empty")
    if len(data) > MAX_IMAGE_BYTES:
        return MediaSafetyResult(ok=False, reason="too_large")
    if data[:5] == b"%PDF-" or data[:4] == b"%PDF":
        return MediaSafetyResult(ok=False, reason="not_visual")
    sniffed = _sniff_mime(data)
    declared = (declared_mime or "").split(";", 1)[0].strip().lower()
    if declared == "image/jpg":
        declared = "image/jpeg"
    if declared and declared not in ALLOWED_MIMES:
        return MediaSafetyResult(ok=False, reason="invalid_mime")
    mime = sniffed or (declared if declared in ALLOWED_MIMES else None)
    if mime is None:
        return MediaSafetyResult(ok=False, reason="invalid_mime")
    if sniffed and declared and declared in ALLOWED_MIMES:
        if sniffed != declared and not (
            sniffed == "image/jpeg" and declared == "image/jpeg"
        ):
            # Declared MIME disagrees with magic — treat as spoofed.
            if sniffed not in ALLOWED_MIMES:
                return MediaSafetyResult(ok=False, reason="invalid_mime")
            mime = sniffed
    previous_cap = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    ImageFile.LOAD_TRUNCATED_IMAGES = False
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            width, height = img.size
            if width <= 0 or height <= 0:
                return MediaSafetyResult(ok=False, reason="corrupt")
            pixels = width * height
            if pixels > MAX_IMAGE_PIXELS:
                return MediaSafetyResult(ok=False, reason="too_large")
            return MediaSafetyResult(
                ok=True,
                mime_type=mime,
                width=width,
                height=height,
            )
    except Image.DecompressionBombError:
        return MediaSafetyResult(ok=False, reason="too_large")
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        return MediaSafetyResult(ok=False, reason="corrupt")
    except Exception:
        logger.debug("validate_image_bytes: unexpected decode failure", exc_info=True)
        return MediaSafetyResult(ok=False, reason="corrupt")
    finally:
        Image.MAX_IMAGE_PIXELS = previous_cap
