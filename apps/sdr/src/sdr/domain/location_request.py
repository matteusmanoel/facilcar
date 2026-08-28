"""Protocol-deterministic store-location request.

Asking where the store is is a capability request (like photos), not open
commercial language. Code owns the evidence; Decision must execute send_location.
"""

from __future__ import annotations

import re
import unicodedata

_LOCATION_REQUEST = re.compile(
    r"(?:"
    r"onde\s+fica|"
    r"onde\s+voc[eê]s\s+(?:ficam|est[aã]o)|"
    r"endere[cç]o|"
    r"localiza[cç][aã]o|"
    r"como\s+chego|"
    r"como\s+fa[cç]o\s+pra\s+(?:chegar|ir)|"
    r"\bmaps\b|"
    r"google\s+maps|"
    r"pin\s+da\s+loja|"
    r"manda(?:r)?\s+(?:o\s+)?endere[cç]o"
    r")",
    re.I,
)


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")


def has_store_location_request_evidence(text: str) -> bool:
    """True when inbound asks for the store address / location pin."""
    return bool(_LOCATION_REQUEST.search(_normalize(text)))
