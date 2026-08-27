"""Canonical commercial engine displacement (liters).

LLM extracts the semantic role of a number. This module normalizes and validates:
- Decimal with one fractional digit
- range 0.6–8.0
- reject ambiguous / non-engine quantities (price, installment, rate)
- never infer a value when the number is not clearly displacement
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

ENGINE_MIN = Decimal("0.6")
ENGINE_MAX = Decimal("8.0")
ENGINE_QUANTUM = Decimal("0.1")

# Commercial token, e.g. 1.0 / 1.4 / 1.8 / 2.0
_DISPLACEMENT_TOKEN = r"\b([1-8][.,][0-9])\b"

# Window around a match that indicates the number is NOT engine displacement.
_NON_ENGINE_MARKERS = (
    "%",
    "taxa",
    "juros",
    "parcela",
    "r$",
    "rs",
    "km",
    " mil",
    "mil ",
    "entrada",
    "orçamento",
    "orcamento",
    "budget",
    "reais",
    "preço",
    "preco",
    "valor",
)

_FLEXIBLE_MARKERS = (
    "também",
    "tambem",
    "pode ser",
    "ou também",
)

_ANY_ENGINE_MARKERS = (
    "qualquer motor",
    "qualquer cilindr",
)


def _to_quantum(value: Decimal) -> Decimal | None:
    quantized = value.quantize(ENGINE_QUANTUM)
    if abs(quantized - value) > Decimal("0.0000001"):
        return None
    if quantized < ENGINE_MIN or quantized > ENGINE_MAX:
        return None
    return quantized


def normalize_engine_displacement(raw: Any) -> Decimal | None:
    """Normalize a single candidate to Decimal(x.x) or None.

    Compound labels like ``1.0 TSI`` are rejected here (qualifiers do not belong
    on this field). Callers that split import text should pass only the numeric token.
    """
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, Decimal):
        return _to_quantum(raw)
    if isinstance(raw, int):
        return None  # integers like 2 are years/counts, not commercial displacement
    if isinstance(raw, float):
        try:
            return _to_quantum(Decimal(str(raw)))
        except (InvalidOperation, ValueError):
            return None

    text = str(raw).strip().replace(",", ".")
    if not text or text.lower() in {"unknown", "n/a", "na", "?"}:
        return None
    # Reject compound commercial labels (TSI, Turbo, Fire Flex).
    if any(ch.isalpha() for ch in text):
        return None
    if text.count(".") != 1:
        return None
    try:
        value = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    return _to_quantum(value)


def as_engine_list(raw: Any) -> list[Decimal]:
    """Coerce a fact value into a unique sorted list of displacements."""
    if raw is None or isinstance(raw, bool):
        return []
    if isinstance(raw, list):
        out: list[Decimal] = []
        for item in raw:
            normalized = normalize_engine_displacement(item)
            if normalized is not None and normalized not in out:
                out.append(normalized)
        return sorted(out)
    if isinstance(raw, str) and "," in raw:
        return as_engine_list([part.strip() for part in raw.split(",")])
    single = normalize_engine_displacement(raw)
    return [single] if single is not None else []


def engine_list_for_json(values: list[Decimal]) -> list[float] | float | None:
    """Serialize for canonical facts: one value as float, several as list."""
    if not values:
        return None
    as_floats = [float(v) for v in values]
    if len(as_floats) == 1:
        return as_floats[0]
    return as_floats


def format_engine_token(value: Decimal) -> str:
    return f"{value:.1f}"


def is_engine_flexible_utterance(text: str) -> bool:
    """True when the customer adds another engine without dropping the previous."""
    if is_any_engine_utterance(text):
        return False
    low = (text or "").lower()
    return any(marker in low for marker in _FLEXIBLE_MARKERS)


def is_any_engine_utterance(text: str) -> bool:
    """True when the customer unconstrained the displacement filter."""
    low = (text or "").lower()
    return any(marker in low for marker in _ANY_ENGINE_MARKERS)


def _window_is_non_engine(text: str, start: int, end: int) -> bool:
    window = text[max(0, start - 24) : min(len(text), end + 24)].lower()
    return any(marker in window for marker in _NON_ENGINE_MARKERS)


def extract_engine_displacements_from_text(text: str) -> list[Decimal]:
    """Deterministic candidates from inbound text, excluding non-engine quantities."""
    if not text or not str(text).strip():
        return []
    found: list[Decimal] = []
    for match in re.finditer(_DISPLACEMENT_TOKEN, text):
        if _window_is_non_engine(text, match.start(), match.end()):
            continue
        normalized = normalize_engine_displacement(match.group(1).replace(",", "."))
        if normalized is not None and normalized not in found:
            found.append(normalized)
    return found


def sanitize_engine_fact_against_source(
    proposed: Any,
    source_text: str,
) -> list[Decimal]:
    """Keep LLM-proposed displacements only when they also survive source validation.

    If the source contains the same token only in a non-engine window, drop it.
    If the LLM proposed a value that never appears as a valid candidate, drop it
    unless the source has no ``d.d`` tokens at all (trust the already-normalized
    fact from a previous turn / structured value without re-parsing the new text).
    """
    proposed_list = as_engine_list(proposed)
    if not proposed_list:
        return []
    if not source_text or not str(source_text).strip():
        return proposed_list

    has_token = re.search(_DISPLACEMENT_TOKEN, source_text) is not None
    from_text = extract_engine_displacements_from_text(source_text)
    if has_token:
        # Token present: keep only values that survived non-engine rejection.
        return [value for value in proposed_list if value in from_text]
    # Follow-up without a d.d token — leave structured proposal for merge.
    return proposed_list
