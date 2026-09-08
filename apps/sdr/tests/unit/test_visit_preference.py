"""Phase 4 — visit preference without agenda loop or handoff block."""

from __future__ import annotations

from datetime import date, datetime, time, timezone

import pytest

from sdr.application.process_turn import process_turn
from sdr.domain.clock import GOLDEN_CLOCK_ISO, set_clock
from sdr.domain.decision import decide, inventory_search_key
from sdr.domain.types import (
    Action,
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    HandoffSignals,
    LifecycleStatus,
    TurnFacts,
)
from sdr.domain.visit import (
    FORBIDDEN_CUSTOMER_PHRASES,
    customer_copy_leaks_process,
    parse_visit_utterance,
)

TUESDAY_SLOTS = [
    "terça-feira, 8/09 às 9h30",
    "terça-feira, 8/09 às 14h",
]


@pytest.fixture(autouse=True)
def _freeze_golden_clock() -> None:
    set_clock(GOLDEN_CLOCK_ISO)
    yield
    set_clock(None)


def _triaged_after_invite(**kwargs) -> ConversationCanonicalState:
    facts = {
        "desired_model": "Fox",
        "deal_type": "purchase",
        "payment_method": "financing",
        "down_payment": 0,
        "desired_installment": 2000,
        "name": "Mateus Ferreira",
        "document_type": "CNH",
    }
    from sdr.domain.types import Actionability

    state = ConversationCanonicalState(
        thread_id="visit-phase4",
        customer=CustomerState(phone="5511999999999", name="Mateus Ferreira"),
        intent=BusinessIntent.PURCHASE_FINANCING,
        language="pt-BR",
        facts=facts,
        last_inventory_search_key=inventory_search_key(facts),
        last_shown_vehicle_ids=["fox-v1"],
        assistant_turn_count=5,
        visit_invited=True,
        pending_question="visit",
        installment_asked=True,
        documents_asked=True,
        offered_visit_slots=list(TUESDAY_SLOTS),
    )
    state.business.actionability = Actionability.ACTIONABLE
    state.lifecycle.status = LifecycleStatus.READY_FOR_HANDOFF
    for key, value in kwargs.items():
        setattr(state, key, value)
    return state


def _understand(text: str, visit_intent: bool = False) -> object:
    async def _fn(_text: str, _state: ConversationCanonicalState) -> TurnFacts:
        return TurnFacts(
            intent=BusinessIntent.PURCHASE_FINANCING,
            language="pt-BR",
            facts={},
            signals=HandoffSignals(visit_intent=True if visit_intent else None),
        )

    return _fn


def _assert_no_process_leak(texts: list[str]) -> None:
    joined = " ".join(texts).lower()
    assert not customer_copy_leaks_process(joined), joined
    for phrase in FORBIDDEN_CUSTOMER_PHRASES:
        assert phrase not in joined


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def test_b_amanha_930_uses_canonical_clock() -> None:
    parsed = parse_visit_utterance("amanhã às 9:30", TUESDAY_SLOTS)
    assert parsed.date == date(2026, 9, 8)
    assert parsed.time == time(9, 30)
    assert parsed.period is None
    assert parsed.within_store_hours is True


def test_c_full_tuesday_date_same_result() -> None:
    parsed = parse_visit_utterance("Terça-feira 8/09 às 9:30", TUESDAY_SLOTS)
    assert parsed.date == date(2026, 9, 8)
    assert parsed.time == time(9, 30)


def test_j_utc_day_boundary_does_not_shift_brt_tomorrow() -> None:
    utc_tuesday = datetime(2026, 9, 8, 2, 0, tzinfo=timezone.utc)
    parsed = parse_visit_utterance("amanhã às 9:30", now=utc_tuesday)
    assert utc_tuesday.date() == date(2026, 9, 8)
    assert parsed.date == date(2026, 9, 8)


def test_p_partial_state_is_distinguishable() -> None:
    interest = parse_visit_utterance("Quero ir aí ver o carro")
    assert interest.interest is True
    assert interest.date is None
    assert interest.time is None
    assert interest.period is None

    day_only = parse_visit_utterance("Vou amanhã")
    assert day_only.date == date(2026, 9, 8)
    assert day_only.time is None
    assert day_only.period is None

    period = parse_visit_utterance("Amanhã de manhã")
    assert period.date == date(2026, 9, 8)
    assert period.period == "morning"
    assert period.time is None

    full = parse_visit_utterance("Amanhã às 9h30")
    assert full.date == date(2026, 9, 8)
    assert full.time == time(9, 30)
    assert full.period is None


