"""Financing roteiro — Decision owns the next field; Composer must not invent."""

from __future__ import annotations

import os

import pytest

from sdr.application.process_turn import process_turn
from sdr.config import get_settings
from sdr.domain.decision import decide, inventory_search_key
from sdr.domain.merge import deterministic_merge
from sdr.domain.pending_question import overlay_pending_question
from sdr.domain.types import (
    Action,
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    TurnFacts,
)
from sdr.understanding.validator import validate_bubbles


@pytest.fixture(autouse=True)
def _clear_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    os.environ["OPENAI_API_KEY"] = ""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _state(**kwargs) -> ConversationCanonicalState:
    base = ConversationCanonicalState(
        thread_id="financing-roteiro",
        customer=CustomerState(phone="5545999999999"),
    )
    for key, value in kwargs.items():
        setattr(base, key, value)
    return base


def test_compra_resolves_pending_deal_type() -> None:
    prev = _state(
        intent=BusinessIntent.PURCHASE,
        facts={"desired_model": "Corolla"},
        pending_question="deal_type",
    )
    facts = overlay_pending_question(
        TurnFacts(intent=BusinessIntent.PURCHASE),
        prev,
        "Compra",
    )
    assert facts.facts.get("deal_type") == "purchase"


def test_financiar_sets_payment_method_and_financing_intent() -> None:
    prev = _state(
        intent=BusinessIntent.PURCHASE,
        facts={"desired_model": "Corolla", "deal_type": "purchase"},
        pending_question="payment_method",
        last_inventory_search_key=inventory_search_key(
            {"desired_model": "Corolla", "deal_type": "purchase"}
        ),
    )
    facts = overlay_pending_question(
        TurnFacts(intent=BusinessIntent.PURCHASE),
        prev,
        "Financiar",
    )
    merged = deterministic_merge(prev, facts)
    assert merged.intent == BusinessIntent.PURCHASE_FINANCING
    assert merged.facts.get("payment_method") == "financing"
    plan = decide(merged)
    assert plan.action == Action.ASK_INFO
    assert plan.ask_field == "down_payment"


def test_parcelar_is_same_payment_class_as_financiar() -> None:
    prev = _state(
        intent=BusinessIntent.PURCHASE,
        facts={"desired_model": "Civic", "deal_type": "purchase"},
        pending_question="payment_method",
        last_inventory_search_key=inventory_search_key(
            {"desired_model": "Civic", "deal_type": "purchase"}
        ),
    )
    facts = overlay_pending_question(
        TurnFacts(intent=BusinessIntent.PURCHASE),
        prev,
        "Quero parcelar",
    )
    merged = deterministic_merge(prev, facts)
    assert merged.facts.get("payment_method") == "financing"
    assert decide(merged).ask_field == "down_payment"


def test_down_payment_then_installment_not_consortium() -> None:
    facts = {
        "desired_model": "Corolla",
        "deal_type": "purchase",
        "payment_method": "financing",
        "down_payment": 5000,
    }
    state = _state(
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts=facts,
        last_inventory_search_key=inventory_search_key(facts),
    )
    plan = decide(state)
    assert plan.action == Action.ASK_INFO
    assert plan.ask_field == "desired_installment"


def test_financing_visit_only_after_documents_asked() -> None:
    facts = {
        "desired_model": "Corolla",
        "deal_type": "purchase",
        "down_payment": 5000,
        "desired_installment": 1500,
        "name": "Mateus",
    }
    state = _state(
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts=facts,
        last_inventory_search_key=inventory_search_key(facts),
        documents_asked=True,
        installment_asked=True,
    )
    plan = decide(state)
    assert plan.action == Action.REGISTER_VISIT_INTEREST
    plan2 = decide(state)
    assert plan2.action == Action.HANDOFF_VENDOR


def test_validator_strips_consortium_and_use_type_questions() -> None:
    bubbles = validate_bubbles(
        [
            "Financiamento sem entrada pode ser possível. Você pretende financiar o carro todo ou fazer um consórcio?",
            "Você pretende financiar o carro para uso pessoal ou para empresa?",
        ]
    )
    joined = " ".join(bubbles).lower()
    assert "consórcio" not in joined
    assert "consorcio" not in joined
    assert "uso pessoal" not in joined


