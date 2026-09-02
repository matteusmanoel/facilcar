"""Installment affordability — internal heuristic, never spoken as a term.

A 60-month term is used only to compare desired monthly payment + down payment
against published cash price. The Composer must never mention months or
promise a parcel amount.
"""

from __future__ import annotations

from typing import Any

INTERNAL_TERM_MONTHS = 60
_TIGHT_RATIO = 0.85


def _as_number(raw: Any) -> float | None:
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def installment_capacity(
    down_payment: Any,
    desired_installment: Any,
    *,
    term_months: int = INTERNAL_TERM_MONTHS,
) -> float | None:
    monthly = _as_number(desired_installment)
    if monthly is None or monthly < 0:
        return None
    down = _as_number(down_payment) or 0.0
    return down + monthly * term_months


def is_installment_tight(
    *,
    price_cash: Any,
    down_payment: Any,
    desired_installment: Any,
) -> bool:
    """True when internal capacity is clearly below published cash price."""
    price = _as_number(price_cash)
    capacity = installment_capacity(down_payment, desired_installment)
    if price is None or price <= 0 or capacity is None:
        return False
    return capacity < price * _TIGHT_RATIO
