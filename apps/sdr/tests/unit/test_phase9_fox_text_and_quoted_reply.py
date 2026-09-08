"""Phase 9R Frente A — textual Fox survives vision failure; quoted reply is aligned."""

from __future__ import annotations

import pytest

from sdr.application.process_turn import process_turn
from sdr.domain.decision import decide
from sdr.domain.dialogue_alignment import evaluate_dialogue_alignment
from sdr.domain.inbound import ContentType, InboundTurn, MediaStatus
from sdr.domain.types import (
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    TurnFacts,
)
from sdr.domain.visual_resolution import (
    VisualResolutionSource,
    VisualVehicleResolution,
    apply_visual_resolution,
    visual_search_override,
)


def _state(**kwargs) -> ConversationCanonicalState:
    facts = kwargs.pop("facts", {})
    state = ConversationCanonicalState(
        thread_id=kwargs.pop("thread_id", "t-phase9r-a"),
        customer=kwargs.pop(
            "customer",
            CustomerState(phone="5511988001100", name="Carla Mendes"),
        ),
        intent=kwargs.pop("intent", BusinessIntent.PURCHASE),
        language="pt-BR",
        facts=facts,
    )
    for key, value in kwargs.items():
        setattr(state, key, value)
    return state


def test_a2_visual_resolver_error_does_not_wipe_textual_fox() -> None:
    state = _state(facts={"desired_model": "Fox", "desired_vehicle_text": "Fox"})
    vis = VisualVehicleResolution(
        resolution_source=VisualResolutionSource.UNRESOLVED,
        fallback_reason="lookup_failed",
        vision_attempted=True,
        observed_attributes={"is_vehicle": True, "confidence": 0.1},
    )
    apply_visual_resolution(state, vis, inbound_text="Esse Fox ainda tem?")
    assert state.facts.get("desired_model") == "Fox"
    assert state.facts.get("desired_vehicle_text") == "Fox"

    failed_vehicle = VisualVehicleResolution(
        resolution_source=VisualResolutionSource.UNRESOLVED,
        fallback_reason="no_vehicle_in_image",
        vision_attempted=True,
        observed_attributes={"is_vehicle": False},
    )
    apply_visual_resolution(state, failed_vehicle, inbound_text="Esse Fox ainda tem?")
    assert state.facts.get("desired_model") == "Fox"


def test_a3_known_fox_is_not_reasked_when_vision_fails() -> None:
    state = _state(
        facts={"desired_model": "Fox", "desired_vehicle_text": "Fox"},
        last_visual_resolution={
            "resolution_source": "unresolved",
            "fallback_reason": "lookup_failed",
            "vision_attempted": True,
            "matched_vehicle_id": None,
        },
        visual_applied_this_turn=True,
        assistant_turn_count=1,
    )
    override = visual_search_override(state)
    if override is not None:
        _block, ask, _reason = override
        assert ask != "desired_model"
    plan = decide(state)
    assert plan.ask_field != "desired_model"


@pytest.mark.asyncio
async def test_a3_process_turn_does_not_ask_model_for_fox_caption() -> None:
    async def understand(_text, _state):
        return TurnFacts(
            intent=BusinessIntent.PURCHASE,
            language="pt-BR",
            facts={"desired_model": "Fox", "desired_vehicle_text": "Fox"},
        )

    inbound = InboundTurn(
        thread_id="t-phase9r-a",
        content_type=ContentType.IMAGE,
        text="Esse Fox ainda tem?",
        media_status=MediaStatus.OK,
        raw_message_ref={
            "has_media": True,
            "visual_resolution": {
                "resolution_source": "unresolved",
                "fallback_reason": "lookup_failed",
                "vision_attempted": True,
                "matched_vehicle_id": None,
                "observed_attributes": {"is_vehicle": True, "confidence": 0.2},
            },
        },
    )
    result = await process_turn(
        state=_state(assistant_turn_count=1),
        inbound=inbound,
        inbound_text="Esse Fox ainda tem?",
        understand=understand,
        pool=object(),
        image_bytes=b"\x89PNG\r\n\x1a\n" + b"\x00" * 32,
    )
    assert result.state.facts.get("desired_model") == "Fox"
    assert result.action_plan.ask_field != "desired_model"


def test_a10_quoted_vehicle_selection_is_not_payment_misalignment() -> None:
    tagged = evaluate_dialogue_alignment(
        expected_question_field="payment_method",
        detected_question_field="payment_method",
        inbound="Gostei dessa opção",
        turn_def={
            "quoted_message_id": "replay-img-VH-STRADA-2018",
            "response_mode": "quoted_selection",
        },
    )
    assert tagged["dialogue_alignment"] is True

    untagged = evaluate_dialogue_alignment(
        expected_question_field="payment_method",
        detected_question_field="payment_method",
        inbound="Gostei dessa opção",
        turn_def={"quoted_message_id": "replay-img-VH-STRADA-2018"},
    )
    assert untagged["dialogue_alignment"] is True
