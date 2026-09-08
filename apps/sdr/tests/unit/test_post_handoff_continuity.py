"""Phase 10 Frente C — commercially correct turns after HANDOFF_SENT.

HANDOFF_SENT is not silence. The vendor was notified once; later turns still
qualify / answer / ack until a human assumes. Exact LLM copy is not pinned
except the forbidden second-handoff confirmation.
"""

from __future__ import annotations

import os
import re

import pytest

from sdr.application.process_turn import process_turn
from sdr.config import get_settings
from sdr.domain.clock import GOLDEN_CLOCK_ISO, set_clock
from sdr.domain.decision import decide, inventory_search_key
from sdr.domain.dialogue_plan import build_dialogue_plan, contains_repeated_handoff_confirmation
from sdr.domain.inbound import ContentType, InboundTurn, MediaStatus, QuotedContext
from sdr.domain.ownership import vendor_already_notified
from sdr.domain.types import (
    Action,
    Actionability,
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    LifecycleState,
    LifecycleStatus,
    TurnFacts,
)
from sdr.domain.vehicle_reference import PresentedVehicleBinding
from sdr.domain.visit import parse_visit_utterance, should_send_store_location
from sdr.infrastructure.isolated_crm import IsolatedCrmStore


LEAD_ID = "lead-post-handoff-1"
STRADA_2021 = "veh-strada-2021"
STRADA_2017 = "veh-strada-2017"
STRADA_2018 = "veh-strada-2018"
CONV = "syn-conv-post-handoff"

TUESDAY_SLOTS = [
    "terça-feira, 8/09 às 9h30",
    "terça-feira, 8/09 às 14h",
]

_DEFERRED_DOC_ASK = re.compile(
    r"comprovante|renda|resid[eê]ncia|holerite",
    re.I,
)
_GREETING_REOPEN = re.compile(
    r"sou a j[uú]lia|ol[áa]!|como posso (?:te )?ajudar voc[eê] hoje",
    re.I,
)


@pytest.fixture(autouse=True)
def _no_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    os.environ["OPENAI_API_KEY"] = ""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _freeze_golden_clock() -> None:
    set_clock(GOLDEN_CLOCK_ISO)
    yield
    set_clock(None)


def _bindings() -> list[PresentedVehicleBinding]:
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


def _handoff_sent_state(**kwargs) -> ConversationCanonicalState:
    facts = {
        "desired_model": "Strada",
        "desired_vehicle_text": "Strada",
        "deal_type": "purchase",
        "payment_method": "financing",
        "down_payment": 0,
        "desired_installment": 1500,
        "name": "Mateus Ferreira",
        "document_status": {
            "cnh": "deferred",
            "proof_of_residence": "deferred",
            "proof_of_income": "deferred",
        },
        "documents_deferred": True,
        **kwargs.pop("facts", {}),
    }
    state = ConversationCanonicalState(
        thread_id=kwargs.pop("thread_id", CONV),
        customer=kwargs.pop(
            "customer",
            CustomerState(phone="5511999990000", name="Mateus Ferreira"),
        ),
        intent=kwargs.pop("intent", BusinessIntent.PURCHASE_FINANCING),
        language="pt-BR",
        facts=facts,
        last_inventory_search_key=inventory_search_key(facts),
        last_shown_vehicle_ids=kwargs.pop(
            "last_shown_vehicle_ids",
            [STRADA_2021, STRADA_2017, STRADA_2018],
        ),
        primary_vehicle_id=kwargs.pop("primary_vehicle_id", STRADA_2018),
        presented_vehicle_bindings=kwargs.pop("presented_vehicle_bindings", _bindings()),
        assistant_turn_count=kwargs.pop("assistant_turn_count", 6),
        visit_invited=True,
        visit_interest=True,
        visit_date="2026-09-08",
        visit_time="09:30",
        visit_preferred_time="terça-feira, 8/09 às 9h30",
        offered_visit_slots=list(TUESDAY_SLOTS),
        location_sent=True,
        documents_asked=True,
        remaining_documents_asked=True,
        installment_asked=True,
        installment_mismatch_offered=True,
        deferred_fields=["cnh", "proof_of_residence", "proof_of_income"],
        active_lead_ids=[LEAD_ID],
        lifecycle=LifecycleState(status=LifecycleStatus.HANDOFF_SENT),
    )
    state.business.actionability = Actionability.ACTIONABLE
    for key, value in kwargs.items():
        setattr(state, key, value)
    return state


