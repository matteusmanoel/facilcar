"""Document commitment polarity — structural, not brand/keyword product lists.

DOCUMENTS_UNAVAILABLE: the customer cannot send proofs now (and may ask
to be called later). Never treat that as a promise to send.

DOCUMENTS_PROMISED: the customer explicitly committed to sending documents.
A weak attempt ("vou tentar") is not a firm commitment.

PROTOCOL_DETERMINISTIC: first-person send verbs vs unavailability vs hedge.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Final

COMMITMENT_CLAIM_NONE: Final = "none"
COMMITMENT_CLAIM_UNAVAILABLE: Final = "documents_unavailable"
COMMITMENT_CLAIM_PROMISED: Final = "documents_promised"
COMMITMENT_CLAIM_WEAK: Final = "documents_weak_attempt"

# Forbidden when authorized_commitment is false (PT + ES).
_UNSUPPORTED_COMMITMENT_MARKERS: Final[tuple[str, ...]] = (
    "que ia enviar",
    "que voce ia enviar",
    "que você ia enviar",
    "que ibas a enviar",
    "que ibas enviar",
    "como prometeu",
    "como voce prometeu",
    "como você prometeu",
    "como prometiste",
    "que mandaria",
    "que enviaria",
    "que ia mandar",
    "comentou que enviaria",
    "comentou que mandaria",
    "prometeu enviar",
    "prometiste enviar",
)

_FIRM_SEND = re.compile(
    r"\b("
    r"te\s+mando|te\s+envio|"
    r"vou\s+enviar|vou\s+mandar|"
    r"eu\s+envio|eu\s+mando|"
    r"mando\s+(os|as|o|a|amanha|depois)|"
    r"envio\s+(os|as|o|a|amanha|depois)"
    r")\b",
    re.IGNORECASE,
)

_WEAK_ATTEMPT = re.compile(
    r"\b("
    r"vou\s+tentar|tento\s+enviar|tento\s+mandar|"
    r"se\s+eu\s+conseguir|se\s+conseguir|"
    r"talvez\s+(eu\s+)?(envie|mande)|"
    r"vou\s+ver\s+se"
    r")\b",
    re.IGNORECASE,
)

_UNAVAILABLE = re.compile(
    r"\b("
    r"nao\s+estou\s+com|nao\s+tenho|"
    r"nao\s+consigo\s+(enviar|mandar|agora)|"
    r"depois\s+(eu\s+)?(envio|mando)|"
    r"agora\s+nao|"
    r"nao\s+tenho\s+(os\s+)?(comprovantes|documentos|docs)"
    r")\b",
    re.IGNORECASE,
)


def fold_commitment_text(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    folded = "".join(ch for ch in raw if not unicodedata.combining(ch)).lower()
    return " ".join(folded.split())


def inbound_is_weak_document_attempt(text: str) -> bool:
    return bool(_WEAK_ATTEMPT.search(fold_commitment_text(text)))


def inbound_has_firm_document_send_promise(text: str) -> bool:
    folded = fold_commitment_text(text)
    if inbound_is_weak_document_attempt(text):
        return False
    return bool(_FIRM_SEND.search(folded))


def inbound_states_documents_unavailable(text: str) -> bool:
    return bool(_UNAVAILABLE.search(fold_commitment_text(text)))


def commitment_claim_for_inbound(text: str) -> str:
    if inbound_has_firm_document_send_promise(text):
        return COMMITMENT_CLAIM_PROMISED
    if inbound_is_weak_document_attempt(text):
        return COMMITMENT_CLAIM_WEAK
    if inbound_states_documents_unavailable(text):
        return COMMITMENT_CLAIM_UNAVAILABLE
    return COMMITMENT_CLAIM_NONE


def authorized_commitment_from_claim(claim: str) -> bool:
    return claim == COMMITMENT_CLAIM_PROMISED


def outbound_has_unsupported_commitment(text: str) -> bool:
    folded = fold_commitment_text(text)
    return any(marker in folded for marker in _UNSUPPORTED_COMMITMENT_MARKERS)
