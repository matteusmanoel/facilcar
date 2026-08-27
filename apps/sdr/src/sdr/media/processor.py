"""Route inbound media by content type to transcription / Vision / document extract."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from sdr.media.audio_transcriber import transcribe_audio
from sdr.media.document_extractor import (
    ConflictCheckResult,
    ExtractedDocument,
    extract_document,
)
from sdr.media.image_describer import describe_image


class MediaContentType(str, Enum):
    AUDIO = "AUDIO"
    IMAGE = "IMAGE"
    DOCUMENT = "DOCUMENT"


@dataclass(slots=True)
class MediaProcessResult:
    content_type: MediaContentType
    text: str | None = None
    description: str | None = None
    extracted: ExtractedDocument | None = None
    conflict: ConflictCheckResult | None = None
    routed_as: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def _looks_like_document(
    *,
    content_type: MediaContentType,
    mime_type: str | None,
    as_document: bool,
) -> bool:
    if as_document or content_type is MediaContentType.DOCUMENT:
        return True
    if not mime_type:
        return False
    lower = mime_type.lower()
    return lower in (
        "application/pdf",
        "image/pdf",
    ) or lower.endswith("/pdf")


async def process_media(
    data: bytes,
    *,
    content_type: MediaContentType | str,
    mime_type: str | None = None,
    filename: str | None = None,
    as_document: bool = False,
    state_facts: Mapping[str, Any] | None = None,
    client: Any | None = None,
) -> MediaProcessResult:
    """Route by content type.

    - AUDIO → Whisper transcription
    - IMAGE (general) → Vision brief description (no mechanical/value claims)
    - DOCUMENT / IMAGE as doc → document_extractor
    """
    if isinstance(content_type, str):
        ct = MediaContentType(content_type.upper())
    else:
        ct = content_type

    if ct is MediaContentType.AUDIO:
        text = await transcribe_audio(
            data,
            mime_type=mime_type,
            filename=filename,
            client=client,
        )
        return MediaProcessResult(
            content_type=ct,
            text=text,
            routed_as="audio_transcriber",
        )

    if _looks_like_document(content_type=ct, mime_type=mime_type, as_document=as_document):
        extracted, conflict = await extract_document(
            data,
            mime_type=mime_type,
            state_facts=state_facts,
            client=client,
        )
        return MediaProcessResult(
            content_type=MediaContentType.DOCUMENT
            if ct is MediaContentType.DOCUMENT
            else ct,
            extracted=extracted,
            conflict=conflict,
            text=None,
            routed_as="document_extractor",
        )

    # General IMAGE
    description = await describe_image(data, mime_type=mime_type, client=client)
    return MediaProcessResult(
        content_type=ct,
        description=description,
        text=description,
        routed_as="image_describer",
    )
