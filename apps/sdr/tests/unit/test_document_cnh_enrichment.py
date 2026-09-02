"""CNH extraction enrichment — OCR normalize + CRM field flow helpers."""

from __future__ import annotations

from sdr.domain.pending_question import overlay_pending_question
from sdr.domain.types import (
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    TurnFacts,
)
from sdr.media.document_extractor import (
    normalize_birth_date,
    normalize_naturalidade,
)


def test_normalize_birth_date_iso_to_br() -> None:
    assert normalize_birth_date("2000-04-16") == "16/04/2000"
    assert normalize_birth_date("16/04/2000") == "16/04/2000"
    assert normalize_birth_date("not-a-date") is None


def test_normalize_naturalidade_splits_city_uf() -> None:
    city, uf = normalize_naturalidade("FOZ DO IGUAÇU/PR", None)
    assert city == "FOZ DO IGUAÇU"
    assert uf == "PR"

    city2, uf2 = normalize_naturalidade("IGUACU", "PE")
    assert city2 == "IGUACU"
    assert uf2 == "PE"  # valid UF code — OCR quality is prompt-side

    city3, uf3 = normalize_naturalidade("CIDADE", "XX")
    assert city3 == "CIDADE"
    assert uf3 is None  # invalid UF discarded


def test_financia_100_sets_down_payment_zero_on_payment_method() -> None:
    state = ConversationCanonicalState(
        thread_id="t1",
        customer=CustomerState(phone="5511999999999"),
        pending_question="payment_method",
        intent=BusinessIntent.PURCHASE,
        facts={"desired_model": "Corolla", "deal_type": "purchase"},
    )
    facts = TurnFacts(intent=BusinessIntent.PURCHASE)
    out = overlay_pending_question(
        facts, state, "Financiado. Gostei desse. Financia 100%?"
    )
    assert out.facts.get("payment_method") == "financing"
    assert out.facts.get("down_payment") == 0


def test_financia_100_without_pending_still_sets_zero_when_financing() -> None:
    state = ConversationCanonicalState(
        thread_id="t1",
        customer=CustomerState(phone="5511999999999"),
        pending_question=None,
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts={
            "desired_model": "Corolla",
            "deal_type": "purchase",
            "payment_method": "financing",
        },
    )
    facts = TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING)
    out = overlay_pending_question(facts, state, "Financia 100%?")
    assert out.facts.get("down_payment") == 0
