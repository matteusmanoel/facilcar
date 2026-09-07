"""Granular document status — received / deferred / missing per component.

A requested document is not a received document. Deferring CNH does not
defer the rest of the pack. Handoff may proceed with pendencies;
profile_complete may not.
"""

from __future__ import annotations

import re
from typing import Any

DOCUMENT_COMPONENTS: tuple[str, ...] = (
    "cnh",
    "proof_of_residence",
    "proof_of_income",
)

STATUS_RECEIVED = "received"
STATUS_DEFERRED = "deferred"
STATUS_MISSING = "missing"

_DEFER_UTTERANCE = re.compile(
    r"(enviar|envio|mando|mandar|posso\s+enviar).{0,40}depois|"
    r"depois.{0,24}(enviar|envio|mando|mandar)|"
    r"n[aã]o\s+tenho\s+(agora|no\s+momento)|"
    r"n[aã]o\s+tenho\s+(os\s+)?documentos|"
    r"n[aã]o\s+tenho\s+(a\s+)?(cnh|holerite|comprovante)",
    re.I,
)


def empty_document_status() -> dict[str, str]:
    return {k: STATUS_MISSING for k in DOCUMENT_COMPONENTS}


def parse_document_deferral(text: str) -> dict[str, str]:
    """Return component → deferred for the utterance, or {} if not a deferral."""
    raw = text or ""
    if not _DEFER_UTTERANCE.search(raw):
        return {}
    mentioned: list[str] = []
    if re.search(r"\bcnh\b", raw, re.I):
        mentioned.append("cnh")
    if re.search(r"resid[eê]ncia|comprovante de resid", raw, re.I):
        mentioned.append("proof_of_residence")
    if re.search(r"renda|holerite|comprovante de renda", raw, re.I):
        mentioned.append("proof_of_income")
    if mentioned:
        return {name: STATUS_DEFERRED for name in mentioned}
    return {name: STATUS_DEFERRED for name in DOCUMENT_COMPONENTS}


def merge_document_status(
    prev: dict[str, Any] | None,
    incoming: dict[str, Any] | None,
) -> dict[str, str]:
    out = empty_document_status()
    for src in (prev, incoming):
        if not isinstance(src, dict):
            continue
        for key in DOCUMENT_COMPONENTS:
            val = src.get(key)
            if val in {STATUS_RECEIVED, STATUS_DEFERRED, STATUS_MISSING}:
                out[key] = val
    return out


def received_components(status: dict[str, Any] | None) -> list[str]:
    if not isinstance(status, dict):
        return []
    return [k for k in DOCUMENT_COMPONENTS if status.get(k) == STATUS_RECEIVED]


def deferred_components(status: dict[str, Any] | None) -> list[str]:
    if not isinstance(status, dict):
        return []
    return [k for k in DOCUMENT_COMPONENTS if status.get(k) == STATUS_DEFERRED]


def missing_components(status: dict[str, Any] | None) -> list[str]:
    if not isinstance(status, dict):
        return list(DOCUMENT_COMPONENTS)
    return [
        k
        for k in DOCUMENT_COMPONENTS
        if status.get(k) not in {STATUS_RECEIVED, STATUS_DEFERRED}
    ]
