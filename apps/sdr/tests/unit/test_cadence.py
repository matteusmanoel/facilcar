"""Cadence map is protocol, not product-term heuristics."""

from __future__ import annotations

from sdr.domain.cadence import CadenceMode, cadence_for
from sdr.domain.types import Action


def test_first_contact_is_engage() -> None:
    assert cadence_for(action=Action.SHOW_OFFERS, should_introduce=True, ack_kind=None) == (
        CadenceMode.ENGAGE_QUESTION
    )


def test_deal_purchase_is_recap() -> None:
    assert cadence_for(
        action=Action.ASK_INFO,
        should_introduce=False,
        ack_kind="deal_purchase",
    ) == CadenceMode.RECAP_QUESTION


def test_visit_is_indirect() -> None:
    assert cadence_for(
        action=Action.REGISTER_VISIT_INTEREST,
        should_introduce=False,
        ack_kind=None,
    ) == CadenceMode.INDIRECT


def test_installment_tight_is_indirect() -> None:
    assert cadence_for(
        action=Action.ASK_INFO,
        should_introduce=False,
        ack_kind=None,
        reason_code="installment_tight",
    ) == CadenceMode.INDIRECT
