"""Deterministic CRM summary must read as production Portuguese."""

from __future__ import annotations

from sdr.domain.summary_labels import document_phrase, parcelas_label
from sdr.domain.types import BusinessIntent, ConversationCanonicalState, CustomerState
from sdr.domain.vendor_summary import compose_vendor_summary


def _state(intent: BusinessIntent, facts: dict, **kwargs) -> ConversationCanonicalState:
    name = facts.get("name")
    return ConversationCanonicalState(
        thread_id="t",
        customer=CustomerState(phone="1", name=name),
        intent=intent,
        facts=facts,
        **kwargs,
    )


def test_parcelas_singular_and_plural() -> None:
    assert parcelas_label(1) == "1 parcela"
    assert parcelas_label(24) == "24 parcelas"


def test_document_labels_are_portuguese() -> None:
    assert document_phrase("cnh") == "a CNH"
    assert document_phrase("proof_of_residence") == "o comprovante de residência"
    assert document_phrase("proof_of_income") == "o comprovante de renda"


def test_purchase_cash_omits_documents_and_debts() -> None:
    result = compose_vendor_summary(
        _state(
            BusinessIntent.PURCHASE,
            {"desired_model": "Onix Plus", "payment_method": "cash", "name": "Lucas Rocha"},
        )
    )
    low = result.text.lower()
    assert "documentos" not in low
    assert "débito" not in low and "debito" not in low
    assert "prova_of" not in low
    assert result.validation.get("pass") is True


def test_sale_omits_documents() -> None:
    result = compose_vendor_summary(
        _state(
            BusinessIntent.SALE,
            {
                "name": "Bruno Azevedo",
                "trade_model": "Corolla",
                "trade_year": "2020",
                "trade_color": "prata",
                "mileage": 50000,
                "trade_has_financing": False,
                "trade_has_debts": False,
                "trade_price_expectation": 80000,
            },
            visit_preferred_time="terça-feira, 8/09, às 9h30",
        )
    )
    low = result.text.lower()
    assert "documentos" not in low
    assert "proof_of" not in result.text
    assert "marcada" not in low
    assert "preferência de visita" in low or "preferencia de visita" in low or "pretende visitar" in low
    assert "pendente de confirmação" not in low and "pendente de confirmacao" not in low
    assert result.validation.get("pass") is True


def test_refinancing_incomplete_does_not_invent_pendency() -> None:
    result = compose_vendor_summary(
        _state(
            BusinessIntent.REFINANCING,
            {
                "name": "Igor Teixeira",
                "trade_model": "Jeep Compass",
                "trade_year": "2022",
                "amount_needed": 30000,
            },
        )
    )
    low = result.text.lower()
    assert "sem pendências" not in low
    assert "visita" not in low
    assert "documentos" not in low
    assert "30 mil" in result.text or "30000" in result.text
    assert "complementado" not in low
    assert "handoff_ready" not in low
    assert "perfil completo" not in low
    assert "atendimento pronto" not in low
    assert result.origin == "deterministic"
    assert result.validation.get("pass") is True


def test_trade_financed_includes_desired_installment_and_deferred_docs() -> None:
    result = compose_vendor_summary(
        _state(
            BusinessIntent.TRADE,
            {
                "name": "Paulo Lima",
                "desired_model": "HB20",
                "trade_model": "Peugeot 2008",
                "trade_year": "2019",
                "trade_color": "branco",
                "mileage": 85000,
                "trade_has_financing": True,
                "trade_installment_value": 850,
                "trade_installments_remaining": 24,
                "trade_has_debts": False,
                "trade_price_expectation": 40000,
                "payment_method": "financing",
                "payment_applies_to": "difference",
                "desired_installment": 1800,
                "documents_deferred": True,
                "document_status": {
                    "cnh": "deferred",
                    "proof_of_residence": "deferred",
                    "proof_of_income": "deferred",
                },
            },
            deferred_fields=["cnh", "proof_of_residence", "proof_of_income"],
            visit_preferred_time="segunda-feira, 7/09, às 14h",
        )
    )
    text = result.text
    low = text.lower()
    assert "parcela(s)" not in text
    assert "proof_of_residence" not in text
    assert "24 parcelas" in text
    assert "1.800" in text or "1800" in text
    assert "financiar a diferença" in low
    assert "ficaram para envio posterior" in result.text
    assert "cnh" in low
    assert "comprovante de residência" in low or "comprovante de residencia" in low
    assert "envio posterior" in low
    assert "pretende visitar" in low or "preferência" in low or "preferencia" in low
    assert result.validation.get("pass") is True, result.validation.get("violations")


