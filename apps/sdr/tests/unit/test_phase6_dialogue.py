"""Phase 6 — semantic humanization of the Composer (invariants, not copy matching)."""

from __future__ import annotations

import os
import re
from decimal import Decimal

import pytest

from sdr.application.process_turn import process_turn
from sdr.config import get_settings
from sdr.domain.decision import inventory_search_key
from sdr.domain.dialogue_plan import (
    DialogueAct,
    DirectQuestionKind,
    build_dialogue_plan,
    contains_financing_approval_claim,
    is_courtesy_only,
    looks_like_intent_menu,
)
from sdr.domain.inbound import ContentType, InboundTurn, MediaStatus, QuotedContext
from sdr.domain.inventory_search import InventorySearchRequest, inventory_search_key_from_request
from sdr.domain.types import (
    Action,
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    LifecycleStatus,
    LifecycleState,
    TurnFacts,
)
from sdr.domain.vehicle_reference import PresentedVehicleBinding
from sdr.tools.inventory import InventoryVehicle
from sdr.understanding.response_composer import compose_response
from sdr.understanding.validator import validate_dialogue_plan


STRADA_2021 = "veh-strada-2021"
STRADA_2017 = "veh-strada-2017"
STRADA_2018 = "veh-strada-2018"
CONV = "syn-conv-phase6"


@pytest.fixture(autouse=True)
def _no_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    os.environ["OPENAI_API_KEY"] = ""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _joined(bubbles: list[str]) -> str:
    return " ".join(bubbles).lower()


def _question_count(bubbles: list[str]) -> int:
    return sum(b.count("?") for b in bubbles if isinstance(b, str))


def _name_mentions(bubbles: list[str], name: str) -> int:
    token = name.strip().split()[0]
    if not token:
        return 0
    pat = re.compile(rf"\b{re.escape(token)}\b", re.I)
    return sum(len(pat.findall(b)) for b in bubbles if isinstance(b, str))


def _state(**kwargs) -> ConversationCanonicalState:
    intent = kwargs.pop("intent", BusinessIntent.UNKNOWN)
    facts = kwargs.pop("facts", {})
    turn_count = kwargs.pop("assistant_turn_count", 0)
    customer = kwargs.pop("customer", CustomerState(phone="5511999999999", name="Mateus Ferreira"))
    state = ConversationCanonicalState(
        thread_id=kwargs.pop("thread_id", CONV),
        customer=customer,
        intent=intent,
        language="pt-BR",
        facts=facts,
    )
    state.assistant_turn_count = turn_count
    for key, value in kwargs.items():
        setattr(state, key, value)
    return state


def _strada_bindings() -> list[PresentedVehicleBinding]:
    offer = "offer-set-strada-1"
    return [
        PresentedVehicleBinding(
            conversation_id=CONV,
            provider_message_id="prov-img-2021",
            vehicle_id=STRADA_2021,
            presentation_type="IMAGE",
            position=0,
            offer_set_id=offer,
        ),
        PresentedVehicleBinding(
            conversation_id=CONV,
            provider_message_id="prov-img-2017",
            vehicle_id=STRADA_2017,
            presentation_type="IMAGE",
            position=1,
            offer_set_id=offer,
        ),
        PresentedVehicleBinding(
            conversation_id=CONV,
            provider_message_id="prov-img-2018",
            vehicle_id=STRADA_2018,
            presentation_type="IMAGE",
            position=2,
            offer_set_id=offer,
        ),
    ]


def _shown_stradas(**overrides) -> ConversationCanonicalState:
    facts = {"desired_model": "Strada", "desired_vehicle_text": "Strada", **overrides.pop("facts", {})}
    shown = [STRADA_2021, STRADA_2017, STRADA_2018]
    req = InventorySearchRequest(original_model="Strada", original_vehicle_text="Strada")
    key = inventory_search_key_from_request(req, last_shown_vehicle_ids=shown)
    return _state(
        intent=BusinessIntent.PURCHASE,
        facts=facts,
        last_inventory_search_key=key,
        last_shown_vehicle_ids=shown,
        presented_vehicle_bindings=_strada_bindings(),
        assistant_turn_count=2,
        **overrides,
    )


