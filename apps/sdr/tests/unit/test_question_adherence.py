"""Ask-field adherence of Composer questions."""

from __future__ import annotations

from sdr.domain.question_adherence import classify_question_field, evaluate_adherence
from sdr.domain.vehicle_roles import format_vehicle_label
from sdr.domain.vendor_summary import validate_summary_against_authorized


def test_debts_question_is_not_expectation() -> None:
    q = "Você já tem alguma expectativa de valor para essa troca?"
    assert classify_question_field(q) == "trade_price_expectation"
    report = evaluate_adherence(
        [q],
        "trade_has_debts",
        action="ask_info",
    )
    assert report["match"] is False


def test_debts_question_matches_debts_field() -> None:
    q = "O seu Ford Ka tem algum débito pendente, como multas ou licenciamento?"
    assert classify_question_field(q) == "trade_has_debts"
    report = evaluate_adherence([q], "trade_has_debts", action="ask_info")
    assert report["match"] is True


def test_peugeot_label_does_not_repeat_year() -> None:
    assert format_vehicle_label({"brand": "Peugeot", "model": "2008", "year": "2008"}) == "Peugeot 2008"
    assert format_vehicle_label({"brand": "Peugeot", "model": "2008", "year": "2019"}) == "Peugeot 2008 2019"


def test_paid_off_summary_cannot_say_financed() -> None:
    authorized = {
        "intent": "trade",
        "customer_vehicle": {"brand": "Volkswagen", "model": "Gol", "financing_status": "paid_off"},
        "desired_vehicle": {"brand": "Chevrolet", "model": "Onix"},
        "debt_status": "has_debts",
        "payment_method": "cash",
        "payment_applies_to": "difference",
    }
    result = validate_summary_against_authorized("O Gol está financiado.", authorized)
    assert result["pass"] is False
    assert "paid_off_described_as_financed" in result["violations"]


def test_expectation_cannot_be_store_appraisal() -> None:
    authorized = {
        "intent": "sale",
        "customer_vehicle": {"brand": "Volkswagen", "model": "Gol"},
        "price_expectation": 80000,
    }
    result = validate_summary_against_authorized(
        "O veículo está avaliado em R$ 80.000 pela loja.",
        authorized,
    )
    assert result["pass"] is False
    assert "expectation_described_as_store_appraisal" in result["violations"]


def test_purchase_summary_rejects_client_debts_absence() -> None:
    authorized = {"intent": "purchase", "desired_vehicle": {"model": "Onix"}}
    result = validate_summary_against_authorized(
        "Não há informações sobre as dívidas do cliente.",
        authorized,
    )
    assert result["pass"] is False
