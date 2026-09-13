"""Partial debt checks — fines ≠ all debts."""

from __future__ import annotations

import re
from typing import Any

# Core categories participate in the aggregate debt_status.
# `other` is extra evidence only — omit it unless the customer stated it.
CORE_DEBT_KEYS = ("fines", "ipva", "licensing")
DEBT_KEYS = ("fines", "ipva", "licensing", "other")
STATUS_CLEAR = "clear"
STATUS_HAS = "has_debt"
STATUS_UNKNOWN = "unknown"
STATUS_PARTIAL = "partial"
STATUS_HAS_DEBTS = "has_debts"

_FINES_ONLY = re.compile(
    r"n[aã]o\s+tenho\s+multas|sem\s+multas|multas?\s+n[aã]o|s[oó]\s+n[aã]o\s+tenho\s+multa",
    re.I,
)
_IPVA = re.compile(r"\bipva\b", re.I)
_LICENSING = re.compile(r"licenci", re.I)
_CLEAR_ALL = re.compile(
    r"tudo\s+em\s+dia|sem\s+d[eé]bitos|nada\s+pendente|regularizado|"
    r"sem\s+pend[eê]ncias|n[aã]o\s+tenho\s+d[eé]bito",
    re.I,
)
_HAS_DEBT = re.compile(r"\b(?:tem|tenho|possu[oi])\b.*\b(?:multa|d[eé]bito|ipva|licenci)", re.I)


def empty_checks() -> dict[str, str]:
    return {k: STATUS_UNKNOWN for k in CORE_DEBT_KEYS}


def persistable_checks(checks: dict[str, Any] | None) -> dict[str, str]:
    """Drop unknown `other` so clear + other=unknown never coexists."""
    merged = merge_checks(None, checks)
    out = {k: merged[k] for k in CORE_DEBT_KEYS}
    extra = None
    if isinstance(checks, dict):
        extra = checks.get("other")
    if extra in {STATUS_CLEAR, STATUS_HAS}:
        out["other"] = extra
    return out


def merge_checks(prev: dict[str, Any] | None, incoming: dict[str, Any] | None) -> dict[str, str]:
    out = empty_checks()
    other: str | None = None
    for src in (prev, incoming):
        if not isinstance(src, dict):
            continue
        for key in CORE_DEBT_KEYS:
            val = src.get(key)
            if val in {STATUS_CLEAR, STATUS_HAS, STATUS_UNKNOWN}:
                out[key] = val
        extra = src.get("other")
        if extra in {STATUS_CLEAR, STATUS_HAS}:
            other = extra
    if other:
        out["other"] = other
    return out


def compute_debt_status(checks: dict[str, Any] | None) -> str:
    merged = merge_checks(None, checks)
    if any(merged.get(k) == STATUS_HAS for k in CORE_DEBT_KEYS) or merged.get("other") == STATUS_HAS:
        return STATUS_HAS_DEBTS
    if all(merged.get(k) == STATUS_CLEAR for k in CORE_DEBT_KEYS):
        return STATUS_CLEAR
    if any(merged.get(k) == STATUS_CLEAR for k in CORE_DEBT_KEYS):
        return STATUS_PARTIAL
    return STATUS_UNKNOWN


def debts_are_resolved(checks: dict[str, Any] | None, status: str | None) -> bool:
    if status == STATUS_HAS_DEBTS:
        return True
    if status == STATUS_CLEAR:
        return True
    return compute_debt_status(checks) in {STATUS_CLEAR, STATUS_HAS_DEBTS}


def parse_debt_utterance(text: str) -> dict[str, Any]:
    """Return a fragment: checks updates and/or confirmed types. Never uses sem_multas."""
    raw = text or ""
    checks: dict[str, str] = {}
    out: dict[str, Any] = {}

    if _FINES_ONLY.search(raw) and not _CLEAR_ALL.search(raw):
        checks["fines"] = STATUS_CLEAR
        out["partial"] = True

    ipva = bool(_IPVA.search(raw))
    licensing = bool(_LICENSING.search(raw))
    clearish = bool(_CLEAR_ALL.search(raw)) or bool(re.search(r"em\s+dia", raw, re.I))

    if ipva and (clearish or re.search(r"em\s+dia", raw, re.I)):
        checks["ipva"] = STATUS_CLEAR
    if licensing and (clearish or re.search(r"em\s+dia", raw, re.I)):
        checks["licensing"] = STATUS_CLEAR

    if _CLEAR_ALL.search(raw) and not _FINES_ONLY.search(raw):
        out["all_clear"] = True
        checks = {k: STATUS_CLEAR for k in CORE_DEBT_KEYS}

    if re.search(r"multa", raw, re.I) and re.search(r"atrasad|pendente|tem\s+uma", raw, re.I):
        checks["fines"] = STATUS_HAS
        out["has_debts"] = True
        types = []
        if re.search(r"multa", raw, re.I):
            types.append("multa")
        if licensing:
            types.append("licenciamento")
        if ipva:
            types.append("ipva")
        if types:
            out["debt_types"] = " e ".join(types)

    if checks:
        out["debt_checks"] = checks
    return out
