"""Protocol-deterministic photo request — not a product-term heuristic.

Asking to send listing photos is a capability request (like visit / vendor),
not open commercial language. Code owns the evidence; the LLM may agree but
cannot invent the signal without inbound evidence.
"""

from __future__ import annotations

import re
import unicodedata

# Capability request to send listing photos on the current WhatsApp thread.
_PHOTO_REQUEST = re.compile(
    r"(?:"
    r"\btem\s+fotos?\b|"
    r"\btem\s+imagens?\b|"
    r"(?:manda|mandar|enviar|envia|mostra|mostrar|pode\s+mandar)"
    r".{0,24}(?:fotos?|imagens?|fotinhas)|"
    r"(?:fotos?|imagens?).{0,24}(?:aqui|whatsapp|por\s+favor|pfv|pra\s+mim)"
    r")",
    re.I,
)


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")


def has_photo_request_evidence(text: str) -> bool:
    """True when inbound asks to send the listing photos on this thread."""
    return bool(_PHOTO_REQUEST.search(_normalize(text)))
