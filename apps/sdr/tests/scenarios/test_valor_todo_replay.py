"""Replay: 'valor todo' — down_payment=0 produces correct ack template.

Scenario:
  State: financing roteiro in progress, pending_question='down_payment'
  Inbound: "Valor todo" (or "sem entrada") → overlay sets down_payment=0
  Expected:
    - action=ASK_INFO (next roteiro field: desired_installment)
    - outbound ack contains "valor todo" phrasing (not "entrada")
    - outbound does NOT contain the specific amount echoed back
    - outbound does NOT say "taxas tendem" or similar conditional promises

Tests the full process_turn pipeline to verify:
  1. _NO_DOWN regex correctly sets down_payment=0 via overlay_pending_question
  2. ack_kind='down_payment' is forced through template (not LLM)
  3. Template for zero-entry says "financiar o valor todo" (not "anotei a entrada")
  4. No amount echo (client may say "100 mil" — we must not repeat it)
"""

from __future__ import annotations

import os

import pytest

from sdr.application.process_turn import process_turn
from sdr.domain.decision import inventory_search_key
from sdr.domain.types import (
    Action,
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    TurnFacts,
)
from sdr.config import get_settings


@pytest.fixture(autouse=True)
def _no_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    os.environ["OPENAI_API_KEY"] = ""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _financing_state_awaiting_down_payment() -> ConversationCanonicalState:
    """State: financing roteiro, payment_method confirmed, waiting for down_payment."""
    facts = {
        "desired_model": "Corolla",
        "deal_type": "purchase",
        "payment_method": "financing",
    }
    state = ConversationCanonicalState(
        thread_id="valor-todo-replay",
        customer=CustomerState(phone="5511999999999"),
        intent=BusinessIntent.PURCHASE_FINANCING,
        language="pt-BR",
        facts=facts,
        last_inventory_search_key=inventory_search_key(facts),
        last_shown_vehicle_ids=["corolla-v1"],
        pending_question="down_payment",
    )
    state.assistant_turn_count = 3
    return state


@pytest.mark.asyncio
async def test_valor_todo_sets_down_payment_zero_and_advances() -> None:
    """'Valor todo' → down_payment=0 via overlay → ASK_INFO for desired_installment."""
    state = _financing_state_awaiting_down_payment()

    async def _understand_valor_todo(text: str, s: ConversationCanonicalState) -> TurnFacts:
        # LLM would return these; overlay_pending_question will also set down_payment=0
        return TurnFacts(
            intent=BusinessIntent.PURCHASE_FINANCING,
            language="pt-BR",
            facts={},  # LLM may not catch this; overlay handles it
        )

    result = await process_turn(
        state=state,
        inbound_text="Valor todo",
        understand=_understand_valor_todo,
        pool=None,
    )

    # Must have set down_payment=0 in state via overlay
    assert result.state.facts.get("down_payment") == 0, (
        f"Expected down_payment=0 after 'Valor todo', "
        f"got {result.state.facts.get('down_payment')!r}. "
        "_NO_DOWN regex in overlay_pending_question must match 'valor todo'."
    )

    # Must advance to desired_installment question
    assert result.action_plan.action == Action.ASK_INFO, (
        f"Expected ASK_INFO (next roteiro field), got {result.action_plan.action!r}."
    )
    assert result.action_plan.ask_field == "desired_installment", (
        f"Expected ask_field='desired_installment', got {result.action_plan.ask_field!r}."
    )

    # Must produce non-empty response
    assert len(result.outbound_texts) > 0, "Must produce at least one outbound bubble."

    joined = " ".join(result.outbound_texts)

    # Template must acknowledge zero-entry without implying an "entrada"
    assert "valor todo" in joined.lower() or "valor total" in joined.lower(), (
        f"Response must confirm zero-entry with 'valor todo' or 'valor total' phrasing. "
        f"Got: {result.outbound_texts}"
    )

    # Must NOT echo specific amounts (e.g., "100 mil", "30 mil")
    import re
    assert not re.search(r"\d+\s*(?:mil|k\b)", joined, re.I), (
        f"Response must not echo specific amounts. Got: {result.outbound_texts}"
    )

    # Must NOT say "anotei a entrada" (wrong for zero-entry case)
    assert "anotei a entrada" not in joined.lower(), (
        f"'Anotei a entrada' is wrong for zero-entry 'valor todo'. Got: {result.outbound_texts}"
    )


@pytest.mark.asyncio
async def test_sem_entrada_same_as_valor_todo() -> None:
    """'Sem entrada' is semantically equivalent to 'valor todo' — same down_payment=0 result."""
    state = _financing_state_awaiting_down_payment()

    async def _understand_sem_entrada(text: str, s: ConversationCanonicalState) -> TurnFacts:
        return TurnFacts(
            intent=BusinessIntent.PURCHASE_FINANCING,
            language="pt-BR",
            facts={},
        )

    result = await process_turn(
        state=state,
        inbound_text="Sem entrada",
        understand=_understand_sem_entrada,
        pool=None,
    )

    assert result.state.facts.get("down_payment") == 0, (
        f"Expected down_payment=0 for 'Sem entrada'. "
        f"Got: {result.state.facts.get('down_payment')!r}."
    )
    assert result.action_plan.action == Action.ASK_INFO
    assert result.action_plan.ask_field == "desired_installment"

    joined = " ".join(result.outbound_texts).lower()
    assert "valor todo" in joined or "valor total" in joined, (
        f"Response for 'Sem entrada' must also use zero-entry phrasing. Got: {result.outbound_texts}"
    )


@pytest.mark.asyncio
async def test_positive_down_payment_ack_does_not_say_valor_todo() -> None:
    """Positive down_payment (e.g., 30000) → 'Certo, anotei a entrada.' (NOT 'valor todo')."""
    state = _financing_state_awaiting_down_payment()

    async def _understand_positive_entry(text: str, s: ConversationCanonicalState) -> TurnFacts:
        return TurnFacts(
            intent=BusinessIntent.PURCHASE_FINANCING,
            language="pt-BR",
            facts={"down_payment": 30000},
        )

    result = await process_turn(
        state=state,
        inbound_text="Tenho 30 mil de entrada",
        understand=_understand_positive_entry,
        pool=None,
    )

    assert result.state.facts.get("down_payment") == 30000
    assert result.action_plan.action == Action.ASK_INFO
    assert result.action_plan.ask_field == "desired_installment"

    joined = " ".join(result.outbound_texts).lower()

    # Must NOT echo the amount
    assert "30 mil" not in joined and "30000" not in joined, (
        f"Positive-entry ack must not echo the amount. Got: {result.outbound_texts}"
    )

    # Must NOT say "valor todo" for a positive entry
    assert "valor todo" not in joined and "valor total" not in joined, (
        f"Positive-entry ack must not say 'valor todo'. Got: {result.outbound_texts}"
    )
