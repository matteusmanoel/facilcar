"""Helpers for WhatsApp document → canonical inbound + persist metadata."""

from __future__ import annotations

import json
from typing import Any, Mapping

from sdr.media.document_extractor import ExtractedDocument


def media_ref_from_row(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Read Evolution media pointer stored on Message.turnFactsJson._sdr_media."""
    if row is None:
        return None
    raw = row.get("turnFactsJson") if hasattr(row, "get") else None
    parsed: Any = raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except Exception:
            return None
    if not isinstance(parsed, dict):
        return None
    media = parsed.get("_sdr_media")
    return media if isinstance(media, dict) else None


def document_inbound_text(
    extracted: ExtractedDocument | Mapping[str, Any] | None,
    caption: str = "",
) -> str:
    """Natural-language text for Understanding. Empty when nothing was recovered."""
    parts: list[str] = []
    cap = (caption or "").strip()
    if cap:
        parts.append(cap)

    payload: Mapping[str, Any] | None
    if extracted is None:
        payload = None
    elif isinstance(extracted, ExtractedDocument):
        payload = extracted.as_dict()
    else:
        payload = extracted

    if payload:
        labels = {
            "name": "nome",
            "cpf": "cpf",
            "birth_date": "data_nascimento",
            "birth_city": "cidade_nascimento",
            "birth_state": "uf_nascimento",
            "plate": "placa",
            "document_type": "tipo",
        }
        for key, label in labels.items():
            value = payload.get(key)
            if value:
                parts.append(f"{label}: {value}")

    return "\n".join(parts).strip()


def document_kind_from_inbound_text(text: str) -> str | None:
    """Read ``tipo: CNH`` from our extractor's inbound format."""
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("tipo:"):
            kind = stripped.split(":", 1)[1].strip().upper()
            return kind or None
    return None


def document_kind_from_inbound(inbound: Any) -> str | None:
    """Prefer structured extraction over inbound text; CNH wins if present."""
    kinds = document_kinds_from_inbound(inbound)
    if "CNH" in kinds:
        return "CNH"
    if kinds:
        return kinds[0]
    text = getattr(inbound, "effective_text", None) or getattr(inbound, "text", None) or ""
    return document_kind_from_inbound_text(str(text))


def document_kinds_from_inbound(inbound: Any) -> list[str]:
    """Every extracted document type on this inbound, in segment order."""
    kinds: list[str] = []
    seen: set[str] = set()

    def _add(kind: str | None) -> None:
        if not kind:
            return
        token = str(kind).strip().upper()
        if not token or token in seen:
            return
        seen.add(token)
        kinds.append(token)

    for seg in getattr(inbound, "segments", None) or []:
        extracted = getattr(seg, "document_extracted", None) or {}
        if isinstance(extracted, dict):
            _add(extracted.get("document_type"))
    raw = getattr(inbound, "raw_message_ref", None) or {}
    if isinstance(raw, dict):
        extracted = raw.get("document_extracted")
        if isinstance(extracted, dict):
            _add(extracted.get("document_type"))
        extra = raw.get("document_extracted_list")
        if isinstance(extra, list):
            for item in extra:
                if isinstance(item, dict):
                    _add(item.get("document_type"))
    return kinds


def identity_fields_from_inbound(inbound: Any) -> dict[str, Any]:
    """Identity extracted from every document segment. First non-empty wins."""
    keys = ("cpf", "birth_date", "birth_city", "birth_state", "name")
    payloads: list[Mapping[str, Any]] = []
    for seg in getattr(inbound, "segments", None) or []:
        extracted = getattr(seg, "document_extracted", None)
        if isinstance(extracted, dict):
            payloads.append(extracted)
    raw = getattr(inbound, "raw_message_ref", None) or {}
    if isinstance(raw, dict):
        extracted = raw.get("document_extracted")
        if isinstance(extracted, dict):
            payloads.append(extracted)
        extra = raw.get("document_extracted_list")
        if isinstance(extra, list):
            payloads.extend(item for item in extra if isinstance(item, dict))
    out: dict[str, Any] = {}
    for payload in payloads:
        for key in keys:
            value = payload.get(key)
            if value and key not in out:
                out[key] = value
    return out


def document_extraction_status(*, extracted: bool) -> str:
    """OCR outcome is independent of object-storage upload."""
    return "DONE" if extracted else "FAILED"
