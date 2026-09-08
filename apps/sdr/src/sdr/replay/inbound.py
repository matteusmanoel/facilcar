"""Build a canonical InboundTurn from an explicit golden-scenario fixture.

Every replay capability used by a turn must appear in the JSON: events, delays,
quoted ids, image fixtures, document extraction, and simulated Storage.
"""

from __future__ import annotations

from typing import Any

from sdr.domain.inbound import ContentType, InboundTurn, MediaStatus, QuotedContext
from sdr.domain.inbound_batch import InboundSegment, compose_inbound_turn


def _content_type(raw: Any) -> ContentType:
    try:
        return ContentType[str(raw or "TEXT").upper()]
    except KeyError:
        return ContentType.TEXT


def _quoted(raw: Any) -> QuotedContext | None:
    if raw is None:
        return None
    if isinstance(raw, str) and raw.strip():
        return QuotedContext(stanza_id=raw.strip())
    if isinstance(raw, dict):
        stanza = str(raw.get("stanza_id") or raw.get("quoted_message_id") or "").strip()
        if not stanza:
            return None
        return QuotedContext(
            stanza_id=stanza,
            quoted_text=(str(raw["quoted_text"]) if raw.get("quoted_text") else None),
            quoted_type=(str(raw["quoted_type"]) if raw.get("quoted_type") else None),
        )
    return None


def build_replay_inbound(
    turn_def: dict[str, Any],
    *,
    thread_id: str,
    turn_idx: int,
) -> tuple[InboundTurn, bytes | None, list[int]]:
    """Return inbound, optional image bytes, and event delays_ms."""
    events = turn_def.get("events")
    delays: list[int] = []
    if isinstance(events, list) and events:
        segments: list[InboundSegment] = []
        image_bytes: bytes | None = None
        for order, event in enumerate(events):
            if not isinstance(event, dict):
                continue
            ctype = _content_type(event.get("content_type"))
            delays.append(int(event.get("delay_ms") or 0))
            quoted = _quoted(event.get("quoted") or event.get("quoted_message_id"))
            text = event.get("text") or event.get("caption")
            media_ok = ctype in {ContentType.IMAGE, ContentType.DOCUMENT, ContentType.AUDIO}
            seg = InboundSegment(
                message_id=str(event.get("message_id") or f"replay-{thread_id}-{turn_idx}-{order}"),
                content_type=ctype,
                text=str(text) if text else None,
                caption=str(event["caption"]) if event.get("caption") else None,
                media_status=MediaStatus.OK if media_ok else MediaStatus.NONE,
                provider_message_id=str(event.get("provider_message_id") or "") or None,
                mime_type=str(event["mime_type"]) if event.get("mime_type") else (
                    "image/png" if ctype == ContentType.IMAGE else None
                ),
                order=order,
                quoted=quoted,
                document_extracted=event.get("document_extracted")
                if isinstance(event.get("document_extracted"), dict)
                else None,
            )
            segments.append(seg)
            fixture = event.get("image_fixture") or turn_def.get("image_fixture")
            if ctype == ContentType.IMAGE and fixture:
                from tests.golden.fixtures.synthetic_media import load_image_fixture

                image_bytes = load_image_fixture(str(fixture))
        inbound = compose_inbound_turn(
            thread_id=thread_id,
            segments=segments,
            batch_id=str(turn_def.get("batch_id") or f"replay-batch-{turn_idx}"),
        )
        _apply_turn_metadata(inbound, turn_def)
        return inbound, image_bytes, delays

    inbound_text = str(turn_def.get("inbound") or "")
    ctype = _content_type(turn_def.get("content_type"))
    quoted = _quoted(turn_def.get("quoted") or turn_def.get("quoted_message_id"))
    media_ok = ctype in {ContentType.IMAGE, ContentType.DOCUMENT, ContentType.AUDIO}
    inbound = InboundTurn(
        thread_id=thread_id,
        content_type=ctype,
        text=inbound_text or None,
        media_status=MediaStatus.OK if media_ok else MediaStatus.NONE,
        quoted=[quoted] if quoted else [],
        raw_message_ref={},
    )
    if ctype == ContentType.IMAGE:
        inbound.mime_type = str(turn_def.get("mime_type") or "image/png")
    image_bytes = None
    fixture = turn_def.get("image_fixture")
    if fixture:
        from tests.golden.fixtures.synthetic_media import load_image_fixture

        image_bytes = load_image_fixture(str(fixture))
    _apply_turn_metadata(inbound, turn_def)
    return inbound, image_bytes, delays


def _apply_turn_metadata(inbound: InboundTurn, turn_def: dict[str, Any]) -> None:
    ref = dict(inbound.raw_message_ref or {})
    listing_id = turn_def.get("listing_id")
    listing_url = turn_def.get("listing_url")
    if listing_id:
        ref["listing_id"] = listing_id
    if listing_url:
        ref["listing_url"] = listing_url
    if turn_def.get("media_metadata"):
        ref["media_metadata"] = turn_def["media_metadata"]
    if isinstance(turn_def.get("visual_resolution"), dict):
        ref["visual_resolution"] = turn_def["visual_resolution"]
        ref["has_media"] = True
    extracted = turn_def.get("document_extracted")
    if isinstance(extracted, dict):
        ref["document_extracted"] = extracted
        ref["has_document"] = True
    storage = turn_def.get("storage_simulated")
    if isinstance(storage, dict):
        ref["storage_simulated"] = {
            "status": storage.get("status"),
            "bucket_kind": storage.get("bucket_kind") or "private",
            "public": False,
        }
    inbound.raw_message_ref = ref
    if not inbound.quoted:
        quoted = _quoted(turn_def.get("quoted") or turn_def.get("quoted_message_id"))
        if quoted:
            inbound.quoted = [quoted]
            ref["has_reply"] = True
            inbound.raw_message_ref = ref
