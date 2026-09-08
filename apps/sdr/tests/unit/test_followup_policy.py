"""Phase 11 Frente A — follow-up eligibility and wait-state policy.

Clock is frozen. No sleep. LLM suggestions are structured TurnFacts;
code decides schedule, attempts, and send authorization.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from sdr.domain.clock import TZ_BRT, set_clock
from sdr.domain.followup import (
    ConsentLevel,
    FollowUpCancelIntent,
    FollowUpRecord,
    FollowUpWaitState,
    PauseReason,
    TemporalKind,
    apply_followup_transition,
    authorizes_automatic_send,
    followup_decision,
    mark_awaiting_customer,
    normalize_temporal,
)
from sdr.domain.followup_config import (
    AWAITING_AFTER_FOLLOWUP_WINDOW,
    COMMERCIAL_SILENCE_WINDOW,
    DEFAULT_DAY_HOUR,
    MAX_ATTEMPTS,
)
from sdr.domain.merge import deterministic_merge
from sdr.domain.types import (
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    LifecycleState,
    LifecycleStatus,
    TurnFacts,
)

MONDAY_10 = "2026-09-07T10:00:00-03:00"
SATURDAY_20 = "2026-09-12T20:00:00-03:00"


@pytest.fixture(autouse=True)
def _freeze_clock() -> None:
    set_clock(MONDAY_10)
    yield
    set_clock(None)


def _qualifying(**kwargs) -> ConversationCanonicalState:
    wait = kwargs.pop("wait_state", FollowUpWaitState.ACTIVE_QUALIFICATION)
    record = kwargs.pop("followup", FollowUpRecord())
    lifecycle = kwargs.pop("lifecycle", LifecycleState(status=LifecycleStatus.QUALIFYING))
    state = ConversationCanonicalState(
        thread_id="t-followup",
        customer=CustomerState(phone="5511999999999", name="Bruno"),
        intent=BusinessIntent.PURCHASE_FINANCING,
        language="pt-BR",
        facts={"desired_model": "Strada", "payment_method": "financing"},
        assistant_turn_count=4,
        pending_question="documents",
        lifecycle=lifecycle,
        wait_state=wait.value if isinstance(wait, FollowUpWaitState) else wait,
        followup=record,
    )
    for key, value in kwargs.items():
        setattr(state, key, value)
    return state


def test_a1_documents_promised_tomorrow() -> None:
    state = _qualifying()
    facts = TurnFacts(
        intent=BusinessIntent.PURCHASE_FINANCING,
        pause_reason=PauseReason.DOCUMENTS_PROMISED.value,
        consent_level=ConsentLevel.EXPLICIT_TIME.value,
        temporal_commitment=(
            "Não estou com os comprovantes agora. Pode me chamar amanhã às 14h."
        ),
        pause_confidence=0.9,
    )
    inbound = "Não estou com os comprovantes agora. Pode me chamar amanhã às 14h."
    decision = followup_decision(state, facts, inbound_text=inbound)
    assert decision.eligible is True
    assert decision.send_now is False
    assert decision.authorize_send is False
    assert decision.wait_state == FollowUpWaitState.PAUSED_WITH_FOLLOWUP
    assert decision.pause_reason == PauseReason.DOCUMENTS_PROMISED
    assert decision.maximum_attempts == MAX_ATTEMPTS == 1
    assert decision.schedule_at is not None
    assert decision.schedule_at.date() == date(2026, 9, 8)
    assert decision.schedule_at.hour == 14
    assert decision.original_temporal_text is not None

    applied = apply_followup_transition(state, decision)
    omitted = TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING, facts={"budget": 40000})
    merged = deterministic_merge(applied, omitted)
    assert merged.wait_state == FollowUpWaitState.PAUSED_WITH_FOLLOWUP.value
    assert merged.followup.pause_reason == PauseReason.DOCUMENTS_PROMISED
    assert merged.followup.scheduled_at is not None


def test_a2_decision_with_spouse() -> None:
    state = _qualifying()
    facts = TurnFacts(
        intent=BusinessIntent.PURCHASE_FINANCING,
        pause_reason=PauseReason.DECISION_WITH_PARTNER.value,
        consent_level=ConsentLevel.CONTEXTUAL.value,
        temporal_commitment="Vou ver com meu marido e te retorno.",
    )
    decision = followup_decision(
        state, facts, inbound_text="Vou ver com meu marido e te retorno."
    )
    assert decision.eligible is True
    assert decision.may_ask_return_permission is True
    assert decision.send_now is False
    assert decision.pause_reason == PauseReason.DECISION_WITH_PARTNER
    assert decision.consent_level == ConsentLevel.CONTEXTUAL
    assert decision.schedule_at is None
    assert decision.fallback_resume_at is not None
    assert decision.fallback_resume_at.date() == date(2026, 9, 8)
    assert decision.fallback_resume_at.hour == DEFAULT_DAY_HOUR
    assert decision.maximum_attempts == 1


def test_a3_thinking() -> None:
    state = _qualifying()
    facts = TurnFacts(
        intent=BusinessIntent.PURCHASE,
        pause_reason=PauseReason.THINKING.value,
        consent_level=ConsentLevel.CONTEXTUAL.value,
        temporal_commitment="Vou pensar.",
    )
    decision = followup_decision(state, facts, inbound_text="Vou pensar.")
    assert decision.eligible is True
    assert decision.may_ask_return_permission is True
    assert decision.send_now is False
    assert decision.pause_reason == PauseReason.THINKING
    assert decision.schedule_at is None
    assert decision.fallback_resume_at is not None
    assert decision.fallback_resume_at.date() == date(2026, 9, 8)


def test_a4_commercial_silence_eligible() -> None:
    until = datetime(2026, 9, 7, 6, 0, tzinfo=TZ_BRT)
    record = FollowUpRecord(
        last_bot_had_actionable_question=True,
        significant_commercial_exchange=True,
        awaiting_until=until.isoformat(),
    )
    state = _qualifying(
        wait_state=FollowUpWaitState.AWAITING_CUSTOMER,
        followup=record,
        pending_question="cpf",
    )
    decision = followup_decision(state, TurnFacts(), inbound_text="")
    assert decision.eligible is True
    assert decision.send_now is True
    assert decision.authorize_send is True
    assert decision.pause_reason == PauseReason.NO_RESPONSE_AFTER_QUESTION
    assert decision.wait_state == FollowUpWaitState.FOLLOWUP_DUE
    assert decision.maximum_attempts == 1


def test_a5_greeting_not_eligible() -> None:
    state = ConversationCanonicalState(
        thread_id="t-hi",
        customer=CustomerState(phone="5511999999999"),
        intent=BusinessIntent.SMALLTALK,
        wait_state=FollowUpWaitState.ACTIVE_QUALIFICATION.value,
        followup=FollowUpRecord(),
    )
    facts = TurnFacts(intent=BusinessIntent.SMALLTALK)
    decision = followup_decision(state, facts, inbound_text="Oi")
    assert decision.eligible is False
    assert decision.send_now is False
    assert decision.reason_code == "greeting_only"


def test_a6_refusal_not_eligible() -> None:
    state = _qualifying()
    facts = TurnFacts(
        intent=BusinessIntent.PURCHASE_FINANCING,
        consent_level=ConsentLevel.REFUSED.value,
    )
    decision = followup_decision(state, facts, inbound_text="Não precisa me chamar.")
    assert decision.eligible is False
    assert decision.send_now is False
    assert decision.reason_code == "explicit_refusal"
    assert decision.cancel_intent is None


def test_a7_opt_out() -> None:
    state = _qualifying(
        wait_state=FollowUpWaitState.PAUSED_WITH_FOLLOWUP,
        followup=FollowUpRecord(scheduled_at="2026-09-08T14:00:00-03:00"),
    )
    facts = TurnFacts(
        intent=BusinessIntent.SMALLTALK,
        pause_reason=PauseReason.OPT_OUT.value,
        consent_level=ConsentLevel.REFUSED.value,
    )
    decision = followup_decision(
        state, facts, inbound_text="Não quero mais receber mensagens."
    )
    assert decision.eligible is False
    assert decision.send_now is False
    assert decision.authorize_send is False
    assert decision.cancel_intent == FollowUpCancelIntent.OPT_OUT
    assert decision.reason_code == "opt_out"


def test_a8_explicit_time_within_hours() -> None:
    state = _qualifying()
    facts = TurnFacts(
        intent=BusinessIntent.PURCHASE_FINANCING,
        pause_reason=PauseReason.CUSTOMER_WILL_RETURN.value,
        consent_level=ConsentLevel.EXPLICIT_TIME.value,
        temporal_commitment="Depois das 14h pode falar comigo.",
    )
    decision = followup_decision(
        state, facts, inbound_text="Depois das 14h pode falar comigo."
    )
    assert decision.eligible is True
    assert decision.schedule_at is not None
    assert decision.schedule_at.date() == date(2026, 9, 7)
    assert decision.schedule_at.hour == 14
    assert decision.send_now is False
    assert "14h" in (decision.original_temporal_text or "")

    outside = normalize_temporal("Pode me chamar hoje às 22h")
    assert outside.instant is not None
    assert outside.instant.hour != 22
    assert outside.moved_outside_hours is True
    assert outside.original_text and "22h" in outside.original_text
    assert outside.instant.date() >= date(2026, 9, 8)


def test_a9_period_does_not_invent_a_clock() -> None:
    state = _qualifying()
    week = followup_decision(
        state,
        TurnFacts(
            intent=BusinessIntent.PURCHASE,
            pause_reason=PauseReason.CUSTOMER_WILL_RETURN.value,
            consent_level=ConsentLevel.CONTEXTUAL.value,
            temporal_commitment="Me chama semana que vem.",
        ),
        inbound_text="Me chama semana que vem.",
    )
    assert week.eligible is True
    assert week.schedule_at is None
    assert week.temporal_kind == TemporalKind.PERIOD
    assert week.period_label == "next_week"
    assert week.send_now is False

    lunch = followup_decision(
        state,
        TurnFacts(
            intent=BusinessIntent.PURCHASE,
            pause_reason=PauseReason.CUSTOMER_WILL_RETURN.value,
            consent_level=ConsentLevel.CONTEXTUAL.value,
            temporal_commitment="Depois do almoço.",
        ),
        inbound_text="Depois do almoço.",
    )
    assert lunch.eligible is True
    assert lunch.schedule_at is None
    assert lunch.temporal_kind == TemporalKind.PERIOD
    assert lunch.period_label == "after_lunch"
    assert lunch.send_now is False


def test_a10_single_attempt_limit() -> None:
    record = FollowUpRecord(
        pause_reason=PauseReason.DOCUMENTS_PROMISED,
        consent_level=ConsentLevel.EXPLICIT_TIME,
        scheduled_at="2026-09-07T09:00:00-03:00",
        attempt_number=1,
        sent_at="2026-09-07T09:00:00-03:00",
        awaiting_until=datetime(2026, 9, 8, 9, 0, tzinfo=TZ_BRT).isoformat(),
    )
    state = _qualifying(
        wait_state=FollowUpWaitState.AWAITING_AFTER_FOLLOWUP,
        followup=record,
    )
    decision = followup_decision(state, TurnFacts())
    assert decision.send_now is False
    assert decision.authorize_send is False
    assert decision.maximum_attempts == 1
    assert decision.eligible is False
    assert decision.reason_code in {"max_attempts", "unanswered_followup_dormant"}


def test_a11_dormant_after_unanswered_followup() -> None:
    sent = datetime(2026, 9, 6, 10, 0, tzinfo=TZ_BRT)
    record = FollowUpRecord(
        pause_reason=PauseReason.THINKING,
        attempt_number=1,
        sent_at=sent.isoformat(),
        awaiting_until=(sent + AWAITING_AFTER_FOLLOWUP_WINDOW).isoformat(),
    )
    state = _qualifying(
        wait_state=FollowUpWaitState.AWAITING_AFTER_FOLLOWUP,
        followup=record,
    )
    decision = followup_decision(state, TurnFacts())
    assert decision.wait_state == FollowUpWaitState.DORMANT
    assert decision.send_now is False
    assert decision.authorize_send is False
    assert decision.eligible is False
    assert decision.remarketing_eligible is True
    applied = apply_followup_transition(state, decision)
    assert applied.wait_state == FollowUpWaitState.DORMANT.value
    assert applied.followup.remarketing_eligible is True
    assert authorizes_automatic_send(applied.wait_state) is False


def test_a12_remarketing_does_not_send() -> None:
    dormant = _qualifying(
        wait_state=FollowUpWaitState.DORMANT,
        followup=FollowUpRecord(remarketing_eligible=True, attempt_number=1),
    )
    decision = followup_decision(dormant, TurnFacts())
    assert decision.send_now is False
    assert decision.authorize_send is False
    assert decision.remarketing_eligible is True
    assert authorizes_automatic_send(FollowUpWaitState.REMARKETING_ELIGIBLE) is False

    remarketing = _qualifying(
        wait_state=FollowUpWaitState.REMARKETING_ELIGIBLE,
        followup=FollowUpRecord(remarketing_eligible=True),
    )
    again = followup_decision(remarketing, TurnFacts())
    assert again.send_now is False
    assert again.authorize_send is False
    assert again.eligible is False


def test_human_active_cancels() -> None:
    state = _qualifying(
        lifecycle=LifecycleState(status=LifecycleStatus.HUMAN_ACTIVE),
        wait_state=FollowUpWaitState.PAUSED_WITH_FOLLOWUP,
        followup=FollowUpRecord(scheduled_at="2026-09-08T14:00:00-03:00"),
    )
    decision = followup_decision(state, TurnFacts())
    assert decision.eligible is False
    assert decision.send_now is False
    assert decision.cancel_intent == FollowUpCancelIntent.HUMAN_ASSUMED


def test_overdue_outside_hours_returns_next_window() -> None:
    set_clock(SATURDAY_20)
    record = FollowUpRecord(
        pause_reason=PauseReason.DOCUMENTS_PROMISED,
        consent_level=ConsentLevel.EXPLICIT_TIME,
        scheduled_at="2026-09-12T14:00:00-03:00",
        original_temporal_text="sábado às 14h",
    )
    state = _qualifying(
        wait_state=FollowUpWaitState.PAUSED_WITH_FOLLOWUP,
        followup=record,
    )
    decision = followup_decision(state, TurnFacts())
    assert decision.send_now is False
    assert decision.authorize_send is False
    assert decision.next_window is not None
    assert decision.wait_state == FollowUpWaitState.FOLLOWUP_DUE
    assert decision.reason_code == "due_outside_hours"
    assert decision.original_temporal_text == "sábado às 14h"
    assert decision.next_window.weekday() == 0
    assert decision.next_window.hour == 8


def test_handoff_sent_allows_followup_without_second_handoff() -> None:
    state = _qualifying(lifecycle=LifecycleState(status=LifecycleStatus.HANDOFF_SENT))
    facts = TurnFacts(
        intent=BusinessIntent.PURCHASE_FINANCING,
        pause_reason=PauseReason.CUSTOMER_WILL_RETURN.value,
        consent_level=ConsentLevel.EXPLICIT_TIME.value,
        temporal_commitment="Pode me chamar amanhã.",
    )
    decision = followup_decision(state, facts, inbound_text="Pode me chamar amanhã.")
    assert decision.eligible is True
    assert decision.forbid_handoff_repeat is True
    assert decision.send_now is False


def test_merge_does_not_clear_wait_state_on_omission() -> None:
    prev = _qualifying(
        wait_state=FollowUpWaitState.PAUSED_WITH_FOLLOWUP,
        followup=FollowUpRecord(
            pause_reason=PauseReason.THINKING,
            consent_level=ConsentLevel.CONTEXTUAL,
            original_temporal_text="vou pensar",
        ),
    )
    merged = deterministic_merge(
        prev,
        TurnFacts(intent=BusinessIntent.PURCHASE, facts={"budget": 50000}),
    )
    assert merged.wait_state == FollowUpWaitState.PAUSED_WITH_FOLLOWUP.value
    assert merged.followup.pause_reason == PauseReason.THINKING
    assert merged.followup.consent_level == ConsentLevel.CONTEXTUAL
    assert merged.followup.original_temporal_text == "vou pensar"
    assert merged.facts["desired_model"] == "Strada"


def test_silence_window_matches_config() -> None:
    state = _qualifying()
    mark_awaiting_customer(state)
    assert state.wait_state == FollowUpWaitState.AWAITING_CUSTOMER.value
    until = datetime.fromisoformat(state.followup.awaiting_until)
    expected = datetime(2026, 9, 7, 10, 0, tzinfo=TZ_BRT) + COMMERCIAL_SILENCE_WINDOW
    assert until == expected


def test_amanha_uses_commercial_clock() -> None:
    normalized = normalize_temporal("amanhã")
    assert normalized.instant is not None
    assert normalized.instant.date() == date(2026, 9, 8)
    assert normalized.instant.hour == DEFAULT_DAY_HOUR
    assert normalized.kind == TemporalKind.INSTANT