def test_ordinal_and_courtesy_and_decline_parser() -> None:
    second = parse_visit_utterance("Pode ser o segundo horário", TUESDAY_SLOTS)
    assert second.accepted_offered is True
    assert second.offered_index == 1
    assert second.time == time(14, 0)

    courtesy = parse_visit_utterance("Obrigado")
    assert courtesy.courtesy is True
    assert courtesy.accepted_offered is False
    assert courtesy.declined is False
    assert courtesy.date is None

    decline = parse_visit_utterance("Não consigo ir agora")
    assert decline.declined is True
    assert decline.accepted_offered is False


# ---------------------------------------------------------------------------
# process_turn
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_exact_accept_930_confirms_once_and_handoffs() -> None:
    state = _triaged_after_invite()
    result = await process_turn(
        state=state,
        inbound_text="Pode ser amanhã às 9:30 então.",
        understand=_understand("x", visit_intent=True),
        pool=None,
    )
    assert result.action_plan.action == Action.HANDOFF_VENDOR
    assert result.state.visit_time == "09:30"
    assert result.state.visit_date == "2026-09-08"
    assert result.state.visit_accepted_offered is True
    joined = " ".join(result.outbound_texts).lower()
    assert "9h30" in joined or "9:30" in joined
    assert "que tal" not in joined
    assert "14h" not in joined
    assert "te esperamos" in joined
    _assert_no_process_leak(result.outbound_texts)
    assert result.outbound_texts.count(result.outbound_texts[0]) == 1 or len(result.outbound_texts) <= 2


@pytest.mark.asyncio
async def test_d_vou_amanha_registers_date_without_hour() -> None:
    state = _triaged_after_invite()
    result = await process_turn(
        state=state,
        inbound_text="Vou amanhã",
        understand=_understand("x", visit_intent=True),
        pool=None,
    )
    assert result.action_plan.action == Action.HANDOFF_VENDOR
    assert result.state.visit_date == "2026-09-08"
    assert result.state.visit_time is None
    joined = " ".join(result.outbound_texts).lower()
    assert "que tal" not in joined
    assert "te esperamos" not in joined
    _assert_no_process_leak(result.outbound_texts)


@pytest.mark.asyncio
async def test_e_period_does_not_invent_clock() -> None:
    state = _triaged_after_invite()
    result = await process_turn(
        state=state,
        inbound_text="Amanhã de manhã",
        understand=_understand("x", visit_intent=True),
        pool=None,
    )
    assert result.action_plan.action == Action.HANDOFF_VENDOR
    assert result.state.visit_date == "2026-09-08"
    assert result.state.visit_period == "morning"
    assert result.state.visit_time is None
    _assert_no_process_leak(result.outbound_texts)


@pytest.mark.asyncio
async def test_f_ordinal_second_slot() -> None:
    state = _triaged_after_invite()
    result = await process_turn(
        state=state,
        inbound_text="Pode ser o segundo horário",
        understand=_understand("x", visit_intent=True),
        pool=None,
    )
    assert result.action_plan.action == Action.HANDOFF_VENDOR
    assert result.state.visit_accepted_offered is True
    assert result.state.visit_time == "14:00"
    joined = " ".join(result.outbound_texts).lower()
    assert "9h30" not in joined
    _assert_no_process_leak(result.outbound_texts)


@pytest.mark.asyncio
async def test_g_obrigado_is_not_accept_and_does_not_loop() -> None:
    """Courtesy is not accept/refuse. Qualification is ready → handoff.

    Must not invent a visit, must not repeat the two slot offers, must not
    leak process language. Replaces the old ASK_INFO visit-schedule contract.
    """
    state = _triaged_after_invite()
    result = await process_turn(
        state=state,
        inbound_text="Obrigado",
        understand=_understand("x"),
        pool=None,
    )
    assert result.action_plan.action == Action.HANDOFF_VENDOR
    assert result.state.visit_accepted_offered is False
    assert result.state.visit_date is None
    assert result.state.visit_time is None
    joined = " ".join(result.outbound_texts).lower()
    assert "que tal" not in joined
    assert "9h30" not in joined or "14h" not in joined
    assert "te esperamos" not in joined
    _assert_no_process_leak(result.outbound_texts)


@pytest.mark.asyncio
async def test_h_decline_does_not_block_handoff() -> None:
    state = _triaged_after_invite()
    result = await process_turn(
        state=state,
        inbound_text="Não consigo ir agora",
        understand=_understand("x"),
        pool=None,
    )
    assert result.action_plan.action == Action.HANDOFF_VENDOR
    assert result.state.visit_declined is True
    joined = " ".join(result.outbound_texts).lower()
    assert "que tal" not in joined
    _assert_no_process_leak(result.outbound_texts)


