"""Internal document storage status — independent of commercial receipt.

``document_status.cnh = received`` means the customer provided a CNH in the
conversation. It is not proof that the file is in the private bucket.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Literal

from sdr.domain.document_status import STATUS_RECEIVED, merge_document_status
from sdr.domain.inbound import ContentType, InboundTurn, MediaStatus

STORAGE_PENDING = "pending"
STORAGE_PROCESSING = "processing"
STORAGE_STORED = "stored"
STORAGE_RETRYABLE_FAILURE = "retryable_failure"
STORAGE_PERMANENT_FAILURE = "permanent_failure"

StorageStatus = Literal[
    "pending",
    "processing",
    "stored",
    "retryable_failure",
    "permanent_failure",
]

SCHEMA_STATUS = {
    STORAGE_PENDING: "PENDING",
    STORAGE_PROCESSING: "PROCESSING",
    STORAGE_STORED: "STORED",
    STORAGE_RETRYABLE_FAILURE: "RETRYABLE_FAILURE",
    STORAGE_PERMANENT_FAILURE: "PERMANENT_FAILURE",
}

FORBIDDEN_DOCUMENT_BUCKETS = frozenset({"vehicle-images"})
_SAFE_ID = re.compile(r"[^A-Za-z0-9_-]+")

DOCUMENT_TYPE_TO_COMPONENT = {
    "CNH": "cnh",
    "INCOME_PROOF": "proof_of_income",
    "RESIDENCE_PROOF": "proof_of_residence",
}


def content_hash_for(data: bytes) -> str:
    return hashlib.sha256(data or b"").hexdigest()[:16]


def _safe_token(value: str | None, *, fallback: str = "unknown") -> str:
    cleaned = _SAFE_ID.sub("", (value or "").strip())[:80]
    return cleaned or fallback


def build_document_storage_key(
    *,
    conversation_id: str,
    provider_message_id: str,
    document_type: str,
    content_hash: str,
    extension: str,
) -> str:
    """Stable object key. No name, CPF, phone, or birth date."""
    conv = _safe_token(conversation_id)
    provider = _safe_token(provider_message_id)
    doc = _safe_token((document_type or "OTHER").lower(), fallback="other")
    digest = _safe_token(content_hash, fallback="nodigest")
    ext = (extension or "bin").lstrip(".").lower() or "bin"
    return f"sdr-documents/{conv}/{provider}_{doc}_{digest}.{ext}"


def commercial_status_patch(document_type: str | None) -> dict[str, str]:
    if not document_type:
        return {}
    component = DOCUMENT_TYPE_TO_COMPONENT.get(str(document_type).strip().upper())
    if not component:
        return {}
    return {component: STATUS_RECEIVED}


def _document_types_from_inbound(inbound: InboundTurn) -> list[str]:
    kinds: list[str] = []
    seen: set[str] = set()

    def _add(kind: str) -> None:
        token = str(kind).strip().upper()
        if not token or token in seen:
            return
        seen.add(token)
        kinds.append(token)

    for seg in inbound.segments or []:
        if getattr(seg, "content_type", None) != ContentType.DOCUMENT:
            continue
        extracted = getattr(seg, "document_extracted", None) or {}
        if isinstance(extracted, dict) and extracted.get("document_type"):
            _add(str(extracted["document_type"]))
        else:
            _add("OTHER")
    raw = inbound.raw_message_ref or {}
    extra = raw.get("document_extracted_list")
    if isinstance(extra, list):
        for item in extra:
            if isinstance(item, dict) and item.get("document_type"):
                _add(str(item["document_type"]))
    if not kinds and inbound.content_type == ContentType.DOCUMENT:
        extracted = raw.get("document_extracted")
        if isinstance(extracted, dict) and extracted.get("document_type"):
            _add(str(extracted["document_type"]))
        else:
            _add("OTHER")
    return kinds


def apply_commercial_document_receipt(state: Any, inbound: InboundTurn) -> None:
    """Mark the document as commercially received without implying Storage."""
    has_document = inbound.content_type == ContentType.DOCUMENT or any(
        getattr(seg, "content_type", None) == ContentType.DOCUMENT
        for seg in (inbound.segments or [])
    )
    if not has_document:
        return
    if inbound.media_status == MediaStatus.FAILED:
        return
    state.document_received = True
    incoming: dict[str, str] = {}
    for kind in _document_types_from_inbound(inbound):
        incoming.update(commercial_status_patch(kind))
    if incoming:
        state.facts = dict(state.facts or {})
        state.facts["document_status"] = merge_document_status(
            state.facts.get("document_status"), incoming
        )


def classify_empty_payload(data: bytes | None) -> str:
    if not data:
        return STORAGE_PERMANENT_FAILURE
    return STORAGE_PENDING


def classify_storage_error(exc: BaseException) -> str:
    text = str(exc).lower()
    permanent_markers = (
        "invalidargument",
        "invalid key",
        "empty body",
    )
    if any(m in text for m in permanent_markers):
        return STORAGE_PERMANENT_FAILURE
    return STORAGE_RETRYABLE_FAILURE


def sanitize_storage_error(exc: BaseException) -> str:
    text = f"{type(exc).__name__}: {exc}"
    text = re.sub(r"https?://\\S+", "<url>", text)
    text = re.sub(r"(?i)(secret|token|key|password)=\\S+", r"\\1=<redacted>", text)
    return text[:300]


def resolve_documents_bucket(configured: str | None) -> str | None:
    bucket = (configured or "").strip()
    if not bucket or bucket in FORBIDDEN_DOCUMENT_BUCKETS:
        return None
    return bucket
