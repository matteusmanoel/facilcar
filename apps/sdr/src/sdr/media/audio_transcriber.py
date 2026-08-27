"""OpenAI Whisper audio transcription (mockable)."""

from __future__ import annotations

import io
import logging
from typing import Any

from sdr.config import get_settings

logger = logging.getLogger(__name__)

DEFAULT_WHISPER_MODEL = "whisper-1"


def _is_unittest_mock(client: Any) -> bool:
    module = type(client).__module__ or ""
    return module.startswith("unittest.mock")


async def transcribe_audio(
    data: bytes,
    *,
    mime_type: str | None = None,
    filename: str | None = None,
    language: str | None = "pt",
    client: Any | None = None,
) -> str:
    """Transcribe audio bytes via ``audio.transcriptions.create``.

    Pass a mockable ``client`` (OpenAI-compatible) in tests.
    """
    if not data:
        return ""

    settings = get_settings()
    api_key = (settings.openai_api_key or "").strip()

    if client is None:
        if not api_key:
            logger.warning("transcribe_audio: no OPENAI_API_KEY; returning empty")
            return ""
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key)

    name = filename or "audio.ogg"
    if mime_type and "." not in name:
        # best-effort extension hint for the API
        if "mpeg" in mime_type or "mp3" in mime_type:
            name = "audio.mp3"
        elif "mp4" in mime_type or "m4a" in mime_type:
            name = "audio.m4a"
        elif "wav" in mime_type:
            name = "audio.wav"
        elif "ogg" in mime_type or "opus" in mime_type:
            name = "audio.ogg"

    buffer = io.BytesIO(data)
    buffer.name = name  # type: ignore[attr-defined]

    kwargs: dict[str, Any] = {
        "model": DEFAULT_WHISPER_MODEL,
        "file": buffer,
    }
    if language:
        kwargs["language"] = language

    if _is_unittest_mock(client):
        # Sync-style mock support (MagicMock) and AsyncMock.
        create = client.audio.transcriptions.create
        result = create(**kwargs)
        if hasattr(result, "__await__"):
            result = await result
    else:
        result = await client.audio.transcriptions.create(**kwargs)

    text = getattr(result, "text", None)
    if text is None and isinstance(result, dict):
        text = result.get("text")
    if text is None and isinstance(result, str):
        text = result
    return (text or "").strip()
