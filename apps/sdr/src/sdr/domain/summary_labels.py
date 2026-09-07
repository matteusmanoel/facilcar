"""Portuguese presentation labels for the CRM summary — never expose field names."""

from __future__ import annotations

from typing import Any

DOCUMENT_LABELS: dict[str, str] = {
    "cnh": "CNH",
    "proof_of_residence": "comprovante de residência",
    "proof_of_income": "comprovante de renda",
    "documents": "documentos",
}

DOCUMENT_PHRASES: dict[str, str] = {
    "cnh": "a CNH",
    "proof_of_residence": "o comprovante de residência",
    "proof_of_income": "o comprovante de renda",
    "documents": "os documentos",
}


def document_label(field: str) -> str:
    return DOCUMENT_LABELS.get(field, field.replace("_", " "))


def document_phrase(field: str) -> str:
    return DOCUMENT_PHRASES.get(field, document_label(field))


def join_pt(parts: list[str]) -> str:
    items = [p for p in parts if p]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} e {items[1]}"
    return f"{', '.join(items[:-1])} e {items[-1]}"


def as_int(value: object) -> int | None:
    if value is None or value is True or value is False or value == "":
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(float(str(value).replace("R$", "").strip().replace(" ", "").replace(",", ".")))
    except (TypeError, ValueError):
        return None


def parcelas_label(count: Any) -> str | None:
    n = as_int(count)
    if n is None:
        return None
    if n == 1:
        return "1 parcela"
    return f"{n} parcelas"


def format_money(value: object) -> str | None:
    """Natural money: R$ 40 mil, R$ 1.800, R$ 850."""
    n = as_int(value)
    if n is None:
        return None
    if n >= 1000 and n % 1000 == 0:
        return f"R$ {n // 1000} mil"
    return f"R$ {n:,}".replace(",", ".")


def format_km(value: object) -> str | None:
    n = as_int(value)
    if n is None:
        return None
    if n >= 1000 and n % 1000 == 0:
        return f"{n // 1000} mil km"
    return f"{n:,} km".replace(",", ".")


def difference_payment_label(method: str | None, applies_to: str | None) -> str | None:
    pay = str(method or "").lower()
    if applies_to != "difference":
        if pay == "cash":
            return "à vista"
        if pay == "financing":
            return "financiado"
        return None
    if pay == "cash":
        return "diferença à vista"
    if pay == "financing":
        return "diferença financiada"
    return None


def docs_deferred_sentence(fields: list[str]) -> str | None:
    """Natural Portuguese for deferred simulation documents."""
    keys = [k for k in fields if k]
    if not keys:
        return None
    phrases = [document_phrase(k) for k in keys]
    cap = join_pt(phrases)
    if not cap:
        return None
    cap = cap[0].upper() + cap[1:]
    verb = "ficou" if len(keys) == 1 else "ficaram"
    return f"{cap} {verb} para envio posterior."


def docs_received_sentence(fields: list[str]) -> str | None:
    keys = [k for k in fields if k]
    if not keys:
        return None
    phrases = [document_phrase(k) for k in keys]
    cap = join_pt(phrases)
    cap = cap[0].upper() + cap[1:]
    if len(keys) == 1 and keys[0] == "cnh":
        return f"{cap} já foi recebida."
    verb = "foi recebido" if len(keys) == 1 else "foram recebidos"
    return f"{cap} já {verb}."
