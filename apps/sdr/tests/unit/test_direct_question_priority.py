"""Phase 9R Frente B — unanswered commercial questions precede visit/handoff.

Seams: decide, build_dialogue_plan, validate_dialogue_plan, compose fallback.

Customer asking about vehicle equipment is not a vendor emergency.
Unknown catalog evidence must not be treated as absence.
"""

from __future__ import annotations

import os

import pytest

from sdr.application.process_turn import process_turn
from sdr.config import get_settings
from sdr.domain.decision import decide, inventory_search_key
from sdr.domain.dialogue_plan import (
    DialogueAct,
    DirectQuestionKind,
    build_dialogue_plan,
    classify_direct_questions,
    fallback_bubbles,
    unanswered_questions_for_turn,
)
from sdr.domain.qualification_policy import (
    ACT_ASK_REMAINING_DOCUMENTS,
    ACT_HANDOFF,
    ACT_INVITE_VISIT,
    PRIMARY_ANSWER_QUESTION,
    PRIMARY_ASK_REMAINING_DOCUMENTS,
    PRIMARY_HANDOFF,
    PRIMARY_INVITE_VISIT,
)
from sdr.domain.qualifications import refresh_actionability
from sdr.domain.types import (
    Action,
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    HandoffSignals,
    TurnFacts,
)
from sdr.understanding.validator import validate_dialogue_plan

SUNROOF_Q = "Esse carro tem teto solar panorâmico de série?"
EQUIVALENT_Q = "Esse tem piloto automático adaptativo?"
VISIT_ONLY = ["Que tal segunda-feira, 7/09 às 14h ou terça-feira, 8/09 às 9h30?"]
INVENTED_YES = ["Sim, tem teto solar panorâmico de série."]
ABSENT_WITHOUT_EVIDENCE = ["Esse carro não tem teto solar panorâmico."]
HONEST_UNKNOWN = [
    "Não tenho essa informação confirmada no estoque. Posso pedir ao vendedor para verificar para você."
]


@pytest.fixture(autouse=True)
def _no_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    os.environ["OPENAI_API_KEY"] = ""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _state(**kwargs) -> ConversationCanonicalState:
    base = ConversationCanonicalState(
        thread_id="t-q-priority",
        customer=CustomerState(phone="5511999990009", name="Bruno Azevedo"),
        intent=kwargs.pop("intent", BusinessIntent.PURCHASE_FINANCING),
        language="pt-BR",
        facts=kwargs.pop("facts", {}),
    )
    for key, value in kwargs.items():
        setattr(base, key, value)
    return refresh_actionability(base)


def _handoff_ready(**kwargs) -> ConversationCanonicalState:
    facts = {
        "desired_model": "Strada",
        "desired_vehicle_text": "Strada",
        "deal_type": "purchase",
        "payment_method": "financing",
        "down_payment": 0,
        "desired_installment": 1500,
        "name": "Bruno Azevedo",
        **kwargs.pop("facts", {}),
    }
    shown = kwargs.pop(
        "last_shown_vehicle_ids",
        ["VH-STRADA-2021", "VH-STRADA-2017", "VH-STRADA-2018"],
    )
    return _state(
        facts=facts,
        last_inventory_search_key=inventory_search_key(facts),
        last_shown_vehicle_ids=shown,
        primary_vehicle_id=kwargs.pop("primary_vehicle_id", "VH-STRADA-2018"),
        documents_asked=True,
        installment_asked=True,
        assistant_turn_count=4,
        **kwargs,
    )


def _attach_questions(state: ConversationCanonicalState, inbound: str, **kwargs) -> ConversationCanonicalState:
    state.unanswered_questions = unanswered_questions_for_turn(inbound, **kwargs)
    return state


def _equipment_plan(inbound: str, **kwargs) -> object:
    facts = kwargs.pop("facts_context", {"desired_model": "Strada"})
    return build_dialogue_plan(
        inbound_text=inbound,
        action=kwargs.pop("action", Action.ASK_INFO),
        ask_field=kwargs.pop("ask_field", None),
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts_context=facts,
        assistant_turn_count=4,
        state=kwargs.pop("state", None),
        turn_facts=kwargs.pop("turn_facts", None),
        **kwargs,
    )


def _commercial_question(plan) -> dict:
    for item in plan.direct_questions:
        if item.get("kind") != DirectQuestionKind.WELLBEING.value:
            return item
    raise AssertionError("expected a commercial direct question on the plan")