def _understand(facts: dict | None = None, *, intent: BusinessIntent | None = None):
    async def _fn(_text: str, _state: ConversationCanonicalState) -> TurnFacts:
        return TurnFacts(
            intent=intent or BusinessIntent.PURCHASE_FINANCING,
            language="pt-BR",
            facts=dict(facts or {}),
        )

    return _fn


def _joined(texts: list[str]) -> str:
    return " ".join(texts).lower()


def _assert_no_second_handoff(result) -> None:
    assert result.action_plan.action != Action.HANDOFF_VENDOR
    assert result.action_plan.handoff is not True
    assert result.action_plan.reason_code != "ai_silenced"
    assert result.state.lifecycle.status == LifecycleStatus.HANDOFF_SENT
    tools = [r.get("tool") for r in result.tool_results]
    assert "notification" not in tools
    assert "handoff" not in tools
    assert "register_notification" not in tools
    joined = _joined(result.outbound_texts)
    assert "vou encaminhar" not in joined
    assert not contains_repeated_handoff_confirmation(" ".join(result.outbound_texts))


def _assert_continuation(result) -> None:
    _assert_no_second_handoff(result)
    assert result.action_plan.action != Action.NO_REPLY
    directive = result.response_directive
    assert directive is not None
    assert directive.should_introduce is False
    joined = _joined(result.outbound_texts)
    assert not _GREETING_REOPEN.search(joined)
    assert "sou a júlia" not in joined
    assert not joined.strip().startswith("oi")
    assert not joined.strip().startswith("olá")


def _document_inbound(*, kind: str, caption: str) -> InboundTurn:
    return InboundTurn(
        thread_id=CONV,
        content_type=ContentType.DOCUMENT,
        text=caption,
        media_status=MediaStatus.OK,
        raw_message_ref={"document_extracted": {"document_type": kind}},
    )


# ---------------------------------------------------------------------------
# C1 / C12 — document after handoff
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind,caption,component,ack_token",
    [
        ("CNH", "segue minha cnh", "cnh", "cnh"),
        ("INCOME_PROOF", "mande o comprovante de renda", "proof_of_income", "renda"),
    ],
)
async def test_c1_document_after_handoff_acks_without_second_handoff(
    kind: str,
    caption: str,
    component: str,
    ack_token: str,
) -> None:
    result = await process_turn(
        state=_handoff_sent_state(),
        inbound=_document_inbound(kind=kind, caption=caption),
        understand=_understand(),
    )
    _assert_continuation(result)
    assert result.state.document_received is True
    assert result.state.facts.get("document_status", {}).get(component) == "received"
    joined = _joined(result.outbound_texts)
    assert ack_token in joined or "recebi" in joined
    assert not _DEFERRED_DOC_ASK.search(joined) or ack_token in joined
    # Deferred remainder must not be re-asked as a pack.
    assert "holerite" not in joined
    assert result.action_plan.ask_field != "documents"
    assert result.state.active_lead_ids == [LEAD_ID]


# ---------------------------------------------------------------------------
# C2 — installment after handoff
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text,amount",
    [
        ("A parcela fica em 1800", 1800),
        ("Consigo pagar uns 2000 por mês", 2000),
    ],
)
async def test_c2_installment_after_handoff_acks_without_second_handoff(
    text: str,
    amount: int,
) -> None:
    result = await process_turn(
        state=_handoff_sent_state(),
        inbound_text=text,
        understand=_understand({"desired_installment": amount}),
    )
    _assert_continuation(result)
    assert result.state.facts.get("desired_installment") == amount
    joined = _joined(result.outbound_texts)
    assert any(token in joined for token in ("anotei", "parcela", "entendi", "certo"))


