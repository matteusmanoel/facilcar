"""Vendor-facing CRM summary — human brief, not Intent/Facts dump."""

from __future__ import annotations

from sdr.domain.types import (
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
)
from sdr.domain.vendor_summary import build_vendor_summary, is_placeholder_display_name


def test_placeholder_whatsapp_name() -> None:
    assert is_placeholder_display_name("WhatsApp 0845") is True
    assert is_placeholder_display_name("Maria Silva") is False
    assert is_placeholder_display_name("") is True


def test_vendor_summary_is_human_brief_not_debug_dump() -> None:
    state = ConversationCanonicalState(
        thread_id="t1",
        customer=CustomerState(phone="554588230845", name="WhatsApp 0845"),
        intent=BusinessIntent.PURCHASE,
        facts={"desired_model": "corolla"},
    )
    summary = build_vendor_summary(state)
    assert "Intent:" not in summary
    assert "Facts:" not in summary
    assert "Actionability" not in summary
    assert "corolla" in summary.lower()
    # New narrative format — intent expressed as verb form
    assert "comprando" in summary.lower() or "compra" in summary.lower() or "interesse" in summary.lower()


def test_vendor_summary_financing_not_cash() -> None:
    state = ConversationCanonicalState(
        thread_id="t1",
        customer=CustomerState(phone="554588230845", name="Ana Souza"),
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts={
            "desired_model": "Civic",
            "deal_type": "purchase",
            "payment_method": "financing",
            "down_payment": 15000,
        },
    )
    summary = build_vendor_summary(state)
    # New narrative format: "Cliente Ana Souza." (no colon, period-terminated)
    assert "Ana Souza" in summary
    assert "financiamento" in summary.lower() or "financiada" in summary.lower()
    assert "à vista" not in summary.lower()


def test_vendor_summary_trade_is_narrative() -> None:
    state = ConversationCanonicalState(
        thread_id="t1",
        customer=CustomerState(phone="5541999999999", name="Mateus Ferreira"),
        intent=BusinessIntent.TRADE,
        facts={
            "desired_model": "Fox",
            "trade_model": "Peugeot 2008",
            "trade_year": "2019",
            "trade_color": "branco",
            "trade_has_financing": True,
            "trade_installment_value": 850,
            "trade_installments_remaining": 24,
            "trade_has_debts": False,
            "trade_price_expectation": 55000,
        },
    )
    summary = build_vendor_summary(state)
    assert "Mateus" in summary
    assert "Peugeot" in summary or "2008" in summary
    assert not summary.lstrip().startswith("-")
    assert "\n-" not in summary


def test_empty_vendor_request_summary_is_honest() -> None:
    from sdr.domain.types import HandoffSignals

    state = ConversationCanonicalState(
        thread_id="t1",
        customer=CustomerState(phone="5541999999999"),
        intent=BusinessIntent.UNKNOWN,
        signals=HandoffSignals(explicit_handoff=True),
        facts={},
    )
    summary = build_vendor_summary(state)
    low = summary.lower()
    assert "vendedor" in low
    assert "visita" not in low
    assert "horário" not in low
    assert "já reuni" not in low