# ---------------------------------------------------------------------------
# B1  unknown equipment → explicit uncertainty required
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("inbound", [SUNROOF_Q, EQUIVALENT_Q])
def test_b1_unknown_equipment_requires_uncertainty(inbound: str) -> None:
    plan = _equipment_plan(inbound)
    question = _commercial_question(plan)
    assert question["certainty"] == "unknown"
    assert question.get("subject")
    assert DialogueAct.ANSWER_DIRECT_QUESTION.value in plan.acts
    assert plan.primary_action == PRIMARY_ANSWER_QUESTION

    _bad, invented = validate_dialogue_plan(INVENTED_YES, plan)
    assert invented["pass"] is False
    assert "invented_information" in (invented.get("violations") or [])

    bubbles, honest = validate_dialogue_plan(HONEST_UNKNOWN, plan)
    assert honest["pass"] is True
    joined = " ".join(bubbles).lower()
    assert any(token in joined for token in ("não tenho", "não confirmo", "vendedor", "equipe"))


# ---------------------------------------------------------------------------
# B2  authorized option present → factual answer allowed (not a model heuristic)
# ---------------------------------------------------------------------------

def test_b2_authorized_option_allows_factual_answer() -> None:
    plan = _equipment_plan(
        SUNROOF_Q,
        facts_context={
            "desired_model": "Strada",
            "authorized_options": {"teto solar panorâmico": True},
        },
    )
    question = _commercial_question(plan)
    assert question["certainty"] == "confirmed"
    bubbles, result = validate_dialogue_plan(
        ["Sim, esse veículo tem teto solar panorâmico."],
        plan,
    )
    assert result["pass"] is True
    assert "teto solar panorâmico" in " ".join(bubbles).lower()


# ---------------------------------------------------------------------------
# B3  must not assert equipment absent without evidence
# ---------------------------------------------------------------------------

def test_b3_must_not_assert_absence_without_evidence() -> None:
    plan = _equipment_plan(SUNROOF_Q)
    assert _commercial_question(plan)["certainty"] == "unknown"
    _bubbles, result = validate_dialogue_plan(ABSENT_WITHOUT_EVIDENCE, plan)
    assert result["pass"] is False
    assert "unconfirmed_absence" in (result.get("violations") or [])


# ---------------------------------------------------------------------------
# B4  direct question + new fact in the same batch: both treated
# ---------------------------------------------------------------------------

def test_b4_question_and_new_fact_both_treated() -> None:
    plan = _equipment_plan(
        "Esse carro tem teto solar? Parcela de 1500",
        turn_facts=TurnFacts(
            intent=BusinessIntent.PURCHASE_FINANCING,
            facts={"desired_installment": 1500},
        ),
        facts_context={"desired_model": "Strada", "desired_installment": 1500},
    )
    assert DialogueAct.ANSWER_DIRECT_QUESTION.value in plan.acts
    assert DialogueAct.ACKNOWLEDGE_FACT.value in plan.acts
    assert "desired_installment" in plan.facts_to_acknowledge


# ---------------------------------------------------------------------------
# B5  direct question precedes visit
# ---------------------------------------------------------------------------

def test_b5_direct_question_precedes_visit() -> None:
    ready = _handoff_ready()
    assert ready.handoff_ready is True
    without_question = decide(_handoff_ready())
    assert without_question.action == Action.REGISTER_VISIT_INTEREST

    state = _attach_questions(_handoff_ready(), SUNROOF_Q)
    plan = decide(state)
    assert plan.action != Action.REGISTER_VISIT_INTEREST
    assert plan.primary_action == PRIMARY_ANSWER_QUESTION
    assert PRIMARY_INVITE_VISIT != plan.primary_action
    assert ACT_INVITE_VISIT in (plan.forbidden_concurrent_actions or [])


@pytest.mark.asyncio
async def test_b5_process_turn_does_not_invite_visit_while_question_open() -> None:
    async def understand(_text, _state):
        return TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING, language="pt-BR")

    result = await process_turn(
        state=_handoff_ready(),
        inbound_text=SUNROOF_Q,
        understand=understand,
    )
    assert result.action_plan.action != Action.REGISTER_VISIT_INTEREST
    assert result.action_plan.primary_action == PRIMARY_ANSWER_QUESTION
    joined = " ".join(result.outbound_texts).lower()
    assert "14h" not in joined and "9h30" not in joined
    assert any(token in joined for token in ("não tenho", "não confirmo", "vendedor", "equipe"))


@pytest.mark.parametrize(
    "inbound",
    [
        "Quero marcar uma visita, seria possível no sábado?",
        "Dá para ir aí na terça de manhã?",
        "Pode ser sábado?",
        "Sábado de manhã serve?",
        "Que tal sábado?",
        "Consigo ir amanhã?",
        "Posso ir aí amanhã?",
        "Vocês abrem no sábado?",
        "Fica melhor na quinta?",
    ],
)
def test_visit_scheduling_question_does_not_block_visit_invite(inbound: str) -> None:
    """A visit-scheduling question is the visit path, not an unanswered catalog fact."""
    blocking = unanswered_questions_for_turn(inbound)
    assert blocking == []
    state = _handoff_ready(signals=HandoffSignals(visit_intent=True))
    state.unanswered_questions = blocking
    plan = decide(state)
    assert plan.action in {Action.REGISTER_VISIT_INTEREST, Action.HANDOFF_VENDOR}
    assert plan.primary_action != PRIMARY_ANSWER_QUESTION


