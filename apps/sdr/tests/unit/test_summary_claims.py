"""CRM summary claims must be extracted and authorized."""

from __future__ import annotations

from sdr.domain.summary_propositions import (
    detect_claims,
    text_has_factual_assertions,
    validate_text_against_propositions,
)
from sdr.domain.types import BusinessIntent, ConversationCanonicalState, CustomerState
from sdr.domain.vendor_summary import compose_vendor_summary, validate_summary_against_authorized


def test_factual_summary_with_empty_claims_is_rejected() -> None:
    text = (
        "Paulo Lima pretende trocar seu Peugeot 2008 2019 branco, com 85 mil km, "
        "por um Hyundai HB20. O veículo está financiado."
    )
    assert text_has_factual_assertions(text)
    result = validate_text_against_propositions(
        text,
        {"intent": "trade", "desired_vehicle": {}, "customer_vehicle": {}},
    )
    # Claims are extracted; with no authorizing propositions they still fail.
    assert result["pass"] is False
    empty = validate_text_against_propositions(
        "Há 85 mil km no hodômetro e o ano é 2019, com a CNH.",
        {"intent": "unknown"},
    )
    blob = "Há 85 mil km no hodômetro e o ano é 2019, com a CNH."
    assert text_has_factual_assertions(blob)
    empty = validate_text_against_propositions(blob, {"intent": "unknown"})
    assert empty["pass"] is False
    if not empty.get("claims"):
        assert "factual_summary_without_extracted_claims" in empty["violations"]


def test_paid_off_versus_financed_claims() -> None:
    authorized = {
        "intent": "sale",
        "name": "Bruno",
        "customer_vehicle": {
            "brand": "Toyota",
            "model": "Corolla",
            "financing_status": "paid_off",
        },
    }
    bad = validate_summary_against_authorized("O Corolla está financiado.", authorized)
    assert bad["pass"] is False
    good = validate_summary_against_authorized("Bruno deseja vender o Corolla quitado.", authorized)
    assert "paid_off_described_as_financed" not in good["violations"]
    claims = detect_claims("O veículo está quitado.", authorized)
    assert any(c.get("value") == "paid_off" for c in claims)


def test_debt_versus_no_debt_claims() -> None:
    authorized = {
        "intent": "sale",
        "customer_vehicle": {"model": "Corolla", "brand": "Toyota"},
        "debt_status": "has_debts",
    }
    bad = validate_summary_against_authorized("O Corolla está sem débitos.", authorized)
    assert bad["pass"] is False
    clear = {
        **authorized,
        "debt_status": "clear",
        "customer_vehicle": {**authorized["customer_vehicle"], "debt_status": "clear"},
    }
    good = validate_summary_against_authorized("O Corolla está sem débitos informados.", clear)
    assert "debts_described_as_clear" not in good["violations"]


def test_expectation_versus_appraisal() -> None:
    authorized = {
        "intent": "sale",
        "customer_vehicle": {"brand": "Toyota", "model": "Corolla"},
        "price_expectation": 80000,
    }
    bad = validate_summary_against_authorized(
        "O veículo está avaliado em R$ 80 mil pela loja.",
        authorized,
    )
    assert bad["pass"] is False
    good = validate_summary_against_authorized(
        "Ele espera aproximadamente R$ 80 mil pelo veículo.",
        authorized,
    )
    assert "expectation_described_as_store_appraisal" not in good["violations"]


def test_difference_cash_versus_financed() -> None:
    cash = {
        "intent": "trade",
        "payment_method": "cash",
        "payment_applies_to": "difference",
        "desired_vehicle": {"model": "HB20", "brand": "Hyundai"},
        "customer_vehicle": {"model": "Peugeot 2008", "brand": "Peugeot"},
    }
    bad = validate_summary_against_authorized(
        "Ele pretende financiar a diferença.",
        cash,
    )
    assert bad["pass"] is False
    fin = {**cash, "payment_method": "financing"}
    good = validate_summary_against_authorized(
        "Ele pretende financiar a diferença.",
        fin,
    )
    assert "difference_financing_described_as_cash" not in good["violations"]


def test_visit_pending_versus_marked() -> None:
    authorized = {
        "intent": "sale",
        "visit_preferred_time": "terça-feira, 8/09, às 9h30",
        "visit_pending_vendor_confirm": True,
        "customer_vehicle": {"model": "Corolla", "brand": "Toyota"},
    }
    bad = validate_summary_against_authorized(
        "A visita está marcada para terça-feira. O vendedor confirmará.",
        authorized,
    )
    assert bad["pass"] is False
    assert "visit_described_as_confirmed" in bad["violations"]
    good = validate_summary_against_authorized(
        "A preferência de visita foi registrada para terça-feira, 8/09, às 9h30, "
        "pendente de confirmação do vendedor.",
        authorized,
    )
    assert "visit_described_as_confirmed" not in good["violations"]


def test_documents_deferred_versus_received() -> None:
    authorized = {
        "intent": "purchase_financing",
        "documents_applicable": True,
        "documents_deferred": ["cnh"],
        "desired_vehicle": {"model": "HB20", "brand": "Hyundai"},
    }
    bad = validate_summary_against_authorized(
        "Os documentos necessários para a análise de crédito estão prontos.",
        authorized,
    )
    assert bad["pass"] is False
    good = validate_summary_against_authorized(
        "A CNH ficou para envio posterior.",
        authorized,
    )
    assert "deferred_documents_described_as_ready" not in good["violations"]


def test_inapplicable_documents_for_sale_and_purchase() -> None:
    sale = validate_summary_against_authorized(
        "Bruno deseja vender o Corolla. Documentos não recebidos.",
        {
            "intent": "sale",
            "documents_applicable": False,
            "customer_vehicle": {"model": "Corolla", "brand": "Toyota"},
        },
    )
    assert sale["pass"] is False
    purchase = validate_summary_against_authorized(
        "Lucas pretende comprar um Onix. Sem pendências de documentos.",
        {"intent": "purchase", "documents_applicable": False, "desired_vehicle": {"model": "Onix"}},
    )
    assert purchase["pass"] is False


def test_deterministic_sale_summary_passes_claim_coverage() -> None:
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
        visit_preferred_time="terça-feira, 8/09, às 9h30",
    )
    result = compose_vendor_summary(state)
    assert result.validation.get("pass") is True
    assert result.validation.get("claims")
    assert "marcada" not in result.text.lower()
    assert "documentos" not in result.text.lower()
    assert "parcela(s)" not in result.text
    for link in result.validation.get("claim_links") or []:
        assert link.get("match") is True, link
