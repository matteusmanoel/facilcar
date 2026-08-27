"""Inbound message batching — closed snapshot after quiet window.

Contract
--------
After the temporal quiet window for a thread (phone), the runtime closes a
**cutoff** timestamp and claims only PENDING inbound messages with
``createdAt <= cutoff``. Messages arriving later (or with ``createdAt`` after
the cutoff) belong to the **next** batch.

Official batch composition and status live in Postgres (``Message.turnFactsJson
._sdr_batch`` + ``processingStatus``). Redis is only used for debounce/lock.

Statuses (TEXT, no enum migration):
  PENDING → PROCESSING → DONE | ERROR
  SKIPPED:* unchanged for silence gates
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Sequence
import uuid

from sdr.domain.inbound import (
    ContentType,
    InboundTurn,
    MediaFailureCode,
    MediaStatus,
)


BATCH_JSON_KEY = "_sdr_batch"


class BatchStatus(str, Enum):
    PROCESSING = "PROCESSING"
    DONE = "DONE"
    ERROR = "ERROR"


@dataclass(slots=True)
class InboundSegment:
    """One provider event inside a closed batch (typed origin preserved)."""

    message_id: str
    content_type: ContentType
    text: str | None
    media_status: MediaStatus = MediaStatus.NONE
    failure_code: MediaFailureCode | None = None
    provider_message_id: str | None = None
    mime_type: str | None = None
    created_at: datetime | None = None
    # Image caption stays on the same segment (never a separate turn item).
    caption: str | None = None
    order: int = 0

    def resolved_text(self) -> str | None:
        """Natural-language contribution of this segment for Understanding."""
        if self.media_status == MediaStatus.FAILED:
            return None
        if self.content_type == ContentType.IMAGE:
            # Caption is the understanding text; image bytes are not text.
            return (self.caption or self.text or "").strip() or None
        return (self.text or "").strip() or None


@dataclass(slots=True)
class BatchResult:
    """Deterministic processing outcome recorded on every member message."""

    outbound_texts: list[str] = field(default_factory=list)
    outbound_sent: bool = False
    outbound_provider_ids: list[str | None] = field(default_factory=list)
    action: str | None = None
    reason_code: str | None = None
    error: str | None = None
    processed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "outbound_texts": list(self.outbound_texts),
            "outbound_sent": self.outbound_sent,
            "outbound_provider_ids": list(self.outbound_provider_ids),
            "action": self.action,
            "reason_code": self.reason_code,
            "error": self.error,
            "processed_at": self.processed_at,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "BatchResult":
        data = raw or {}
        return cls(
            outbound_texts=[str(t) for t in (data.get("outbound_texts") or [])],
            outbound_sent=bool(data.get("outbound_sent")),
            outbound_provider_ids=list(data.get("outbound_provider_ids") or []),
            action=data.get("action"),
            reason_code=data.get("reason_code"),
            error=data.get("error"),
            processed_at=data.get("processed_at"),
        )


@dataclass(slots=True)
class InboundBatch:
    """Closed snapshot of inbound messages for one turn."""

    batch_id: str
    conversation_id: str
    phone: str
    instance_name: str
    anchor_message_id: str
    cutoff: datetime
    message_ids: list[str]
    segments: list[InboundSegment]
    status: BatchStatus = BatchStatus.PROCESSING
    result: BatchResult = field(default_factory=BatchResult)

    @property
    def turn_id(self) -> str:
        """Alias — one closed batch == one conversational turn."""
        return self.batch_id

    def member_payload(self, message_id: str, *, order: int) -> dict[str, Any]:
        """JSON fragment stored under ``turnFactsJson._sdr_batch``."""
        return {
            "batch_id": self.batch_id,
            "turn_id": self.batch_id,
            "conversation_id": self.conversation_id,
            "anchor_message_id": self.anchor_message_id,
            "cutoff": _dt_to_iso(self.cutoff),
            "message_ids": list(self.message_ids),
            "order": order,
            "canonical_order": list(self.message_ids),
            "status": self.status.value,
            "result": self.result.to_dict(),
        }


def new_batch_id() -> str:
    return str(uuid.uuid4())


def _dt_to_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_cutoff(raw: str | datetime | None) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    text = str(raw).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def canonical_sort_key(row: Any) -> tuple:
    """Stable order: createdAt ASC, id ASC (out-of-arrival-order safe)."""
    created = row["createdAt"] if isinstance(row, dict) else row["createdAt"]
    mid = row["id"] if isinstance(row, dict) else row["id"]
    if isinstance(created, datetime) and created.tzinfo is not None:
        created = created.astimezone(timezone.utc).replace(tzinfo=None)
    return (created, str(mid))


def select_snapshot_rows(
    candidates: Sequence[Any],
    *,
    cutoff: datetime,
) -> list[Any]:
    """Closed snapshot: only rows with ``createdAt <= cutoff``, canonical order.

    Does **not** take every PENDING in the conversation — only those at or
    before the cutoff instant.
    """
    cutoff_naive = cutoff
    if cutoff.tzinfo is not None:
        cutoff_naive = cutoff.astimezone(timezone.utc).replace(tzinfo=None)

    included: list[Any] = []
    for row in candidates:
        created = row["createdAt"] if isinstance(row, dict) else row["createdAt"]
        if isinstance(created, datetime) and created.tzinfo is not None:
            created = created.astimezone(timezone.utc).replace(tzinfo=None)
        if created <= cutoff_naive:
            included.append(row)
    included.sort(key=canonical_sort_key)
    return included


def parse_batch_from_turn_facts(raw: Any) -> dict[str, Any] | None:
    """Extract ``_sdr_batch`` from Message.turnFactsJson."""
    data: dict[str, Any]
    if raw is None:
        return None
    if isinstance(raw, str):
        import json

        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return None
    elif isinstance(raw, dict):
        data = raw
    else:
        try:
            data = dict(raw)
        except Exception:
            return None
    batch = data.get(BATCH_JSON_KEY)
    return batch if isinstance(batch, dict) else None


def merge_turn_facts(existing: Any, patch: dict[str, Any]) -> dict[str, Any]:
    """Shallow-merge JSON patches without dropping ``_sdr_media`` / batch keys."""
    base: dict[str, Any] = {}
    if isinstance(existing, dict):
        base = dict(existing)
    elif isinstance(existing, str) and existing.strip():
        import json

        try:
            parsed = json.loads(existing)
            if isinstance(parsed, dict):
                base = parsed
        except json.JSONDecodeError:
            base = {}
    out = {**base, **patch}
    # Nested merge for _sdr_batch so result updates keep ids/cutoff.
    if BATCH_JSON_KEY in base and BATCH_JSON_KEY in patch:
        prev = base[BATCH_JSON_KEY] if isinstance(base[BATCH_JSON_KEY], dict) else {}
        nxt = patch[BATCH_JSON_KEY] if isinstance(patch[BATCH_JSON_KEY], dict) else {}
        out[BATCH_JSON_KEY] = {**prev, **nxt}
        if "result" in prev or "result" in nxt:
            prev_r = prev.get("result") if isinstance(prev.get("result"), dict) else {}
            nxt_r = nxt.get("result") if isinstance(nxt.get("result"), dict) else {}
            out[BATCH_JSON_KEY]["result"] = {**prev_r, **nxt_r}
    return out


def compose_inbound_turn(
    *,
    thread_id: str,
    segments: Sequence[InboundSegment],
    batch_id: str | None = None,
) -> InboundTurn:
    """Build one InboundTurn from ordered typed segments.

    Understanding sees ``effective_text`` = non-empty segment texts joined by
    newlines. Failed media segments do not contribute text (and do not become
    greetings). Dominant content_type is the first non-text modality if any,
    else TEXT. Image+caption remain a single segment.
    """
    ordered = sorted(segments, key=lambda s: s.order)
    texts: list[str] = []
    any_failed = False
    failure_code: MediaFailureCode | None = None
    dominant = ContentType.TEXT
    mime_type: str | None = None
    provider_ids: list[str] = []

    for seg in ordered:
        if seg.provider_message_id:
            provider_ids.append(seg.provider_message_id)
        if seg.media_status == MediaStatus.FAILED:
            any_failed = True
            failure_code = seg.failure_code or failure_code
            continue
        resolved = seg.resolved_text()
        if resolved:
            texts.append(resolved)
        if seg.content_type != ContentType.TEXT and dominant == ContentType.TEXT:
            dominant = seg.content_type
            mime_type = seg.mime_type

    joined = "\n".join(texts).strip()
    if not joined and any_failed and not texts:
        media_status = MediaStatus.FAILED
        text = None
    elif any(s.media_status == MediaStatus.OK for s in ordered):
        media_status = MediaStatus.OK if joined else MediaStatus.FAILED
        text = joined or None
        if not joined and any_failed:
            media_status = MediaStatus.FAILED
    else:
        media_status = MediaStatus.NONE
        text = joined or None

    return InboundTurn(
        thread_id=thread_id,
        content_type=dominant if joined or dominant == ContentType.TEXT else dominant,
        text=text,
        media_status=media_status if text or media_status == MediaStatus.FAILED else MediaStatus.NONE,
        failure_code=failure_code if media_status == MediaStatus.FAILED else None,
        provider_message_id=provider_ids[0] if provider_ids else None,
        mime_type=mime_type,
        raw_message_ref={
            "batch_id": batch_id,
            "segment_count": len(ordered),
            "message_ids": [s.message_id for s in ordered],
            "segments": [
                {
                    "message_id": s.message_id,
                    "content_type": s.content_type.value,
                    "order": s.order,
                    "media_status": s.media_status.value,
                    "has_text": bool(s.resolved_text()),
                }
                for s in ordered
            ],
        },
        segments=list(ordered),
    )