def test_plan_greeting_requires_reciprocity() -> None:
    plan = build_dialogue_plan(
        inbound_text="Olá, tudo bem?",
        action=Action.SMALLTALK,
        should_introduce=True,
        intent=BusinessIntent.SMALLTALK,
    )
    assert DialogueAct.RAPPORT.value in plan.acts
    assert plan.wellbeing_reciprocity is True


def test_plan_greeting_with_vehicle_skips_intent_menu() -> None:
    plan = build_dialogue_plan(
        inbound_text="Oi, e essa Strada ainda tem?",
        action=Action.SHOW_OFFERS,
        intent=BusinessIntent.PURCHASE,
        should_introduce=True,
        facts_context={"desired_model": "Strada"},
        ask_field="payment_method",
    )
    assert plan.skip_generic_intent_menu is True
    kinds = {q["kind"] for q in plan.direct_questions}
    assert DirectQuestionKind.AVAILABILITY.value in kinds
    assert DialogueAct.ANSWER_DIRECT_QUESTION.value in plan.acts


def test_plan_financing_burst_answers_before_next_field() -> None:
    facts = TurnFacts(
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts={"payment_method": "financing", "down_payment": 0},
    )
    plan = build_dialogue_plan(
        inbound_text="Compra financiada. Financia 100%?",
        action=Action.ASK_INFO,
        ask_field="desired_installment",
        intent=BusinessIntent.PURCHASE_FINANCING,
        turn_facts=facts,
        facts_context={"payment_method": "financing", "down_payment": 0, "desired_model": "Civic"},
        ack_kind="payment_financing",
    )
    assert DialogueAct.ANSWER_DIRECT_QUESTION.value in plan.acts
    assert DialogueAct.SAFETY_DISCLAIMER.value in plan.acts
    assert DialogueAct.ASK_NEXT_FIELD.value in plan.acts
    assert "down_payment" in plan.forbid_reask_fields
    assert plan.canonical_question == "desired_installment"


def test_courtesy_only_detection() -> None:
    assert is_courtesy_only("Obrigado") is True
    assert is_courtesy_only("Obrigado!", TurnFacts()) is True
    assert is_courtesy_only(
        "Obrigado, parcela de 2000",
        TurnFacts(facts={"desired_installment": 2000}),
    ) is False
    assert is_courtesy_only("Financia 100%?") is False


@pytest.mark.asyncio
async def test_a_greeting_reciprocity_without_rigid_menu() -> None:
    async def understand(_text, _state):
        return TurnFacts(intent=BusinessIntent.SMALLTALK, language="pt-BR")

    result = await process_turn(
        state=_state(assistant_turn_count=0),
        inbound_text="Olá! Tudo bem?",
        understand=understand,
    )
    joined = _joined(result.outbound_texts)
    assert result.outbound_texts
    assert result.response_directive is not None
    plan = result.response_directive.dialogue_plan
    assert plan.get("wellbeing_reciprocity") is True
    assert any(
        token in joined
        for token in ("tudo bem", "bem sim", "e você", "e com você", "por aqui", "tudo certo")
    ), f"missing reciprocity: {result.outbound_texts}"
    assert not looks_like_intent_menu(joined), f"rigid intent menu: {result.outbound_texts}"
    assert "júlia" in joined or "julia" in joined


@pytest.mark.asyncio
async def test_b_greeting_with_vehicle_skips_buy_trade_menu(monkeypatch) -> None:
    car = InventoryVehicle(
        id="v-strada",
        slug="strada",
        title="FIAT STRADA FREEDOM",
        brand_name="Fiat",
        model="Strada",
        type="CAR",
        price_cash=Decimal("68900"),
        mileage=45000,
        color="Branco",
        year_model=2018,
        year_manufacture=2018,
        version="Freedom",
        images=({"id": "c1", "url": "https://cdn.example/strada.jpg", "sortOrder": 0, "isCover": True},),
    )

    async def fake_search(_pool, _req):
        return [car]

    monkeypatch.setattr("sdr.tools.inventory.search_with_request", fake_search)

    async def understand(_text, _state):
        return TurnFacts(
            intent=BusinessIntent.PURCHASE,
            language="pt-BR",
            facts={"desired_model": "Strada"},
        )

    result = await process_turn(
        state=_state(assistant_turn_count=0),
        inbound_text="Olá! E essa Strada, ainda tem?",
        understand=understand,
        pool=object(),
    )
    joined = _joined(result.outbound_texts)
    assert not looks_like_intent_menu(joined), result.outbound_texts
    assert not ("comprar" in joined and "trocar" in joined and "vender" in joined)