def test_visit_preference_is_pending() -> None:
    result = compose_vendor_summary(
        _state(
            BusinessIntent.SALE,
            {
                "name": "Bruno Azevedo",
                "trade_model": "Corolla",
                "trade_has_financing": False,
                "trade_has_debts": False,
            },
            visit_preferred_time="terça-feira, 8/09, às 9h30",
        )
    )
    low = result.text.lower()
    assert "marcada" not in low
    assert "agendada" not in low
    assert "pretende visitar" in low
    assert "pendente de confirmação" not in low and "pendente de confirmacao" not in low


def test_cnh_singular_agreement() -> None:
    result = compose_vendor_summary(
        _state(
            BusinessIntent.PURCHASE_FINANCING,
            {
                "name": "Carla Nunes",
                "desired_model": "HB20",
                "down_payment": 10000,
                "documents_deferred": True,
                "document_status": {"cnh": "deferred"},
            },
            deferred_fields=["cnh"],
        )
    )
    assert "ficou para envio posterior" in result.text
    assert "ficaram para envio posterior" not in result.text
    assert result.validation.get("pass") is True


def test_gender_neutral_expectation() -> None:
    result = compose_vendor_summary(
        _state(
            BusinessIntent.SALE,
            {
                "name": "Maria Souza",
                "trade_model": "Corolla",
                "trade_year": "2020",
                "trade_has_financing": False,
                "trade_has_debts": False,
                "trade_price_expectation": 80000,
            },
        )
    )
    low = result.text.lower()
    assert "ele espera" not in low
    assert "ela espera" not in low
    assert "expectativa informada" in low
    assert result.validation.get("pass") is True


def test_zero_down_is_financing_without_entry() -> None:
    result = compose_vendor_summary(
        _state(
            BusinessIntent.PURCHASE_FINANCING,
            {
                "name": "Lucas Rocha",
                "desired_model": "Onix",
                "down_payment": 0,
                "desired_installment": 1200,
            },
        )
    )
    low = result.text.lower()
    assert "financiar sem entrada" in low
    assert "entrada de r$ 0" not in low
    assert result.validation.get("pass") is True


def test_consignment_describes_consignment_not_appraisal() -> None:
    result = compose_vendor_summary(
        _state(
            BusinessIntent.CONSIGNMENT,
            {
                "name": "Helena Dias",
                "trade_model": "Civic",
                "trade_year": "2019",
                "leave_at_store": True,
                "trade_price_expectation": 70000,
            },
        )
    )
    low = result.text.lower()
    assert "consignação" in low or "consignacao" in low
    assert "loja para consignação" in low or "loja para consignacao" in low
    assert "para avaliação" not in low and "para avaliacao" not in low
    assert result.validation.get("pass") is True


def test_narrative_omits_internal_operational_flags() -> None:
    result = compose_vendor_summary(
        _state(
            BusinessIntent.REFINANCING,
            {
                "name": "Igor Teixeira",
                "trade_model": "Jeep Compass",
                "trade_year": "2022",
                "amount_needed": 30000,
            },
            handoff_ready=True,
            profile_complete=False,
        )
    )
    low = result.text.lower()
    assert "handoff_ready" not in low
    assert "perfil completo" not in low
    assert "atendimento pronto" not in low
    assert "complementado" not in low
    assert result.validation.get("pass") is True


