"""Internal 60-month capacity is never a spoken term."""

from __future__ import annotations

from sdr.domain.installment import INTERNAL_TERM_MONTHS, installment_capacity, is_installment_tight


def test_capacity_uses_internal_term() -> None:
    assert INTERNAL_TERM_MONTHS == 60
    assert installment_capacity(30000, 2000) == 30000 + 2000 * 60


def test_corolla_class_price_is_not_tight() -> None:
    assert is_installment_tight(
        price_cash=84900,
        down_payment=30000,
        desired_installment=2000,
    ) is False


def test_low_installment_is_tight() -> None:
    assert is_installment_tight(
        price_cash=84900,
        down_payment=5000,
        desired_installment=1000,
    ) is True
