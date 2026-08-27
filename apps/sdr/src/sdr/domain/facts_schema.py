"""Canonical TurnFacts vocabulary — single authority for fact keys and values.

LLM structured output may use aliases; before TurnFacts enters merge, every
key/value passes through ``normalize_facts``. Unknown keys are rejected
(returned in ``rejected``) and never enter canonical state.

Design rules
------------
- Product vocabulary (brands, models, categories) is NEVER hardcoded here.
- Monetary fields are normalized to numeric values generically.
- Free-text vehicle descriptions are preserved as ``desired_vehicle_text``
  when category/propulsion cannot be safely decomposed.
- Omission / unknown values never overwrite prior valid values (merge layer).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from sdr.domain.engine_displacement import (
    as_engine_list,
    engine_list_for_json,
    sanitize_engine_fact_against_source,
)

# ---------------------------------------------------------------------------
# Authoritative allowed keys (canonical state.facts)
# ---------------------------------------------------------------------------

CANONICAL_FACT_KEYS: frozenset[str] = frozenset(
    {
        # Desired vehicle (purchase interest)
        "desired_model",
        "desired_vehicle_text",  # free-text when taxonomy cannot decompose
        "desired_engine_displacement_liters",  # optional; never a triage question
        "desired_engine_flexible",  # explicit extra-engine acceptance; not asked
        "desired_engine_any",  # unconstrained displacement; not asked
        "brand",
        "category",
        "vehicle_type",  # propulsion/type when confidently known
        "color",
        "year",
        # Budget / money
        "budget",
        "max_price",
        "down_payment",
        "asking_price",
        "amount_needed",
        "vehicle_value",
        "monthly_income",
        # Preferences
        "use_type",
        "payment_type",
        "timeline",
        "city",
        "name",
        # Own vehicle (sale / trade / refinance / consignment)
        "vehicle_model",
        "vehicle_year",
        "trade_model",
        "trade_year",
        "sell_model",
        "sell_year",
        "mileage",
        "leave_at_store",
        "vehicle_status",
    }
)

# Incoming LLM / heuristic aliases → canonical key.
FACT_KEY_ALIASES: dict[str, str] = {
    "budget_max": "budget",
    "max_budget": "budget",
    "price_range": "budget",
    "valor": "budget",
    "faixa_valor": "budget",
    "usage": "use_type",
    "use": "use_type",
    "vehicle_interest": "desired_vehicle_text",
    "desired_vehicle": "desired_vehicle_text",
    "model": "desired_model",
    "brand_model": "desired_model",
    "engine": "desired_engine_displacement_liters",
    "engine_displacement": "desired_engine_displacement_liters",
    "motorizacao": "desired_engine_displacement_liters",
    "cilindrada": "desired_engine_displacement_liters",
    "engine_flexible": "desired_engine_flexible",
    "engine_any": "desired_engine_any",
    "any_engine": "desired_engine_any",
    "entrada": "down_payment",
    "desired_price": "asking_price",
    "raise_amount": "amount_needed",
    "valor_levantar": "amount_needed",
    "approx_value": "vehicle_value",
    "income": "monthly_income",
    "km": "mileage",
    "type": "vehicle_type",
    "intent_detail": "desired_vehicle_text",  # free-text detail, not a signal
}

# Fields that must be numeric after normalization.
MONEY_KEYS: frozenset[str] = frozenset(
    {
        "budget",
        "max_price",
        "down_payment",
        "asking_price",
        "amount_needed",
        "vehicle_value",
        "monthly_income",
    }
)

# Known short propulsion / type tokens (generic, not product brands).
# Multi-token free text on vehicle_type is remapped to desired_vehicle_text.
_PROPULSION_OR_TYPE_TOKENS: frozenset[str] = frozenset(
    {
        "flex",
        "gasolina",
        "etanol",
        "diesel",
        "eletrico",
        "eléctrico",
        "hibrido",
        "híbrido",
        "manual",
        "automatico",
        "automático",
        "cvt",
    }
)

_MONEY_RE = re.compile(
    r"(?:r\$\s*)?(\d[\d.,]*)\s*(mil|k)?",
    re.IGNORECASE,
)


def resolve_fact_key(raw_key: str) -> str | None:
    """Map alias → canonical key, or return key if already canonical.

    Returns None when the key is not allowed.
    """
    key = (raw_key or "").strip().lower()
    if not key:
        return None
    if key in FACT_KEY_ALIASES:
        key = FACT_KEY_ALIASES[key]
    if key in CANONICAL_FACT_KEYS:
        return key
    return None


def normalize_money_value(raw: Any) -> float | int | None:
    """Parse monetary strings generically: '15 mil', 'R$ 15.000', '15000' → number."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return int(raw) if float(raw).is_integer() else float(raw)

    text = str(raw).strip().lower()
    if not text or text in {"unknown", "n/a", "na", "?"}:
        return None

    text = text.replace("r$", "").strip()
    m = _MONEY_RE.search(text)
    if not m:
        return None

    num_raw = m.group(1).replace(".", "").replace(",", ".")
    try:
        value = float(num_raw)
    except ValueError:
        return None

    suffix = (m.group(2) or "").lower()
    if suffix in ("mil", "k"):
        value *= 1000

    if value.is_integer():
        return int(value)
    return value


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _looks_like_free_vehicle_text(value: str) -> bool:
    """True when value is multi-token free description, not a short type token."""
    tokens = value.lower().split()
    if len(tokens) >= 2:
        return True
    if len(tokens) == 1 and tokens[0] not in _PROPULSION_OR_TYPE_TOKENS:
        # Single unknown token — still acceptable as vehicle_type OR free text.
        # Prefer free text when it is not a known propulsion token.
        return True
    return False


