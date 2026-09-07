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
        "desired_vehicle",  # nested role object (canonical)
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
        "desired_installment",
        "asking_price",
        "amount_needed",
        "vehicle_value",
        "monthly_income",
        # Preferences
        "use_type",
        "payment_method",
        "timeline",
        "city",
        "name",
        # Own vehicle (sale / trade / refinance / consignment)
        "customer_vehicle",  # nested role object (canonical)
        "debt_status",
        "debt_checks",
        "payment_applies_to",
        "documents_received",
        "documents_deferred",
        "document_status",
        "vehicle_model",
        "vehicle_year",
        "trade_model",
        "trade_year",
        "sell_model",
        "sell_year",
        "mileage",
        "leave_at_store",
        "vehicle_status",
        # Commercial mode: purchase vs trade (never inferred from mere "quero comprar").
        "deal_type",
        # Own vehicle — trade-in / sale / consignment / refinancing extended fields
        "trade_color",             # colour of vehicle being traded / sold
        "trade_has_financing",     # bool: active financing on the trade-in vehicle
        "trade_installment_value", # current monthly installment value (R$)
        "trade_installments_remaining",  # number of installments still due
        "trade_has_debts",         # bool: unpaid fines / licensing fees
        "trade_debt_type",         # free-text description of debts
        "trade_price_expectation", # client's expected value for own vehicle (R$)
        "trade_in_owner_is_client", # bool: document in client's name (vs third party)
        "trade_renavam",           # RENAVAM registration number of trade-in vehicle
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
    "parcela": "desired_installment",
    "desired_payment": "desired_installment",
    "monthly_payment": "desired_installment",
    "valor_parcela": "desired_installment",
    "desired_price": "asking_price",
    "raise_amount": "amount_needed",
    "valor_levantar": "amount_needed",
    "approx_value": "vehicle_value",
    "income": "monthly_income",
    "km": "mileage",
    "type": "vehicle_type",
    "intent_detail": "desired_vehicle_text",  # free-text detail, not a signal
    "compra_ou_troca": "deal_type",
    "deal_mode": "deal_type",
    "payment_type": "payment_method",
    "financing": "payment_method",
    "pagamento": "payment_method",
    # Trade-in / own-vehicle extended aliases
    "renavam": "trade_renavam",
    "cor_veiculo": "trade_color",
    "cor_carro": "trade_color",
    "vehicle_color": "trade_color",
    "financiado": "trade_has_financing",
    "tem_financiamento": "trade_has_financing",
    "has_financing": "trade_has_financing",
    "parcela_atual": "trade_installment_value",
    "valor_parcela_atual": "trade_installment_value",
    "installment_value": "trade_installment_value",
    "parcelas_restantes": "trade_installments_remaining",
    "remaining_installments": "trade_installments_remaining",
    "debitos": "trade_has_debts",
    "tem_debitos": "trade_has_debts",
    "has_debts": "trade_has_debts",
    "tipo_debito": "trade_debt_type",
    "debt_type": "trade_debt_type",
    "valor_esperado": "trade_price_expectation",
    "expectativa_valor": "trade_price_expectation",
    "price_expectation": "trade_price_expectation",
    "owner_is_client": "trade_in_owner_is_client",
    "documento_no_nome": "trade_in_owner_is_client",
}