@pytest.mark.asyncio
async def test_c_financing_burst_one_decision_direct_answer() -> None:
    facts = {
        "desired_model": "Civic",
        "deal_type": "purchase",
    }
    key = inventory_search_key({**facts, "payment_method": "financing", "down_payment": 0})

    async def understand(_text, _state):
        return TurnFacts(
            intent=BusinessIntent.PURCHASE_FINANCING,
            language="pt-BR",
            facts={"payment_method": "financing", "down_payment": 0, "desired_model": "Civic"},
        )

    result = await process_turn(
        state=_state(
            intent=BusinessIntent.PURCHASE,
            facts=facts,
            last_inventory_search_key=key,
            last_shown_vehicle_ids=["civic-1"],
            assistant_turn_count=1,
        ),
        inbound_text="Compra financiada.\nFinancia 100%?",
        understand=understand,
    )
    joined = _joined(result.outbound_texts)
    assert result.action_plan.action == Action.ASK_INFO
    assert result.action_plan.ask_field == "desired_installment"
    assert "entrada" not in joined or "sem entrada" in joined
    assert any(token in joined for token in ("análise", "financeira", "simula"))
    assert not contains_financing_approval_claim(joined)
    assert "parcela" in joined
    assert _question_count(result.outbound_texts) <= 2


def test_d_validator_rejects_financing_approval_language() -> None:
    plan = build_dialogue_plan(
        inbound_text="Financia 100%?",
        action=Action.ASK_INFO,
        ask_field="desired_installment",
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts_context={"payment_method": "financing", "down_payment": 0},
        turn_facts=TurnFacts(facts={"down_payment": 0, "payment_method": "financing"}),
    )
    bubbles, result = validate_dialogue_plan(
        ["Vamos financiar o valor todo, financiamento aprovado, taxa garantida de 1%."],
        plan,
        language="pt-BR",
        customer_name="Mateus",
    )
    joined = _joined(bubbles)
    assert "vamos financiar" not in joined
    assert "aprovado" not in joined
    assert "taxa garantida" not in joined
    assert result.get("violations")


@pytest.mark.asyncio
async def test_e_installment_ack_advances_to_documents() -> None:
    facts = {
        "desired_model": "Civic",
        "deal_type": "purchase",
        "payment_method": "financing",
        "down_payment": 0,
    }

    async def understand(_text, _state):
        return TurnFacts(
            intent=BusinessIntent.PURCHASE_FINANCING,
            language="pt-BR",
            facts={"desired_installment": 1800},
        )

    result = await process_turn(
        state=_state(
            intent=BusinessIntent.PURCHASE_FINANCING,
            facts=facts,
            last_inventory_search_key=inventory_search_key(facts),
            last_shown_vehicle_ids=["civic-1"],
            pending_question="desired_installment",
            installment_asked=True,
            assistant_turn_count=3,
        ),
        inbound_text="Consigo pagar uns 1800 de parcela",
        understand=understand,
    )
    joined = _joined(result.outbound_texts)
    assert result.action_plan.ask_field == "documents"
    assert "parcela" in joined or "anotei" in joined or "certo" in joined or "perfeito" in joined
    assert not re.search(r"at[eé] quanto de parcela", joined)
    assert "cnh" in joined or "documento" in joined or "comprovante" in joined


