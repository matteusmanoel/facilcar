"""Canonical InboundTurn — single typed contract for all inbound modalities.

All provider events (text, audio, image, document) must be normalized into
an InboundTurn before the Understanding Engine runs. This prevents the
understanding layer from receiving modality-specific raw formats.

Media failure is represented as an explicit status — never as a magic text
sentinel like '__MEDIA_FAILED__' passed as customer message content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ContentType(str, Enum):
    TEXT = "TEXT"
    AUDIO = "AUDIO"
    IMAGE = "IMAGE"
    DOCUMENT = "DOCUMENT"


class MediaStatus(str, Enum):
    """Represents the result of media enrichment."""

    OK = "OK"         # Text is available and trustworthy.
    NONE = "NONE"     # No media — plain text message.
    FAILED = "FAILED" # Media was present but could not be processed.


class MediaFailureCode(str, Enum):
    DOWNLOAD_FAILED = "DOWNLOAD_FAILED"
    TRANSCRIPTION_FAILED = "TRANSCRIPTION_FAILED"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    NO_MEDIA_REF = "NO_MEDIA_REF"
    UNSUPPORTED_TYPE = "UNSUPPORTED_TYPE"


@dataclass(slots=True)
class InboundTurn:
    """Normalized representation of a customer message.

    Invariants:
    - All modalities converge to this type before Understanding Engine runs.
    - text is the resolved natural-language content (transcription for audio,
      extracted text for documents, caption/alt for images).
    - text is None only when media_status == FAILED.
    - raw_message_ref holds only provider metadata (no base64 content).
    """

    thread_id: str
    content_type: ContentType = ContentType.TEXT
    text: str | None = None
    media_status: MediaStatus = MediaStatus.NONE
    failure_code: MediaFailureCode | None = None
    # Optional provider metadata (no raw bytes, no base64).
    provider_message_id: str | None = None
    mime_type: str | None = None
    timestamp: float | None = None
    # Non-base64 reference for tracing/audit only.
    raw_message_ref: dict[str, Any] = field(default_factory=dict)
    # Typed origins when this turn was composed from a closed inbound batch.
    # Empty for single-message / legacy callers.
    segments: list[Any] = field(default_factory=list)

    @property
    def is_media_failed(self) -> bool:
        return self.media_status == MediaStatus.FAILED

    @property
    def effective_text(self) -> str:
        """Resolved text for understanding. Empty string on failure."""
        return self.text or ""


def make_text_inbound(
    thread_id: str,
    text: str,
    *,
    provider_message_id: str | None = None,
    timestamp: float | None = None,
) -> InboundTurn:
    return InboundTurn(
        thread_id=thread_id,
        content_type=ContentType.TEXT,
        text=text,
        media_status=MediaStatus.NONE,
        provider_message_id=provider_message_id,
        timestamp=timestamp,
    )


def make_audio_inbound(
    thread_id: str,
    transcription: str,
    *,
    mime_type: str | None = None,
    provider_message_id: str | None = None,
    timestamp: float | None = None,
) -> InboundTurn:
    return InboundTurn(
        thread_id=thread_id,
        content_type=ContentType.AUDIO,
        text=transcription,
        media_status=MediaStatus.OK,
        mime_type=mime_type,
        provider_message_id=provider_message_id,
        timestamp=timestamp,
    )


def make_media_failed_inbound(
    thread_id: str,
    failure_code: MediaFailureCode,
    *,
    content_type: ContentType = ContentType.AUDIO,
    provider_message_id: str | None = None,
) -> InboundTurn:
    return InboundTurn(
        thread_id=thread_id,
        content_type=content_type,
        text=None,
        media_status=MediaStatus.FAILED,
        failure_code=failure_code,
        provider_message_id=provider_message_id,
    )


def inbound_from_text_compat(text: str, thread_id: str = "") -> InboundTurn:
    """Compatibility helper for code that receives a plain text string.

    Used during the transition from raw str to InboundTurn.
    """
    if not text:
        return InboundTurn(
            thread_id=thread_id,
            content_type=ContentType.TEXT,
            text=None,
            media_status=MediaStatus.NONE,
        )
    return make_text_inbound(thread_id, text)
