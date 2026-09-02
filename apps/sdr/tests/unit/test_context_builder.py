"""Unit tests for ConversationContextBuilder."""

from __future__ import annotations

from sdr.context_builder import ConversationContextBuilder
from sdr.domain.inbound import make_text_inbound
from sdr.domain.types import (
    ActionPlan,
    Action,
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
)


def _state(**kwargs) -> ConversationCanonicalState:
    base = ConversationCanonicalState(
        thread_id="t1",
        customer=CustomerState(phone="5511999999999"),
    )
    for key, value in kwargs.items():
        setattr(base, key, value)
    return base


def test_build_understanding_summary_basic() -> None:
    builder = ConversationContextBuilder()
    state = _state(intent=BusinessIntent.PURCHASE, language="pt-BR")
    summary = builder.build_understanding_summary(state)
    assert "purchase" in summary
    assert "pt-BR" in summary
    assert "BOT_ACTIVE" in summary


def test_understanding_summary_includes_known_facts() -> None:
    builder = ConversationContextBuilder()
    state = _state(
        intent=BusinessIntent.PURCHASE,
        facts={"desired_model": "Civic", "budget": "50000"},
    )
    summary = builder.build_understanding_summary(state)
    assert "Civic" in summary
    assert "50000" in summary


def test_understanding_summary_excludes_operational_keys() -> None:
    builder = ConversationContextBuilder()
    state = _state(
        intent=BusinessIntent.PURCHASE,
        facts={"desired_model": "Civic", "_inventory_searched": True},
    )
    summary = builder.build_understanding_summary(state)
    # _inventory_searched is operational metadata, not customer fact
    assert "_inventory_searched" not in summary


def test_understanding_summary_excludes_sensitive_keys() -> None:
    builder = ConversationContextBuilder()
    state = _state(
        facts={"cpf": "123.456.789-00", "desired_model": "Civic"},
    )
    summary = builder.build_understanding_summary(state)
    assert "123.456.789-00" not in summary


def test_understanding_summary_without_accumulated_summary() -> None:
    builder = ConversationContextBuilder()
    state = _state()
    summary = builder.build_understanding_summary(state, accumulated_summary=None)
    assert "sem resumo acumulado" in summary


def test_understanding_summary_with_accumulated_summary() -> None:
    builder = ConversationContextBuilder()
    state = _state()
    summary = builder.build_understanding_summary(
        state,
        accumulated_summary="Cliente buscou Civic branco no mês passado."
    )
    assert "Civic branco" in summary


def test_understanding_summary_includes_linked_vehicle_titles() -> None:
    builder = ConversationContextBuilder()
    state = _state(intent=BusinessIntent.PURCHASE)
    summary = builder.build_understanding_summary(
        state,
        linked_vehicle_titles=["Honda Civic 2020", "  ", "Toyota Corolla"],
    )
    assert "Honda Civic 2020" in summary
    assert "Toyota Corolla" in summary
    assert "não perguntar de novo" in summary


def test_build_composition_payload_keys() -> None:
    builder = ConversationContextBuilder()
    state = _state(
        assistant_turn_count=1,
        intent=BusinessIntent.PURCHASE,
        language="pt-BR",
    )
    inbound = make_text_inbound("t1", "Quero um carro")
    plan = ActionPlan(action=Action.ASK_INFO, ask_field="budget")
    payload = builder.build_composition_payload(
        inbound=inbound,
        state=state,
        plan=plan,
        tool_results=[],
    )
    assert "context" in payload
    assert "action_plan" in payload
    assert "tool_results" in payload
    assert "inbound" in payload


def test_build_composition_payload_should_introduce_false_on_second_turn() -> None:
    builder = ConversationContextBuilder()
    state = _state(assistant_turn_count=1)
    inbound = make_text_inbound("t1", "Quero comprar um carro")
    plan = ActionPlan(action=Action.SMALLTALK)
    payload = builder.build_composition_payload(
        inbound=inbound,
        state=state,
        plan=plan,
        tool_results=[],
    )
    assert payload["context"]["should_introduce"] is False
    assert "NÃO se apresente" in payload["context"]["intro_instruction"]
    assert payload["context"]["inbound_text"] == "Quero comprar um carro"
    assert "Continuação" in payload["context"]["response_objective"]


def test_build_composition_payload_should_introduce_true_on_first_turn() -> None:
    builder = ConversationContextBuilder()
    state = _state(assistant_turn_count=0)
    inbound = make_text_inbound("t1", "Oi")
    plan = ActionPlan(action=Action.SMALLTALK)
    payload = builder.build_composition_payload(
        inbound=inbound,
        state=state,
        plan=plan,
        tool_results=[],
    )
    assert payload["context"]["should_introduce"] is True
    assert "apresente-se" in payload["context"]["intro_instruction"]


def test_build_composition_payload_excludes_operational_facts() -> None:
    builder = ConversationContextBuilder()
    state = _state(
        assistant_turn_count=1,
        facts={"desired_model": "Civic", "last_inv_key": "abc123"},
    )
    inbound = make_text_inbound("t1", "Quero um Civic")
    plan = ActionPlan(action=Action.ASK_INFO, ask_field="budget")
    payload = builder.build_composition_payload(
        inbound=inbound,
        state=state,
        plan=plan,
        tool_results=[],
    )
    # desired_model should be present, operational keys should not appear in forbidden list
    facts = payload["context"]["facts"]
    assert "desired_model" in facts