@pytest.mark.asyncio
async def test_f_cnh_ack_without_storage_leak() -> None:
    facts = {
        "desired_model": "Civic",
        "payment_method": "financing",
        "down_payment": 0,
        "desired_installment": 1800,
    }

    async def understand(_text, _state):
        return TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING, language="pt-BR")

    inbound = InboundTurn(
        thread_id=CONV,
        content_type=ContentType.DOCUMENT,
        text="nome: Mateus Ferreira\ntipo: CNH",
        media_status=MediaStatus.OK,
    )
    result = await process_turn(
        state=_state(
            intent=BusinessIntent.PURCHASE_FINANCING,
            facts=facts,
            last_inventory_search_key=inventory_search_key(facts),
            last_shown_vehicle_ids=["civic-1"],
            documents_asked=True,
            pending_question="documents",
            assistant_turn_count=4,
        ),
        inbound=inbound,
        understand=understand,
    )
    joined = _joined(result.outbound_texts)
    assert "cnh" in joined or "documento" in joined
    assert "storage" not in joined
    assert "bucket" not in joined
    assert "reenvi" not in joined


@pytest.mark.asyncio
async def test_g_reply_on_strada_2018_does_not_research(monkeypatch) -> None:
    searched = {"n": 0}

    async def fake_search(_pool, _req):
        searched["n"] += 1
        return []

    monkeypatch.setattr("sdr.tools.inventory.search_with_request", fake_search)

    async def understand(_text, _state):
        return TurnFacts(intent=BusinessIntent.PURCHASE, language="pt-BR")

    inbound = InboundTurn(
        thread_id=CONV,
        content_type=ContentType.TEXT,
        text="Gostei dessa opção",
        media_status=MediaStatus.OK,
        quoted=[QuotedContext(stanza_id="prov-img-2018", quoted_text="Fiat Strada 2018")],
    )
    result = await process_turn(
        state=_shown_stradas(),
        inbound=inbound,
        understand=understand,
        pool=object(),
    )
    assert searched["n"] == 0
    assert result.state.primary_vehicle_id == STRADA_2018
    assert result.action_plan.action != Action.SHOW_OFFERS
    joined = _joined(result.outbound_texts)
    assert "2021" not in joined
    assert "civic" not in joined


@pytest.mark.asyncio
async def test_h_trade_question_answered_before_used_car_fields() -> None:
    async def understand(_text, _state):
        return TurnFacts(intent=BusinessIntent.TRADE, language="pt-BR", facts={"deal_type": "trade"})

    result = await process_turn(
        state=_state(
            intent=BusinessIntent.PURCHASE,
            facts={"desired_model": "Civic"},
            last_inventory_search_key=inventory_search_key({"desired_model": "Civic"}),
            last_shown_vehicle_ids=["civic-1"],
            assistant_turn_count=2,
        ),
        inbound_text="Vocês aceitam meu carro na troca?",
        understand=understand,
    )
    joined = _joined(result.outbound_texts)
    assert "troca" in joined
    assert any(token in joined for token in ("sim", "aceit", "trabalh", "inclu"))
    first = result.outbound_texts[0].lower()
    assert not first.strip().startswith("qual marca")


@pytest.mark.asyncio
async def test_i_availability_before_payment_method() -> None:
    async def understand(_text, _state):
        return TurnFacts(intent=BusinessIntent.PURCHASE, language="pt-BR")

    result = await process_turn(
        state=_shown_stradas(facts={"desired_model": "Strada", "deal_type": "purchase"}),
        inbound_text="Ainda está disponível?",
        understand=understand,
    )
    joined = _joined(result.outbound_texts)
    assert any(token in joined for token in ("dispon", "ainda", "estoque", "sim"))
    first = result.outbound_texts[0].lower()
    assert not first.startswith("seria à vista")


def test_j_unknown_question_does_not_invent() -> None:
    plan = build_dialogue_plan(
        inbound_text="Esse carro tem teto solar panorâmico de série?",
        action=Action.ASK_INFO,
        ask_field="payment_method",
        intent=BusinessIntent.PURCHASE,
        facts_context={"desired_model": "Strada"},
        assistant_turn_count=2,
    )
    kinds = {q["kind"] for q in plan.direct_questions}
    assert DirectQuestionKind.UNKNOWN.value in kinds
    bubbles, result = validate_dialogue_plan(
        ["Sim, tem teto solar panorâmico de série e teto de vidro."],
        plan,
        language="pt-BR",
        customer_name="Mateus",
    )
    joined = _joined(bubbles)
    assert "sim, tem teto" not in joined
    assert "teto de vidro" not in joined
    assert result.get("violations") or "não" in joined or "equipe" in joined or "vendedor" in joined


