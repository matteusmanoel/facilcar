"""Factual CRM summary validation."""

from __future__ import annotations

from sdr.domain.types import BusinessIntent, ConversationCanonicalState, CustomerState
from sdr.domain.vendor_summary import compose_vendor_summary, validate_summary_against_authorized


def test_sale_summary_rejects_trade_language() -> None:
    ok = validate_summary_against_authorized(
        "Bruno também está interessado em realizar a troca pelo mesmo modelo.",
        {"intent": "sale", "desired_vehicle": {}, "customer_vehicle": {"model": "Corolla", "brand": "Toyota"}},
    )
    assert ok["pass"] is False
    assert "sale_summary_mentions_trade" in ok["violations"]


def test_deferred_docs_cannot_be_ready() -> None:
    ok = validate_summary_against_authorized(
        "Os documentos necessários para a análise de crédito estão prontos.",
        {"intent": "purchase_financing", "documents_deferred": ["cnh"], "desired_vehicle": {"model": "HB20"}},
    )
    assert ok["pass"] is False


def test_honda_corolla_rejected() -> None:
    ok = validate_summary_against_authorized(
        "Cliente Sérgio Pires quer um Honda Corolla prata.",
        {
            "intent": "purchase",
            "desired_vehicle": {"model": "Corolla", "brand": "Toyota"},
            "customer_vehicle": {},
        },
    )
    assert ok["pass"] is False


def test_deterministic_sale_summary_has_no_trade() -> None:
    state = ConversationCanonicalState(
        thread_id="t",
        customer=CustomerState(phone="1", name="Bruno Azevedo"),
        intent=BusinessIntent.SALE,
        facts={
            "customer_vehicle": {
                "model": "Corolla",
                "brand": "Toyota",
                "year": "2020",
                "color": "prata",
                "mileage": 50000,
                "financing_status": "paid_off",
                "debt_status": "clear",
                "price_expectation": 80000,
            },
            "name": "Bruno Azevedo",
        },
    )
    result = compose_vendor_summary(state)
    assert "troca" not in result.text.lower()
    assert result.validation.get("pass") is True