def normalize_facts(
    raw_facts: dict[str, Any],
    *,
    source_text: str | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Normalize fact keys/values into the canonical vocabulary.

    Returns ``(canonical_facts, rejected_keys)``.
    Unknown keys are listed in ``rejected_keys`` and excluded from the result.
    """
    out: dict[str, Any] = {}
    rejected: list[str] = []

    for raw_key, raw_value in raw_facts.items():
        if raw_key.startswith("_"):
            rejected.append(raw_key)
            continue

        canonical = resolve_fact_key(str(raw_key))
        if canonical is None:
            rejected.append(str(raw_key))
            continue

        if raw_value is None:
            continue
        if isinstance(raw_value, str) and not raw_value.strip():
            continue
        if isinstance(raw_value, str) and raw_value.strip().lower() in {
            "unknown",
            "n/a",
            "na",
            "?",
        }:
            continue

        value: Any = raw_value

        # Remap free-text vehicle_type → desired_vehicle_text.
        if canonical == "vehicle_type" and isinstance(value, str):
            cleaned = _normalize_whitespace(value)
            if _looks_like_free_vehicle_text(cleaned):
                # Prefer desired_vehicle_text; do not invent category/propulsion.
                if "desired_vehicle_text" not in out:
                    out["desired_vehicle_text"] = cleaned
                continue
            value = cleaned.lower()

        if canonical == "desired_engine_displacement_liters":
            engines = as_engine_list(value)
            if source_text:
                engines = sanitize_engine_fact_against_source(engines, source_text)
            serialized = engine_list_for_json(engines)
            if serialized is None:
                rejected.append(f"{raw_key}:invalid_engine")
                continue
            value = serialized
        elif canonical in {"desired_engine_flexible", "desired_engine_any"}:
            if isinstance(value, str):
                value = value.strip().lower() in {"true", "1", "yes", "sim"}
            else:
                value = bool(value)
            if not value:
                continue
        elif canonical in MONEY_KEYS:
            money = normalize_money_value(value)
            if money is None:
                # Malformed money — reject this value, do not poison state.
                rejected.append(f"{raw_key}:malformed_money")
                continue
            value = money
        elif isinstance(value, str):
            value = _normalize_whitespace(value)

        # First write wins for same canonical key within one turn
        # (aliases may collide; prefer first non-empty).
        if canonical not in out:
            out[canonical] = value

    return out, rejected


def is_pure_greeting(text: str) -> bool:
    """True only when the entire normalized message is a greeting.

    ``Oi, gostaria de saber...`` must return False.
    ``Olá`` / ``Bom dia!`` must return True.
    """
    if not text or not str(text).strip():
        return False
    normalized = unicodedata.normalize("NFKC", str(text))
    low = normalized.strip().lower()
    # Strip trailing punctuation / emoji spacing only — not mid-message content.
    low = re.sub(r"[!?.…,;:\s]+$", "", low).strip()
    low = re.sub(r"^[!?.…,;:\s]+", "", low).strip()
    greetings = frozenset(
        {
            "oi",
            "olá",
            "ola",
            "oie",
            "oii",
            "hello",
            "hi",
            "hey",
            "hola",
            "bom dia",
            "boa tarde",
            "boa noite",
            "buen dia",
            "buenas",
            "buenas tardes",
            "buenas noches",
            "tudo bem",
            "tudo bom",
            "eai",
            "e aí",
            "salve",
        }
    )
    return low in greetings