def test_equipment_question_still_blocks_visit_when_visit_is_also_mentioned() -> None:
    inbound = "Esse carro tem teto solar panorâmico de série? Quero marcar uma visita."
    blocking = unanswered_questions_for_turn(inbound)
    assert blocking
    assert any(item.get("kind") == DirectQuestionKind.UNKNOWN.value for item in blocking)
    state = _attach_questions(_handoff_ready(signals=HandoffSignals(visit_intent=True)), inbound)
    plan = decide(state)
    assert plan.action != Action.REGISTER_VISIT_INTEREST
    assert plan.primary_action == PRIMARY_ANSWER_QUESTION


# ---------------------------------------------------------------------------
# B6  direct question precedes remaining-documents ask
# ---------------------------------------------------------------------------

def test_b6_direct_question_precedes_remaining_documents() -> None:
    docs = _handoff_ready(
        document_received=True,
        facts={"document_status": {"cnh": "received"}},
    )
    without_question = decide(
        _handoff_ready(
            document_received=True,
            facts={"document_status": {"cnh": "received"}},
        )
    )
    assert without_question.primary_action == PRIMARY_ASK_REMAINING_DOCUMENTS

    state = _attach_questions(docs, SUNROOF_Q)
    plan = decide(state)
    assert plan.ask_field != "documents"
    assert plan.primary_action == PRIMARY_ANSWER_QUESTION
    assert ACT_ASK_REMAINING_DOCUMENTS in (plan.forbidden_concurrent_actions or [])


# ---------------------------------------------------------------------------
# B7  question precedes handoff except explicit vendor request
# Rule: "tem teto solar?" is NOT a vendor emergency. explicit_handoff may still win.
# ---------------------------------------------------------------------------

def test_b7_question_is_not_vendor_emergency() -> None:
    state = _attach_questions(_handoff_ready(visit_invited=True), SUNROOF_Q)
    plan = decide(state)
    assert plan.action != Action.HANDOFF_VENDOR
    assert plan.primary_action == PRIMARY_ANSWER_QUESTION
    assert ACT_HANDOFF in (plan.forbidden_concurrent_actions or [])


def test_b7_explicit_vendor_request_may_still_win() -> None:
    state = _attach_questions(
        _handoff_ready(signals=HandoffSignals(explicit_handoff=True)),
        SUNROOF_Q,
    )
    plan = decide(state)
    assert plan.action == Action.HANDOFF_VENDOR
    assert plan.primary_action == PRIMARY_HANDOFF


# ---------------------------------------------------------------------------
# B8  composer output that ignores the question is rejected
# ---------------------------------------------------------------------------

def test_b8_ignoring_the_question_is_rejected() -> None:
    plan = _equipment_plan(SUNROOF_Q, action=Action.REGISTER_VISIT_INTEREST)
    _bubbles, result = validate_dialogue_plan(VISIT_ONLY, plan)
    assert result["pass"] is False
    assert "ignored_direct_question" in (result.get("violations") or [])


# ---------------------------------------------------------------------------
# B9  retry is still subject to the same contract
# ---------------------------------------------------------------------------

def test_b9_retry_output_still_rejected_if_it_ignores_the_question() -> None:
    plan = _equipment_plan(SUNROOF_Q)
    retry_copy = ["Que tal passar na loja amanhã às 9h30 para ver o carro?"]
    _bubbles, first = validate_dialogue_plan(VISIT_ONLY, plan)
    _retry, second = validate_dialogue_plan(retry_copy, plan)
    assert first["pass"] is False
    assert second["pass"] is False
    assert "ignored_direct_question" in (second.get("violations") or [])


# ---------------------------------------------------------------------------
# B10  contextual fallback answers the subject, does not pivot to visit slots
# ---------------------------------------------------------------------------

def test_b10_fallback_answers_subject_instead_of_visit_slots() -> None:
    plan = _equipment_plan(SUNROOF_Q, action=Action.REGISTER_VISIT_INTEREST)
    bubbles = fallback_bubbles(plan, language="pt-BR")
    joined = " ".join(bubbles).lower()
    assert bubbles
    assert "14h" not in joined
    assert "9h30" not in joined
    assert "que tal" not in joined
    assert any(token in joined for token in ("não tenho", "não confirmo", "vendedor", "equipe"))
    assert any(
        token in joined
        for token in ("teto", "informação", "estoque", "detalhe", "verificar")
    )