@pytest.mark.asyncio
async def test_k_name_not_repeated_every_bubble() -> None:
    facts = {
        "desired_model": "Civic",
        "payment_method": "financing",
        "down_payment": 0,
    }

    async def understand(_text, _state):
        return TurnFacts(
            intent=BusinessIntent.PURCHASE_FINANCING,
            language="pt-BR",
            facts={"desired_installment": 2000},
        )

    result = await process_turn(
        state=_state(
            intent=BusinessIntent.PURCHASE_FINANCING,
            facts=facts,
            last_inventory_search_key=inventory_search_key(facts),
            last_shown_vehicle_ids=["civic-1"],
            pending_question="desired_installment",
            assistant_turn_count=3,
        ),
        inbound_text="Parcela de 2000",
        understand=understand,
    )
    mentions = _name_mentions(result.outbound_texts, "Mateus")
    if len(result.outbound_texts) >= 2:
        named_bubbles = sum(1 for b in result.outbound_texts if re.search(r"\bmateus\b", b, re.I))
        assert named_bubbles < len(result.outbound_texts)
    assert mentions <= 1


@pytest.mark.asyncio
async def test_l_simple_reply_is_not_a_questionnaire() -> None:
    async def understand(_text, _state):
        return TurnFacts(
            intent=BusinessIntent.PURCHASE_FINANCING,
            language="pt-BR",
            facts={"payment_method": "financing"},
        )

    facts = {"desired_model": "Civic", "deal_type": "purchase"}
    result = await process_turn(
        state=_state(
            intent=BusinessIntent.PURCHASE,
            facts=facts,
            last_inventory_search_key=inventory_search_key({**facts, "payment_method": "financing"}),
            last_shown_vehicle_ids=["civic-1"],
            pending_question="payment_method",
            assistant_turn_count=2,
        ),
        inbound_text="Financiado",
        understand=understand,
    )
    assert _question_count(result.outbound_texts) <= 1


@pytest.mark.asyncio
async def test_m_visit_confirm_has_no_vendor_loop() -> None:
    from sdr.domain.scheduling import suggest_visit_slots

    slots = suggest_visit_slots()
    facts = {
        "desired_model": "Civic",
        "payment_method": "financing",
        "down_payment": 0,
        "desired_installment": 2000,
        "name": "Mateus Ferreira",
    }

    async def understand(_text, _state):
        return TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING, language="pt-BR")

    result = await process_turn(
        state=_state(
            intent=BusinessIntent.PURCHASE_FINANCING,
            facts=facts,
            last_inventory_search_key=inventory_search_key(facts),
            last_shown_vehicle_ids=["civic-1"],
            visit_invited=True,
            offered_visit_slots=list(slots),
            documents_asked=True,
            assistant_turn_count=6,
        ),
        inbound_text="Pode ser o primeiro horário",
        understand=understand,
    )
    joined = _joined(result.outbound_texts)
    assert "confirmação do vendedor" not in joined
    assert "vendedor vai confirmar" not in joined


@pytest.mark.asyncio
async def test_n_courtesy_does_not_reopen_roteiro() -> None:
    facts = {
        "desired_model": "Civic",
        "deal_type": "purchase",
        "payment_method": "financing",
        "down_payment": 0,
    }

    async def understand(_text, _state):
        return TurnFacts(intent=BusinessIntent.SMALLTALK, language="pt-BR")

    result = await process_turn(
        state=_state(
            intent=BusinessIntent.PURCHASE_FINANCING,
            facts=facts,
            last_inventory_search_key=inventory_search_key(facts),
            last_shown_vehicle_ids=["civic-1"],
            pending_question="desired_installment",
            assistant_turn_count=3,
        ),
        inbound_text="Obrigado",
        understand=understand,
    )
    joined = _joined(result.outbound_texts)
    assert result.action_plan.action == Action.SMALLTALK
    assert result.action_plan.ask_field in (None, "")
    assert not re.search(r"at[eé] quanto de parcela", joined)
    assert not looks_like_intent_menu(joined)
    assert any(token in joined for token in ("nada", "disponha", "imagina", "que isso", "qualquer"))


