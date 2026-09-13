"""Closed-snapshot inbound coalesce — build typed segments + InboundTurn."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Sequence

from sdr.domain.inbound import ContentType, MediaFailureCode, MediaStatus, QuotedContext
from sdr.domain.inbound_batch import (
    InboundBatch,
    InboundSegment,
    BatchResult,
    BatchStatus,
    compose_inbound_turn,
    new_batch_id,
    parse_batch_from_turn_facts,
    select_snapshot_rows,
)


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def content_type_from_row(row: Any) -> ContentType:
    raw = str(row["contentType"] or "TEXT").upper()
    try:
        return ContentType(raw)
    except ValueError:
        return ContentType.TEXT


def _facts_from_row(row: Any) -> dict[str, Any]:
    raw = row["turnFactsJson"]
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    try:
        data = dict(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def quoted_from_row(row: Any) -> QuotedContext | None:
    data = _facts_from_row(row)
    if not data:
        return None
    quoted_obj = data.get("_sdr_quoted")
    stanza_id = data.get("_sdr_quoted_id")
    quoted_text = None
    quoted_type = None
    if isinstance(quoted_obj, dict):
        stanza_id = stanza_id or quoted_obj.get("stanzaId") or quoted_obj.get("stanza_id")
        quoted_text = quoted_obj.get("quotedText") or quoted_obj.get("quoted_text")
        quoted_type = quoted_obj.get("quotedType") or quoted_obj.get("quoted_type")
    if not stanza_id and not quoted_text:
        return None
    return QuotedContext(
        stanza_id=str(stanza_id) if stanza_id else None,
        quoted_text=str(quoted_text) if quoted_text else None,
        quoted_type=str(quoted_type) if quoted_type else None,
    )


def segment_from_row(
    row: Any,
    *,
    order: int,
    text_override: str | None = None,
    media_status: MediaStatus | None = None,
    failure_code: MediaFailureCode | None = None,
) -> InboundSegment:
    """Map a Message row to a typed segment (image caption stays on IMAGE)."""
    ctype = content_type_from_row(row)
    stored_text = row["text"]
    transcription = row["transcription"]
    if text_override is not None:
        text = text_override
    elif ctype == ContentType.AUDIO:
        text = transcription or stored_text
    elif ctype == ContentType.IMAGE:
        text = stored_text  # caption on same provider event
    else:
        text = stored_text or transcription

    caption = stored_text if ctype == ContentType.IMAGE else None
    status = media_status
    if status is None:
        if ctype in (ContentType.AUDIO, ContentType.DOCUMENT) and not (text or "").strip():
            # Unresolved media — caller should enrich before compose; mark NONE
            # until enrichment decides OK/FAILED.
            status = MediaStatus.NONE
        elif ctype == ContentType.AUDIO and (text or "").strip():
            status = MediaStatus.OK
        elif ctype == ContentType.IMAGE:
            status = MediaStatus.OK if (caption or text) else MediaStatus.NONE
        else:
            status = MediaStatus.NONE

    facts = _facts_from_row(row)
    document_extracted = facts.get("document_extracted")
    if not isinstance(document_extracted, dict):
        document_extracted = None
    vehicle_hint = facts.get("vehicle_hint")
    if not isinstance(vehicle_hint, dict):
        vehicle_hint = None

    return InboundSegment(
        message_id=str(row["id"]),
        content_type=ctype,
        text=text,
        media_status=status if failure_code is None else MediaStatus.FAILED,
        failure_code=failure_code,
        provider_message_id=str(row["providerMessageId"] or "") or None,
        mime_type=row["mediaMimeType"],
        created_at=row["createdAt"],
        caption=caption,
        order=order,
        quoted=quoted_from_row(row),
        vehicle_hint=vehicle_hint,
        document_extracted=document_extracted,
    )


def build_batch_from_claimed_rows(
    rows: Sequence[Any],
    *,
    conversation_id: str,
    phone: str,
    instance_name: str,
    cutoff: datetime,
    batch_id: str | None = None,
    segments: Sequence[InboundSegment] | None = None,
) -> InboundBatch:
    message_ids = [str(r["id"]) for r in rows]
    bid = batch_id or new_batch_id()
    segs = list(segments) if segments is not None else [
        segment_from_row(r, order=i) for i, r in enumerate(rows)
    ]
    return InboundBatch(
        batch_id=bid,
        conversation_id=conversation_id,
        phone=phone,
        instance_name=instance_name,
        anchor_message_id=message_ids[0],
        cutoff=cutoff,
        message_ids=message_ids,
        segments=segs,
        status=BatchStatus.PROCESSING,
        result=BatchResult(),
    )


def batch_meta_from_seed(row: Any) -> dict[str, Any] | None:
    return parse_batch_from_turn_facts(row["turnFactsJson"])


def is_retry_seed(row: Any) -> bool:
    if str(row["processingStatus"] or "") != "ERROR":
        return False
    meta = batch_meta_from_seed(row)
    if not meta:
        return False
    result = meta.get("result") or {}
    return result.get("outbound_sent") is not True


def compose_turn_from_batch(batch: InboundBatch) -> Any:
    return compose_inbound_turn(
        thread_id=batch.conversation_id,
        segments=batch.segments,
        batch_id=batch.batch_id,
    )


# Re-export for callers/tests
__all__ = [
    "batch_meta_from_seed",
    "build_batch_from_claimed_rows",
    "compose_turn_from_batch",
    "content_type_from_row",
    "is_retry_seed",
    "quoted_from_row",
    "segment_from_row",
    "select_snapshot_rows",
    "utc_now_naive",
]