@pytest.mark.asyncio
async def test_i_outside_hours_registers_without_claiming_availability() -> None:
    state = _triaged_after_invite()
    result = await process_turn(
        state=state,
        inbound_text="Pode ser domingo às 10h",
        understand=_understand("x", visit_intent=True),
        pool=None,
    )
    assert result.action_plan.action == Action.HANDOFF_VENDOR
    assert result.state.visit_time == "10:00"
    assert result.state.visit_within_hours is False
    joined = " ".join(result.outbound_texts).lower()
    assert "te esperamos" not in joined
    assert "encaminh" in joined
    _assert_no_process_leak(result.outbound_texts)


@pytest.mark.asyncio
async def test_k_idempotent_reprocess_after_handoff() -> None:
    state = _triaged_after_invite()
    first = await process_turn(
        state=state,
        inbound_text="Pode ser amanhã às 9:30 então.",
        understand=_understand("x", visit_intent=True),
        pool=None,
    )
    assert first.action_plan.action == Action.HANDOFF_VENDOR
    first_locations = [r for r in first.tool_results if r.get("tool") == "send_location"]
    second = await process_turn(
        state=first.state,
        inbound_text="Pode ser amanhã às 9:30 então.",
        understand=_understand("x", visit_intent=True),
        pool=None,
    )
    assert second.action_plan.action == Action.NO_REPLY
    assert second.outbound_texts == []
    assert second.tool_results == []
    assert first.state.visit_date == second.state.visit_date == "2026-09-08"
    assert len(first_locations) <= 1
    assert first.state.lifecycle.status == LifecycleStatus.HANDOFF_SENT


@pytest.mark.asyncio
async def test_l_post_handoff_time_updates_without_second_handoff() -> None:
    state = _triaged_after_invite()
    first = await process_turn(
        state=state,
        inbound_text="Vou amanhã",
        understand=_understand("x", visit_intent=True),
        pool=None,
    )
    assert first.action_plan.action == Action.HANDOFF_VENDOR
    second = await process_turn(
        state=first.state,
        inbound_text="às 9:30",
        understand=_understand("x", visit_intent=True),
        pool=None,
    )
    assert second.action_plan.action == Action.NO_REPLY
    assert second.outbound_texts == []
    assert second.state.visit_date == "2026-09-08"
    assert second.state.visit_time == "09:30"
    assert second.state.lifecycle.status == LifecycleStatus.HANDOFF_SENT
    assert second.state.last_inventory_search_key == first.state.last_inventory_search_key


@pytest.mark.asyncio
async def test_n_does_not_repeat_offer_after_accept() -> None:
    state = _triaged_after_invite()
    result = await process_turn(
        state=state,
        inbound_text="Pode ser o primeiro horário",
        understand=_understand("x", visit_intent=True),
        pool=None,
    )
    joined = " ".join(result.outbound_texts).lower()
    assert "que tal" not in joined
    assert "14h" not in joined
    _assert_no_process_leak(result.outbound_texts)


@pytest.mark.asyncio
async def test_o_customer_copy_forbids_process_terms() -> None:
    state = _triaged_after_invite()
    result = await process_turn(
        state=state,
        inbound_text="Pode ser amanhã às 9:30 então.",
        understand=_understand("x", visit_intent=True),
        pool=None,
    )
    _assert_no_process_leak(result.outbound_texts)


def test_m_other_intents_do_not_require_visit() -> None:
    from sdr.domain.types import Actionability

    cases = [
        (
            BusinessIntent.PURCHASE,
            {"desired_model": "Onix", "name": "Ana", "payment_method": "cash"},
        ),
        (
            BusinessIntent.TRADE,
            {
                "desired_model": "Onix",
                "trade_model": "Gol",
                "trade_year": "2018",
                "name": "Ana",
            },
        ),
        (
            BusinessIntent.SALE,
            {"trade_model": "Civic", "trade_year": "2020", "name": "Ana"},
        ),
        (
            BusinessIntent.CONSIGNMENT,
            {"trade_model": "Compass", "trade_year": "2021", "name": "Ana"},
        ),
        (
            BusinessIntent.REFINANCING,
            {
                "trade_model": "Renegade",
                "trade_year": "2019",
                "amount_needed": 20000,
                "name": "Ana",
            },
        ),
    ]
    for intent, facts in cases:
        state = ConversationCanonicalState(
            thread_id=f"visit-m-{intent.value}",
            customer=CustomerState(phone="1", name="Ana"),
            intent=intent,
            language="pt-BR",
            facts=facts,
            documents_asked=True,
            installment_asked=True,
            visit_invited=True,
            pending_question="visit",
            last_shown_vehicle_ids=["v1"],
            last_inventory_search_key=inventory_search_key(facts),
        )
        state.business.actionability = Actionability.ACTIONABLE
        plan = decide(state)
        assert plan.ask_field != "visit", intent.value
        assert plan.reason_code != "visit_schedule_ask", intent.value
        if plan.action == Action.ASK_INFO:
            assert plan.ask_field not in {None, "visit"}