# ---------------------------------------------------------------------------
# C3 — down payment change, no funnel restart
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text,amount",
    [
        ("Vou dar 20 mil de entrada", 20000),
        ("Entrada de 15 mil então", 15000),
    ],
)
async def test_c3_down_payment_change_merges_without_restart(
    text: str,
    amount: int,
) -> None:
    previous = _handoff_sent_state()
    result = await process_turn(
        state=previous,
        inbound_text=text,
        understand=_understand({"down_payment": amount}),
    )
    _assert_continuation(result)
    assert result.state.facts.get("down_payment") == amount
    assert result.state.last_inventory_search_key == previous.last_inventory_search_key
    assert result.action_plan.action != Action.SHOW_OFFERS
    assert not any(r.get("tool") == "inventory_search" for r in result.tool_results)
    joined = _joined(result.outbound_texts)
    assert "comprar, trocar, vender" not in joined


# ---------------------------------------------------------------------------
# C4 — equipment question after handoff (9R uncertainty)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "Tem teto solar?",
        "Esse tem sensor de estacionamento?",
    ],
)
async def test_c4_equipment_question_after_handoff_answers_without_restart(
    text: str,
) -> None:
    previous = _handoff_sent_state()
    result = await process_turn(
        state=previous,
        inbound_text=text,
        understand=_understand(),
    )
    _assert_continuation(result)
    assert result.state.primary_vehicle_id == STRADA_2018
    assert result.action_plan.action != Action.SHOW_OFFERS
    assert not any(r.get("tool") == "inventory_search" for r in result.tool_results)
    joined = _joined(result.outbound_texts)
    assert any(
        token in joined
        for token in (
            "não tenho",
            "não consigo confirmar",
            "não consta",
            "verificar",
            "vendedor",
        )
    )
    assert result.action_plan.reason_code == "answer_direct_question"


# ---------------------------------------------------------------------------
# C5 / C8 — visit time change, no second location
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text,expected_time",
    [
        ("Consigo ir às 15h em vez de 9h30", "15:00"),
        ("Melhor às 16h então", "16:00"),
    ],
)
async def test_c5_visit_time_change_updates_without_second_handoff_or_location(
    text: str,
    expected_time: str,
) -> None:
    parsed = parse_visit_utterance(text, [])
    assert parsed.time is not None
    assert parsed.time.strftime("%H:%M") == expected_time

    previous = _handoff_sent_state()
    assert should_send_store_location(previous) is False
    result = await process_turn(
        state=previous,
        inbound_text=text,
        understand=_understand(),
    )
    _assert_continuation(result)
    assert result.state.visit_time == expected_time
    assert result.state.visit_date == "2026-09-08"
    assert not any(r.get("tool") == "send_location" for r in result.tool_results)
    assert result.action_plan.action != Action.SEND_LOCATION
    joined = _joined(result.outbound_texts)
    assert any(token in joined for token in ("anotei", "registrei", "preferência", "15h", "16h", "visita"))


# ---------------------------------------------------------------------------
# C6 — quoted reply can change primary without a new search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text,stanza,expected_primary",
    [
        ("Gostei dessa opção", "prov-img-2021", STRADA_2021),
        ("Quero essa", "prov-img-2017", STRADA_2017),
    ],
)
async def test_c6_quoted_reply_changes_primary_without_inventory_search(
    text: str,
    stanza: str,
    expected_primary: str,
) -> None:
    previous = _handoff_sent_state()
    key_before = previous.last_inventory_search_key
    inbound = InboundTurn(
        thread_id=CONV,
        content_type=ContentType.TEXT,
        text=text,
        media_status=MediaStatus.OK,
        quoted=[QuotedContext(stanza_id=stanza, quoted_text="Fiat Strada")],
    )
    result = await process_turn(
        state=previous,
        inbound=inbound,
        understand=_understand(),
    )
    _assert_continuation(result)
    assert result.state.primary_vehicle_id == expected_primary
    assert result.state.last_inventory_search_key == key_before
    assert result.action_plan.action != Action.SHOW_OFFERS
    assert not any(r.get("tool") == "inventory_search" for r in result.tool_results)


# ---------------------------------------------------------------------------
# C7 / C8 — decide + location request after pin already sent
# ---------------------------------------------------------------------------


