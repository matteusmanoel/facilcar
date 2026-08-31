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


def document_extraction_status(*, extracted: bool) -> str:
    """OCR outcome is independent of object-storage upload."""
    return "DONE" if extracted else "FAILED"