@pytest.mark.asyncio
async def test_observed_corolla_financing_path_stays_on_roteiro() -> None:
    """Observed live path: Compra → Financiar → 5 mil. Never consórcio / uso."""

    async def understand(text: str, state: ConversationCanonicalState) -> TurnFacts:
        low = text.lower()
        if "corolla" in low:
            return TurnFacts(
                intent=BusinessIntent.PURCHASE,
                facts={"desired_model": "Corolla"},
            )
        if "compra" in low:
            return TurnFacts(intent=BusinessIntent.PURCHASE)
        if "financ" in low:
            return TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING)
        if "5 mil" in low or "5000" in low:
            return TurnFacts(
                intent=BusinessIntent.PURCHASE_FINANCING,
                facts={"down_payment": 5000},
            )
        return TurnFacts(intent=BusinessIntent.PURCHASE)

    state = _state()
    r1 = await process_turn(
        state=state,
        inbound_text="Gostaria de saber mais informações sobre o Corolla",
        understand=understand,
    )
    state = r1.state
    state.assistant_turn_count = 1
    state.last_inventory_search_key = inventory_search_key(state.facts)
    state.last_shown_vehicle_ids = ["veh-corolla"]

    r2 = await process_turn(state=state, inbound_text="Compra", understand=understand)
    state = r2.state
    joined2 = " ".join(r2.outbound_texts).lower()
    assert "consórcio" not in joined2
    assert "uso pessoal" not in joined2
    # After "Compra" on PURCHASE intent (model already known), system asks payment method.
    assert r2.action_plan.ask_field == "payment_method"

    r3 = await process_turn(state=state, inbound_text="Financiar", understand=understand)
    state = r3.state
    joined3 = " ".join(r3.outbound_texts).lower()
    assert "consórcio" not in joined3
    assert "uso pessoal" not in joined3
    assert r3.action_plan.ask_field == "down_payment"
    assert "entrada" in joined3

    r4 = await process_turn(
        state=state, inbound_text="Posso dar uma entrada de 5 mil", understand=understand
    )
    joined4 = " ".join(r4.outbound_texts).lower()
    assert "consórcio" not in joined4
    assert "uso pessoal" not in joined4
    assert r4.action_plan.ask_field == "desired_installment"
    assert "parcela" in joined4
    assert "mês" not in joined4 or "parcela" in joined4
    assert "quantos meses" not in joined4
    assert "condições tendem" not in joined4


@pytest.mark.asyncio
async def test_location_question_invites_visit_instead_of_address() -> None:
    facts = {
        "desired_model": "Corolla",
        "deal_type": "purchase",
        "payment_method": "financing",
        "down_payment": 20000,
    }

    async def understand(text: str, state: ConversationCanonicalState) -> TurnFacts:
        return TurnFacts(
            intent=BusinessIntent.PURCHASE_FINANCING,
            location_request=True,
        )

    state = _state(
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts=facts,
        last_inventory_search_key=inventory_search_key(facts),
        documents_asked=True,
        assistant_turn_count=4,
    )
    result = await process_turn(
        state=state,
        inbound_text="Qual a localização da loja?",
        understand=understand,
    )
    joined = " ".join(result.outbound_texts).lower()
    assert result.action_plan.action == Action.SEND_LOCATION
    assert result.state.pending_question == "visit"
    assert result.state.visit_invited is True
    assert "ipanema" not in joined
    assert "cep" not in joined
    assert "encaminhar" not in joined
    assert "esperamos você" in joined or "loja" in joined


@pytest.mark.asyncio
async def test_onde_fica_a_loja_same_visit_cta_contract() -> None:
    """Semantic equivalent of an address ask — still pin + visit CTA, not street text."""
    facts = {
        "desired_model": "Civic",
        "deal_type": "purchase",
        "payment_method": "financing",
        "down_payment": 8000,
    }

    async def understand(text: str, state: ConversationCanonicalState) -> TurnFacts:
        return TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING, location_request=True)

    state = _state(
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts=facts,
        last_inventory_search_key=inventory_search_key(facts),
        documents_asked=True,
        assistant_turn_count=3,
    )
    result = await process_turn(
        state=state,
        inbound_text="Onde fica a loja?",
        understand=understand,
    )
    assert result.action_plan.action == Action.SEND_LOCATION
    joined = " ".join(result.outbound_texts).lower()
    assert "rua" not in joined
    assert "esperamos você" in joined or "loja" in joined


def test_handoff_summary_financing_is_not_cash() -> None:
    from sdr.domain.vendor_summary import build_vendor_summary

    state = _state(
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts={
            "desired_model": "Corolla",
            "deal_type": "purchase",
            "payment_method": "financing",
            "down_payment": 20000,
        },
    )
    summary = build_vendor_summary(state)
    assert "financiamento" in summary.lower() or "financiada" in summary.lower() or "financiando" in summary.lower()
    assert "à vista" not in summary.lower()