def test_c7_decide_does_not_plan_second_handoff() -> None:
    state = _handoff_sent_state()
    assert vendor_already_notified(state) is True
    plan = decide(state)
    assert plan.action != Action.HANDOFF_VENDOR
    assert plan.handoff is not True
    assert plan.action != Action.NO_REPLY


def test_c8_location_request_after_sent_does_not_resend() -> None:
    state = _handoff_sent_state()
    state.location_request = True
    assert should_send_store_location(state) is False
    plan = decide(state)
    assert plan.action != Action.SEND_LOCATION
    assert not any(tc.get("tool") == "send_location" for tc in (plan.tool_calls or []))
    assert plan.action != Action.HANDOFF_VENDOR


# ---------------------------------------------------------------------------
# C9 — dialogue_plan / fallback must not repeat handoff confirmation
# ---------------------------------------------------------------------------


def test_c9_dialogue_plan_forbids_second_handoff_copy() -> None:
    state = _handoff_sent_state()
    plan = build_dialogue_plan(
        inbound_text="Anotei, mudei a parcela para 1800",
        action=Action.ASK_INFO,
        intent=BusinessIntent.PURCHASE_FINANCING,
        should_introduce=False,
        assistant_turn_count=6,
        facts_context=state.facts,
        turn_facts=TurnFacts(facts={"desired_installment": 1800}),
        state=state,
        lifecycle_status=LifecycleStatus.HANDOFF_SENT.value,
    )
    assert plan.skip_reintroduce is True
    assert "handoff_message" not in plan.acts
    joined_restrictions = " ".join(plan.restrictions).lower()
    assert "encaminhar" in joined_restrictions
    assert contains_repeated_handoff_confirmation(
        "Perfeito. Já organizei as informações e vou encaminhar para nossa equipe."
    )
    assert not contains_repeated_handoff_confirmation("Anotei a parcela em reais.")


# ---------------------------------------------------------------------------
# C10 / C11 — same lead on reread; qualify=False after first handoff
# ---------------------------------------------------------------------------


def test_c10_c11_crm_snapshot_keeps_same_lead_without_duplicate_notify() -> None:
    store = IsolatedCrmStore()
    first = _handoff_sent_state(crm_revision=1)
    first.lifecycle = LifecycleState(status=LifecycleStatus.READY_FOR_HANDOFF)
    created = store.create_from_state(first, first_inbound="Oi, vi as Stradas")
    first.active_lead_ids = [created["id"]]
    qualified = store.sync_from_state(created["id"], first, qualify=True, first_inbound="Oi, vi as Stradas")
    assert qualified["id"] == created["id"]
    assert store.handoff_count == 1
    assert store.qualified_notifications == 1

    later = _handoff_sent_state(crm_revision=2, active_lead_ids=[created["id"]])
    later.facts["desired_installment"] = 1800
    later.lifecycle = LifecycleState(status=LifecycleStatus.HANDOFF_SENT)
    updated = store.sync_from_state(created["id"], later, qualify=False)
    assert updated["id"] == created["id"]
    reread = store.reread_id(created["id"])
    assert reread is not None
    assert reread["id"] == created["id"]
    assert store.handoff_count == 1
    assert store.qualified_notifications == 1


@pytest.mark.asyncio
async def test_c11_process_turn_keeps_active_lead_ids() -> None:
    result = await process_turn(
        state=_handoff_sent_state(),
        inbound_text="A parcela fica em 1800",
        understand=_understand({"desired_installment": 1800}),
    )
    assert result.state.active_lead_ids == [LEAD_ID]
    _assert_continuation(result)


# ---------------------------------------------------------------------------
# Introduction contract after handoff
# ---------------------------------------------------------------------------


def test_should_introduce_stays_false_when_assistant_already_spoke() -> None:
    state = _handoff_sent_state(assistant_turn_count=6)
    plan = build_dialogue_plan(
        inbound_text="Ok",
        action=Action.SMALLTALK,
        should_introduce=False,
        assistant_turn_count=state.assistant_turn_count,
        state=state,
        lifecycle_status=LifecycleStatus.HANDOFF_SENT.value,
    )
    assert plan.skip_reintroduce is True
    assert state.assistant_turn_count > 0