@pytest.mark.asyncio
async def test_o_post_handoff_does_not_reintroduce() -> None:
    async def understand(_text, _state):
        return TurnFacts(
            intent=BusinessIntent.PURCHASE_FINANCING,
            language="pt-BR",
            facts={"desired_installment": 1500},
        )

    result = await process_turn(
        state=_state(
            intent=BusinessIntent.PURCHASE_FINANCING,
            facts={"desired_model": "Civic", "payment_method": "financing"},
            lifecycle=LifecycleState(status=LifecycleStatus.HANDOFF_SENT),
            assistant_turn_count=8,
        ),
        inbound_text="Mudei de ideia, parcela de 1500",
        understand=understand,
    )
    assert result.action_plan.action != Action.HANDOFF_VENDOR
    assert result.action_plan.action != Action.NO_REPLY
    joined = _joined(result.outbound_texts)
    assert "olá" not in joined
    assert "sou a júlia" not in joined


@pytest.mark.asyncio
async def test_p_llm_unavailable_fallback_is_contextual() -> None:
    bubbles = await compose_response(
        {
            "language": "pt-BR",
            "should_introduce": False,
            "inbound_text": "Financia 100%?",
            "ack_kind": "payment_financing",
            "facts": {"payment_method": "financing", "down_payment": 0, "desired_model": "Civic"},
            "customer_name": "Mateus Ferreira",
            "dialogue_plan": build_dialogue_plan(
                inbound_text="Financia 100%?",
                action=Action.ASK_INFO,
                ask_field="desired_installment",
                intent=BusinessIntent.PURCHASE_FINANCING,
                facts_context={"payment_method": "financing", "down_payment": 0},
                turn_facts=TurnFacts(facts={"payment_method": "financing", "down_payment": 0}),
            ).to_dict(),
        },
        {"action": "ask_info", "ask_field": "desired_installment"},
    )
    joined = _joined(bubbles)
    assert bubbles
    assert "olá" not in joined
    assert "sou a júlia" not in joined
    assert not looks_like_intent_menu(joined)
    assert any(token in joined for token in ("simula", "sem entrada", "análise", "financeira"))
    assert not contains_financing_approval_claim(joined)


@pytest.mark.asyncio
async def test_q_intent_correction_cash_recalculates_next_field() -> None:
    facts = {
        "desired_model": "Civic",
        "deal_type": "purchase",
        "payment_method": "financing",
        "down_payment": 0,
    }

    async def understand(_text, _state):
        return TurnFacts(
            intent=BusinessIntent.PURCHASE,
            language="pt-BR",
            facts={"payment_method": "cash"},
            explicit_corrections=["payment_method"],
        )

    result = await process_turn(
        state=_state(
            intent=BusinessIntent.PURCHASE_FINANCING,
            facts=facts,
            last_inventory_search_key=inventory_search_key(facts),
            last_shown_vehicle_ids=["civic-1"],
            pending_question="desired_installment",
            assistant_turn_count=4,
        ),
        inbound_text="Na verdade vai ser à vista",
        understand=understand,
    )
    joined = _joined(result.outbound_texts)
    assert result.state.facts.get("payment_method") in {"cash", "a_vista"}
    assert "vista" in joined or "contado" in joined
    assert result.action_plan.ask_field != "desired_installment"
    assert result.action_plan.ask_field != "down_payment"


def test_validator_blocks_internal_leak_and_reintro() -> None:
    plan = build_dialogue_plan(
        inbound_text="Ok",
        action=Action.ASK_INFO,
        ask_field="desired_installment",
        intent=BusinessIntent.PURCHASE_FINANCING,
        should_introduce=False,
        assistant_turn_count=2,
        facts_context={"payment_method": "financing"},
    )
    bubbles, result = validate_dialogue_plan(
        ["Oi! Sou a Júlia da FacilCar. Vou fazer o handoff da triagem no CRM."],
        plan,
        language="pt-BR",
        customer_name="Mateus",
    )
    joined = _joined(bubbles)
    assert "handoff" not in joined
    assert "triagem" not in joined
    assert "crm" not in joined
    assert result.get("violations")
