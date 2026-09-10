"""Document commitment polarity — unavailability is not a promise."""

from __future__ import annotations

import json

import pytest

from sdr.domain.document_commitment import (
    COMMITMENT_CLAIM_PROMISED,
    COMMITMENT_CLAIM_UNAVAILABLE,
    COMMITMENT_CLAIM_WEAK,
    commitment_claim_for_inbound,
    inbound_has_firm_document_send_promise,
    outbound_has_unsupported_commitment,
)
from sdr.domain.followup import PauseReason, enrich_turn_facts_from_inbound, followup_decision, suggest_pause_from_inbound
from sdr.domain.followup_plan import FollowUpAction, FollowUpPlan, FollowUpReason, fallback_followup_bubbles
from sdr.domain.followup_validator import validate_followup
from sdr.domain.types import BusinessIntent, ConversationCanonicalState, TurnFacts
from sdr.understanding.followup_composer import compose_followup


def _qualifying() -> ConversationCanonicalState:
    return ConversationCanonicalState(
        thread_id="doc-commitment",
        intent=BusinessIntent.PURCHASE_FINANCING,
        assistant_turn_count=3,
    )


def _plan(*, authorized: bool) -> FollowUpPlan:
    claim = COMMITMENT_CLAIM_PROMISED if authorized else COMMITMENT_CLAIM_UNAVAILABLE
    return FollowUpPlan(
        reason=FollowUpReason.DOCUMENTS_PENDING.value,
        requested_action=FollowUpAction.ASK_DOCUMENTS_STATUS.value,
        pending_commitment="callback_14h" if not authorized else "send_proofs_tomorrow",
        authorized_commitment=authorized,
        commitment_claim=claim,
        authorized_facts={
            "pending_commitment": "callback_14h",
            "authorized_commitment": authorized,
            "commitment_claim": claim,
        },
    )


def test_unavailability_is_not_a_promise() -> None:
    inbound = "Não estou com os comprovantes agora."
    assert commitment_claim_for_inbound(inbound) == COMMITMENT_CLAIM_UNAVAILABLE
    assert inbound_has_firm_document_send_promise(inbound) is False
    reason, _consent, _commitment = suggest_pause_from_inbound(inbound)
    assert reason is None


def test_callback_request_is_not_a_document_promise() -> None:
    inbound = "Não estou com os comprovantes agora. Pode me chamar amanhã às 14h."
    reason, _consent, _commitment = suggest_pause_from_inbound(inbound)
    assert reason == PauseReason.DOCUMENTS_UNAVAILABLE
    facts = TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING)
    enrich_turn_facts_from_inbound(facts, inbound)
    assert facts.pause_reason == PauseReason.DOCUMENTS_UNAVAILABLE.value
    decision = followup_decision(_qualifying(), facts, inbound_text=inbound)
    assert decision.eligible is True
    assert decision.pause_reason == PauseReason.DOCUMENTS_UNAVAILABLE
    assert decision.schedule_at is not None
    assert decision.schedule_at.hour == 14


def test_explicit_promise_may_be_mentioned() -> None:
    inbound = "Mando os comprovantes amanhã. Pode me chamar."
    assert inbound_has_firm_document_send_promise(inbound) is True
    assert commitment_claim_for_inbound(inbound) == COMMITMENT_CLAIM_PROMISED
    reason, _consent, _commitment = suggest_pause_from_inbound(inbound)
    assert reason == PauseReason.DOCUMENTS_PROMISED
    bubbles = fallback_followup_bubbles(_plan(authorized=True))
    joined = " ".join(bubbles).lower()
    assert "comprovante" in joined
    validation = validate_followup(bubbles, _plan(authorized=True))
    assert validation.sendable
    assert "unsupported_commitment" not in validation.violations


def test_vou_tentar_is_not_a_firm_commitment() -> None:
    inbound = "Vou tentar enviar os comprovantes. Pode me chamar amanhã."
    assert inbound_has_firm_document_send_promise(inbound) is False
    assert commitment_claim_for_inbound(inbound) == COMMITMENT_CLAIM_WEAK
    reason, _consent, _commitment = suggest_pause_from_inbound(inbound)
    assert reason == PauseReason.DOCUMENTS_UNAVAILABLE


def test_fallback_respects_unavailable_polarity() -> None:
    bubbles = fallback_followup_bubbles(_plan(authorized=False))
    joined = " ".join(bubbles).lower()
    assert "separar" in joined or "verificar" in joined
    assert "ia enviar" not in joined
    assert "prometeu" not in joined
    assert outbound_has_unsupported_commitment(joined) is False
    validation = validate_followup(bubbles, _plan(authorized=False))
    assert validation.sendable


def test_invalid_composer_unsupported_commitment_rejected() -> None:
    validation = validate_followup(
        ["Conseguiu reunir os comprovantes que você ia enviar?"],
        _plan(authorized=False),
    )
    assert not validation.sendable
    assert "unsupported_commitment" in validation.violations
    assert validation.bubbles == []


@pytest.mark.asyncio
async def test_invalid_llm_copy_falls_back_without_invented_promise() -> None:
    class _LyingClient:
        def __init__(self) -> None:
            self.chat = self
            self.completions = self

        async def create(self, **_kwargs: object) -> object:
            class _Msg:
                content = json.dumps(
                    {"bubbles": ["Conseguiu reunir os comprovantes que ia enviar?"]}
                )

            class _Choice:
                message = _Msg()

            class _Resp:
                choices = [_Choice()]

            return _Resp()

    result = await compose_followup(_plan(authorized=False), client=_LyingClient())
    joined = " ".join(result.bubbles).lower()
    assert "ia enviar" not in joined
    assert "prometeu" not in joined
    if result.sendable:
        assert result.used_fallback
        assert len(result.bubbles) == 1
        assert "unsupported_commitment" not in result.violations


def test_followup_keeps_one_primary_action() -> None:
    validation = validate_followup(
        [
            "Conseguiu separar os comprovantes?",
            "Quer agendar visita amanhã?",
        ],
        _plan(authorized=False),
    )
    assert not validation.sendable
    assert "more_than_one_question" in validation.violations


def test_envio_noun_is_not_a_firm_promise() -> None:
    inbound = "Pode me chamar depois sobre o envio dos comprovantes."
    assert inbound_has_firm_document_send_promise(inbound) is False
    reason, _consent, _commitment = suggest_pause_from_inbound(inbound)
    assert reason == PauseReason.DOCUMENTS_UNAVAILABLE


def test_llm_cannot_overclaim_document_promise() -> None:
    inbound = "Não estou com os comprovantes agora. Pode me chamar amanhã às 14h."
    facts = TurnFacts(
        intent=BusinessIntent.PURCHASE_FINANCING,
        pause_reason=PauseReason.DOCUMENTS_PROMISED.value,
    )
    enrich_turn_facts_from_inbound(facts, inbound)
    assert facts.pause_reason == PauseReason.DOCUMENTS_UNAVAILABLE.value