def test_empty_vendor_request_is_special_deterministic_summary() -> None:
    from sdr.domain.types import HandoffSignals
    from sdr.domain.vendor_summary import (
        CLAIM_POLICY_VENDOR_REQUEST,
        ORIGIN_SPECIAL_VENDOR_REQUEST,
    )

    result = compose_vendor_summary(
        ConversationCanonicalState(
            thread_id="t",
            customer=CustomerState(phone="1"),
            intent=BusinessIntent.UNKNOWN,
            signals=HandoffSignals(explicit_handoff=True),
            facts={},
        )
    )
    assert result.origin == ORIGIN_SPECIAL_VENDOR_REQUEST
    assert result.validation.get("claim_policy") == CLAIM_POLICY_VENDOR_REQUEST
    assert result.validation.get("pass") is True
    assert "vendedor" in result.text.lower()
    assert result.used_fallback is False
    assert result.llm_attempted is False


def test_summary_llm_disabled_by_default(monkeypatch) -> None:
    from sdr.domain.vendor_summary import ORIGIN_DETERMINISTIC

    monkeypatch.setattr(
        "sdr.domain.vendor_summary._vendor_summary_llm_allowed", lambda: False
    )
    result = compose_vendor_summary(
        _state(
            BusinessIntent.PURCHASE,
            {"desired_model": "Onix Plus", "payment_method": "cash", "name": "Lucas Rocha"},
        )
    )
    assert result.origin == ORIGIN_DETERMINISTIC
    assert result.llm_attempted is False
    assert result.used_fallback is False
    assert result.used_llm is False
    assert result.validation.get("pass") is True
    assert result.validation.get("summary_origin") == ORIGIN_DETERMINISTIC


def test_summary_llm_unavailable_does_not_block_handoff(monkeypatch) -> None:
    from sdr.domain.vendor_summary import ORIGIN_DETERMINISTIC

    monkeypatch.setattr(
        "sdr.domain.vendor_summary._vendor_summary_llm_allowed", lambda: True
    )

    def _boom(_authorized):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr("sdr.domain.vendor_summary._build_vendor_summary_llm", _boom)
    result = compose_vendor_summary(
        _state(
            BusinessIntent.PURCHASE,
            {"desired_model": "Onix Plus", "payment_method": "cash", "name": "Lucas Rocha"},
        )
    )
    assert result.origin == ORIGIN_DETERMINISTIC
    assert result.llm_attempted is True
    assert result.used_llm is False
    assert result.validation.get("pass") is True


def test_summary_llm_rejected_falls_back_to_validated_deterministic(monkeypatch) -> None:
    from sdr.domain.vendor_summary import ORIGIN_DETERMINISTIC_AFTER_LLM_REJECT

    monkeypatch.setattr(
        "sdr.domain.vendor_summary._vendor_summary_llm_allowed", lambda: True
    )
    monkeypatch.setattr(
        "sdr.domain.vendor_summary._build_vendor_summary_llm",
        lambda _auth: "Os documentos estão prontos e a visita está marcada. Perfil completo.",
    )
    result = compose_vendor_summary(
        _state(
            BusinessIntent.SALE,
            {
                "name": "Bruno Azevedo",
                "trade_model": "Corolla",
                "trade_has_financing": False,
                "trade_has_debts": False,
                "trade_price_expectation": 80000,
            },
            visit_preferred_time="terça-feira, 8/09, às 9h30",
        )
    )
    assert result.origin == ORIGIN_DETERMINISTIC_AFTER_LLM_REJECT
    assert result.used_fallback is True
    assert result.llm_rejected is True
    assert result.used_llm is False
    assert result.validation.get("pass") is True
    assert "documentos" not in result.text.lower()
    assert "marcada" not in result.text.lower()
    assert "perfil completo" not in result.text.lower()