# Fields that must be numeric after normalization.
MONEY_KEYS: frozenset[str] = frozenset(
    {
        "budget",
        "max_price",
        "down_payment",
        "desired_installment",
        "asking_price",
        "amount_needed",
        "vehicle_value",
        "monthly_income",
        "trade_installment_value",
        "trade_price_expectation",
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


_DEAL_TYPE_PURCHASE = frozenset(
    {"purchase", "compra", "comprar", "buy", "buying", "so compra", "só compra"}
)
_DEAL_TYPE_TRADE = frozenset(
    {"trade", "troca", "trocar", "trade-in", "trade_in", "na troca"}
)
_DEAL_TYPE_BOTH = frozenset({"both", "ambos", "compra e troca", "compra_e_troca"})


def _normalize_deal_type(raw: Any) -> str | None:
    """Canonical deal_type: purchase | trade | both. Generic purchase interest is not this."""
    if raw is None:
        return None
    text = _normalize_whitespace(str(raw)).lower()
    if not text or text in {"unknown", "n/a", "na", "?"}:
        return None
    if text in _DEAL_TYPE_BOTH or "e troca" in text or "and trade" in text:
        return "both"
    if text in _DEAL_TYPE_TRADE:
        return "trade"
    if text in _DEAL_TYPE_PURCHASE:
        return "purchase"
    return None


_PAYMENT_CASH = frozenset(
    {"cash", "vista", "a vista", "à vista", "avista", "dinheiro", "pix"}
)
_PAYMENT_FINANCING = frozenset(
    {
        "financing",
        "financ",
        "financiar",
        "financiado",
        "financiamento",
        "compra financiada",
        "purchase_financing",
    }
)


def _normalize_payment_method(raw: Any) -> str | None:
    """Canonical payment_method: cash | financing."""
    if raw is None:
        return None
    text = _normalize_whitespace(str(raw)).lower()
    if not text or text in {"unknown", "n/a", "na", "?"}:
        return None
    if text in _PAYMENT_FINANCING or "financ" in text:
        return "financing"
    if text in _PAYMENT_CASH or "vista" in text:
        return "cash"
    return None


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

        if canonical in {"desired_vehicle", "customer_vehicle", "debt_checks", "document_status"} and isinstance(value, dict):
            if canonical not in out:
                out[canonical] = {
                    k: v for k, v in value.items() if v is not None and v != ""
                }
            elif isinstance(out.get(canonical), dict):
                out[canonical] = {**out[canonical], **{
                    k: v for k, v in value.items() if v is not None and v != ""
                }}
            continue

        if canonical == "documents_deferred":
            if isinstance(value, str):
                value = value.strip().lower() in {"true", "1", "yes", "sim"}
            else:
                value = bool(value)
            if not value:
                continue

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
        elif canonical in {"trade_has_financing", "trade_has_debts", "trade_in_owner_is_client"}:
            # Boolean fields — accept string "true"/"false"/"sim"/"não"/"yes"/"no".
            if isinstance(value, bool):
                pass  # already bool
            elif isinstance(value, str):
                low = value.strip().lower()
                if low in {"true", "sim", "yes", "1", "s", "y"}:
                    value = True
                elif low in {"false", "não", "nao", "no", "0", "n"}:
                    value = False
                else:
                    rejected.append(f"{raw_key}:invalid_bool")
                    continue
            else:
                value = bool(value)
        elif canonical in MONEY_KEYS:
            money = normalize_money_value(value)
            if money is None:
                # Malformed money — reject this value, do not poison state.
                rejected.append(f"{raw_key}:malformed_money")
                continue
            value = money
        elif canonical == "trade_installments_remaining":
            # Integer count — accept numeric or short text like "24 parcelas"
            if isinstance(value, int):
                pass
            elif isinstance(value, float):
                value = int(value)
            elif isinstance(value, str):
                import re as _re
                m = _re.search(r"\b(\d+)\b", value)
                if m:
                    value = int(m.group(1))
                else:
                    rejected.append(f"{raw_key}:invalid_count")
                    continue
            else:
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    rejected.append(f"{raw_key}:invalid_count")
                    continue
        elif canonical == "deal_type":
            mapped = _normalize_deal_type(value)
            if mapped is None:
                rejected.append(f"{raw_key}:invalid_deal_type")
                continue
            value = mapped
        elif canonical == "payment_method":
            mapped = _normalize_payment_method(value)
            if mapped is None:
                rejected.append(f"{raw_key}:invalid_payment_method")
                continue
            value = mapped
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