@pytest.mark.asyncio
async def test_ack_before_next_question_after_deal_type() -> None:
    async def understand(text: str, state: ConversationCanonicalState) -> TurnFacts:
        return TurnFacts(intent=BusinessIntent.PURCHASE, facts={"deal_type": "purchase"})

    state = _state(
        intent=BusinessIntent.PURCHASE,
        facts={"desired_model": "Corolla"},
        pending_question="deal_type",
        last_inventory_search_key=inventory_search_key({"desired_model": "Corolla"}),
        assistant_turn_count=1,
    )
    result = await process_turn(
        state=state, inbound_text="Quero comprar", understand=understand
    )
    joined = " ".join(result.outbound_texts)
    assert "anotei" not in joined.lower()
    assert "beleza, então é compra" not in joined.lower()
    # After deal_type=purchase on PURCHASE intent, system asks payment method.
    assert "vista" in joined.lower() or "financ" in joined.lower()
    assert "que ótimo saber" not in joined.lower()
    assert "bacana" not in joined.lower()


def test_overlay_does_not_restate_known_financing_on_document_text() -> None:
    prev = _state(
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts={
            "desired_model": "Corolla",
            "deal_type": "purchase",
            "payment_method": "financing",
            "down_payment": 20000,
        },
        pending_question="documents",
    )
    facts = overlay_pending_question(
        TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING),
        prev,
        "nome: Mateus Ferreira\ncpf: 52998224725\ntipo: CNH",
    )
    assert "payment_method" not in facts.facts


def test_visit_pending_short_yes_sets_visit_intent() -> None:
    prev = _state(
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts={"desired_model": "Corolla", "deal_type": "purchase"},
        pending_question="visit",
    )
    facts = overlay_pending_question(
        TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING),
        prev,
        "Sim, essa semana",
    )
    assert facts.signals.visit_intent is True
    assert facts.facts.get("timeline") == "essa semana"


def test_visit_pending_seria_otimo_does_not_set_visit_intent() -> None:
    """Positive but slot-less reply must stay on the visit question."""
    prev = _state(
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts={"desired_model": "Corolla", "deal_type": "purchase"},
        pending_question="visit",
    )
    facts = overlay_pending_question(
        TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING),
        prev,
        "Seria ótimo",
    )
    assert facts.signals.visit_intent is not True


def test_visit_pending_vou_amanha_stores_timeline() -> None:
    prev = _state(
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts={"desired_model": "Corolla"},
        pending_question="visit",
    )
    facts = overlay_pending_question(
        TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING),
        prev,
        "Vou amanhã",
    )
    assert facts.signals.visit_intent is True
    assert facts.facts.get("timeline") == "amanhã"


@pytest.mark.asyncio
async def test_down_payment_does_not_reshow_inventory() -> None:
    from sdr.domain.budget_status import BudgetStatus

    facts = {
        "desired_model": "Corolla",
        "deal_type": "purchase",
        "payment_method": "financing",
    }
    key = inventory_search_key(facts)

    async def understand(text: str, state: ConversationCanonicalState) -> TurnFacts:
        return TurnFacts(
            intent=BusinessIntent.PURCHASE_FINANCING,
            facts={"down_payment": 20000, "budget": 20000},
            budget_status=BudgetStatus.PROVIDED,
        )

    state = _state(
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts=facts,
        pending_question="down_payment",
        last_inventory_search_key=key,
        last_shown_vehicle_ids=["veh-corolla"],
        assistant_turn_count=3,
    )
    result = await process_turn(
        state=state,
        inbound_text="Tenho 20 mil pra dar de entrada",
        understand=understand,
    )
    assert result.action_plan.action == Action.ASK_INFO
    assert result.action_plan.ask_field == "desired_installment"
    assert result.outbound_media == []
    joined = " ".join(result.outbound_texts).lower()
    assert "parcela" in joined
    # New template acknowledges entry concisely without the old "taxas tendem" phrasing.
    assert "condições tendem a ser melhores" not in joined
    # Must not echo the exact amount the customer provided.
    assert "20 mil" not in joined
    assert "os dois" not in joined


@pytest.mark.asyncio
async def test_installment_answer_does_not_reshow_photos() -> None:
    from sdr.domain.budget_status import BudgetStatus

    facts = {
        "desired_model": "Corolla",
        "deal_type": "purchase",
        "payment_method": "financing",
        "down_payment": 30000,
    }
    key = inventory_search_key(facts)

    async def understand(text: str, state: ConversationCanonicalState) -> TurnFacts:
        return TurnFacts(
            intent=BusinessIntent.PURCHASE_FINANCING,
            facts={
                "desired_installment": 2000,
                "budget": 2000,
                "desired_engine_displacement_liters": 2.0,
            },
            budget_status=BudgetStatus.PROVIDED,
        )

    state = _state(
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts=facts,
        pending_question="desired_installment",
        last_inventory_search_key=key,
        last_shown_vehicle_ids=["veh-corolla"],
        last_shown_price_cash=84900,
        assistant_turn_count=4,
        installment_asked=True,
    )
    result = await process_turn(
        state=state,
        inbound_text="Até uns 2 mil acho que é ok pagar",
        understand=understand,
    )
    assert result.action_plan.action == Action.ASK_INFO
    assert result.action_plan.ask_field == "documents"
    assert result.outbound_media == []


