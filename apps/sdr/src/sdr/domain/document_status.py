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
    r"n[aã]o\s+estou\s+com\s+(os\s+)?documentos|"
    r"n[aã]o\s+tenho\s+(os\s+)?documentos|"
    r"n[aã]o\s+tenho\s+(a\s+)?(cnh|holerite|comprovante)|"
    r"levo\s+(?:o\s+)?(?:resto|restante).{0,24}loja|"
    r"levo\s+(?:o\s+)?resto|"
    r"levo\s+na\s+loja|"
    r"mando\s+depois",
    re.I,
)

_REMAINDER_UTTERANCE = re.compile(
    r"levo\s+(?:o\s+)?(?:resto|restante)|"
    r"(?:o\s+)?(?:resto|restante).{0,24}loja",
    re.I,
)

_ACK_LABELS_PT = {
    "cnh": "CNH",
    "proof_of_income": "comprovante de renda",
    "proof_of_residence": "comprovante de residência",
}
_ACK_LABELS_ES = {
    "cnh": "CNH",
    "proof_of_income": "comprobante de ingresos",
    "proof_of_residence": "comprobante de domicilio",
}


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
    if _REMAINDER_UTTERANCE.search(raw):
        provided = set(mentioned)
        return {
            name: STATUS_DEFERRED
            for name in DOCUMENT_COMPONENTS
            if name not in provided
        }
    if mentioned:
        return {name: STATUS_DEFERRED for name in mentioned}
    return {name: STATUS_DEFERRED for name in DOCUMENT_COMPONENTS}


_STATUS_RANK = {
    STATUS_MISSING: 0,
    STATUS_DEFERRED: 1,
    STATUS_RECEIVED: 2,
}


def merge_document_status(
    prev: dict[str, Any] | None,
    incoming: dict[str, Any] | None,
) -> dict[str, str]:
    """Merge component status. Received never regresses to deferred/missing."""
    out = empty_document_status()
    for src in (prev, incoming):
        if not isinstance(src, dict):
            continue
        for key in DOCUMENT_COMPONENTS:
            val = src.get(key)
            if val not in {STATUS_RECEIVED, STATUS_DEFERRED, STATUS_MISSING}:
                continue
            if _STATUS_RANK[val] >= _STATUS_RANK.get(out.get(key, STATUS_MISSING), 0):
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


_ACK_DISPLAY_ORDER: tuple[str, ...] = (
    "cnh",
    "proof_of_income",
    "proof_of_residence",
)
_KIND_TO_COMPONENT = {
    "CNH": "cnh",
    "INCOME_PROOF": "proof_of_income",
    "RESIDENCE_PROOF": "proof_of_residence",
}

_PROOF_SHORT_PT = {
    "proof_of_income": "renda",
    "proof_of_residence": "residência",
}
_PROOF_SHORT_ES = {
    "proof_of_income": "ingresos",
    "proof_of_residence": "domicilio",
}


def components_from_document_kind(kind: str | None) -> list[str]:
    component = _KIND_TO_COMPONENT.get(str(kind or "").strip().upper())
    return [component] if component else []


def _join_labels(labels: list[str], *, es: bool) -> str:
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    conjunction = " y " if es else " e "
    if len(labels) == 2:
        return conjunction.join(labels)
    return f"{', '.join(labels[:-1])}{conjunction}{labels[-1]}"


def format_received_document_ack(
    received: list[str],
    *,
    name: str | None = None,
    lang: str = "pt-BR",
) -> str:
    """Deterministic commercial receipt. Never implies Storage success."""
    ordered = [c for c in _ACK_DISPLAY_ORDER if c in received]
    es = str(lang or "").lower().startswith("es")
    first = (name or "").strip().split()[0] if name else ""
    if not ordered:
        if es:
            return f"Recibí tu documento, {first}." if first else "Recibí tu documento."
        return f"Recebi seu documento, {first}." if first else "Recebi seu documento."
    if ordered == ["cnh"]:
        if es:
            return f"Recibí tu CNH, {first}." if first else "Recibí tu CNH."
        return f"Recebi sua CNH, {first}." if first else "Recebi sua CNH."

    proofs = [c for c in ordered if c != "cnh"]
    short = _PROOF_SHORT_ES if es else _PROOF_SHORT_PT
    proof_text = _join_labels([short[c] for c in proofs], es=es)
    plural = len(proofs) != 1
    if es:
        noun = "comprobantes" if plural else "comprobante"
        article = "los" if plural else "el"
        cnh_prefix = "Recibí tu CNH y " if "cnh" in ordered else "Recibí "
        return f"{cnh_prefix}{article} {noun} de {proof_text}."
    noun = "comprovantes" if plural else "comprovante"
    article = "os" if plural else "o"
    cnh_prefix = "Recebi sua CNH e " if "cnh" in ordered else "Recebi "
    return f"{cnh_prefix}{article} {noun} de {proof_text}."


def format_remaining_documents_ask(remaining: list[str], *, lang: str = "pt-BR") -> str | None:
    ordered = [c for c in DOCUMENT_COMPONENTS if c in remaining]
    if not ordered:
        return None
    es = str(lang or "").lower().startswith("es")
    if set(ordered) == {"proof_of_income", "proof_of_residence"}:
        joined = (
            "los comprobantes de ingresos y domicilio"
            if es
            else "os comprovantes de renda e residência"
        )
    else:
        labels = _ACK_LABELS_ES if es else _ACK_LABELS_PT
        joined = _join_labels([labels[c] for c in ordered], es=es)
    if es:
        return f"Si puedes, envíame también {joined} para completar la simulación."
    return (
        f"Se conseguir, pode me enviar também {joined} "
        "para completar a simulação."
    )
