"""Phone / JID normalization (digits-only, BR-friendly)."""

from __future__ import annotations

import re

_NON_DIGIT = re.compile(r"\D+")


def normalize_phone(raw: str | None) -> str:
    """Strip to digits only.

    Accepts bare numbers, ``+55…``, and WhatsApp JIDs like
    ``5511999999999@s.whatsapp.net``. Empty / None → ``\"\"``.
    """
    if raw is None:
        return ""
    text = str(raw).strip()
    if not text:
        return ""
    # Drop WhatsApp / group suffixes before digit extraction.
    local = text.split("@", 1)[0]
    # Device suffix (e.g. 5511999000101:12) is not part of the phone identity.
    local = local.split(":", 1)[0]
    digits = _NON_DIGIT.sub("", local)
    return digits


def phone_from_jid(jid: str | None) -> str:
    """Alias used by ingest paths — same digits-only rule."""
    return normalize_phone(jid)