@pytest.mark.asyncio
async def test_document_turn_acks_document_not_financing() -> None:
    from sdr.domain.inbound import ContentType, InboundTurn, MediaStatus

    facts = {
        "desired_model": "Corolla",
        "deal_type": "purchase",
        "payment_method": "financing",
        "down_payment": 20000,
    }

    async def understand(text: str, state: ConversationCanonicalState) -> TurnFacts:
        return TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING)

    state = _state(
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts=facts,
        pending_question="documents",
        last_inventory_search_key=inventory_search_key(facts),
        documents_asked=True,
        assistant_turn_count=5,
    )
    inbound = InboundTurn(
        thread_id=state.thread_id,
        content_type=ContentType.DOCUMENT,
        text="nome: Mateus Ferreira\ntipo: CNH",
        media_status=MediaStatus.OK,
    )
    result = await process_turn(state=state, inbound=inbound, understand=understand)
    joined = " ".join(result.outbound_texts).lower()
    assert "anotei: financiado" not in joined
    assert "documento" in joined or "ficha" in joined or "cnh" in joined
    assert "quantos meses" not in joined
    assert "prazo mais curto" not in joined


def test_overlay_installment_from_monthly_amount() -> None:
    prev = _state(
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts={"desired_model": "Civic", "deal_type": "purchase", "down_payment": 10000},
        pending_question="desired_installment",
    )
    facts = overlay_pending_question(
        TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING),
        prev,
        "até 2000",
    )
    assert facts.facts.get("desired_installment") == 2000
    assert "budget" not in facts.facts


def test_overlay_installment_skip_does_not_block() -> None:
    prev = _state(
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts={"desired_model": "Civic", "deal_type": "purchase", "down_payment": 8000},
        pending_question="desired_installment",
    )
    facts = overlay_pending_question(
        TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING),
        prev,
        "não sei",
    )
    assert "desired_installment" not in facts.facts


def test_overlay_alternatives_ok_short_yes_is_accept() -> None:
    from sdr.domain.pending_interaction import PendingResolution

    prev = _state(
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts={"desired_model": "Civic"},
        pending_question="alternatives_ok",
    )
    facts = overlay_pending_question(
        TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING),
        prev,
        "Sim, pode mostrar",
    )
    assert facts.pending_resolution == PendingResolution.ACCEPT


def test_overlay_alternatives_ok_short_no_is_reject() -> None:
    from sdr.domain.pending_interaction import PendingResolution

    prev = _state(
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts={"desired_model": "Civic"},
        pending_question="alternatives_ok",
    )
    facts = overlay_pending_question(
        TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING),
        prev,
        "Não, seguimos com esse",
    )
    assert facts.pending_resolution == PendingResolution.REJECT


def test_after_installment_asks_documents() -> None:
    facts = {
        "desired_model": "Civic",
        "deal_type": "purchase",
        "payment_method": "financing",
        "down_payment": 8000,
        "desired_installment": 2000,
    }
    state = _state(
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts=facts,
        last_inventory_search_key=inventory_search_key(facts),
        installment_asked=True,
    )
    plan = decide(state)
    assert plan.ask_field == "documents"


@pytest.mark.asyncio
async def test_document_after_installment_invites_visit() -> None:
    from sdr.domain.inbound import ContentType, InboundTurn, MediaStatus

    facts = {
        "desired_model": "Civic",
        "deal_type": "purchase",
        "payment_method": "financing",
        "down_payment": 8000,
        "desired_installment": 2000,
    }

    async def understand(text: str, state: ConversationCanonicalState) -> TurnFacts:
        return TurnFacts(
            intent=BusinessIntent.PURCHASE_FINANCING,
            facts={"name": "MATEUS MANOEL FERREIRA"},
        )

    state = _state(
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts=facts,
        pending_question="documents",
        last_inventory_search_key=inventory_search_key(facts),
        documents_asked=True,
        installment_asked=True,
        assistant_turn_count=6,
    )
    inbound = InboundTurn(
        thread_id=state.thread_id,
        content_type=ContentType.DOCUMENT,
        text="nome: MATEUS MANOEL FERREIRA\ntipo: CNH",
        media_status=MediaStatus.OK,
    )
    result = await process_turn(state=state, inbound=inbound, understand=understand)
    assert result.action_plan.action == Action.REGISTER_VISIT_INTEREST
    joined = " ".join(result.outbound_texts).lower()
    assert "documento" in joined or "ficha" in joined
    assert "encaminhar" not in joined
    assert "manhã ou tarde" not in joined
    assert "quantos meses" not in joined
    assert "sem compromisso" not in joined
    # New scheduling gives concrete slots like "segunda-feira, 7/09, de manhã"
    assert any(w in joined for w in ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "manhã", "tarde", "que tal"])

