"""Unit tests for canonical InboundTurn contract."""

from __future__ import annotations

import pytest

from sdr.domain.inbound import (
    ContentType,
    InboundTurn,
    MediaFailureCode,
    MediaStatus,
    inbound_from_text_compat,
    make_audio_inbound,
    make_media_failed_inbound,
    make_text_inbound,
)


# ---------------------------------------------------------------------------
# Text InboundTurn
# ---------------------------------------------------------------------------

def test_make_text_inbound_basic() -> None:
    inbound = make_text_inbound("t1", "Olá, preciso de um carro")
    assert inbound.content_type == ContentType.TEXT
    assert inbound.text == "Olá, preciso de um carro"
    assert inbound.media_status == MediaStatus.NONE
    assert inbound.failure_code is None
    assert not inbound.is_media_failed
    assert inbound.effective_text == "Olá, preciso de um carro"


def test_make_text_inbound_empty() -> None:
    inbound = make_text_inbound("t1", "")
    assert inbound.text == ""
    assert inbound.effective_text == ""
    assert not inbound.is_media_failed


# ---------------------------------------------------------------------------
# Audio InboundTurn
# ---------------------------------------------------------------------------

def test_make_audio_inbound_with_transcription() -> None:
    inbound = make_audio_inbound("t1", "Quero comprar um Civic")
    assert inbound.content_type == ContentType.AUDIO
    assert inbound.text == "Quero comprar um Civic"
    assert inbound.media_status == MediaStatus.OK
    assert inbound.failure_code is None
    assert not inbound.is_media_failed
    assert inbound.effective_text == "Quero comprar um Civic"


# ---------------------------------------------------------------------------
# Media failure InboundTurn
# ---------------------------------------------------------------------------

def test_make_media_failed_inbound_download_failed() -> None:
    inbound = make_media_failed_inbound("t1", MediaFailureCode.DOWNLOAD_FAILED)
    assert inbound.content_type == ContentType.AUDIO
    assert inbound.text is None
    assert inbound.media_status == MediaStatus.FAILED
    assert inbound.failure_code == MediaFailureCode.DOWNLOAD_FAILED
    assert inbound.is_media_failed
    assert inbound.effective_text == ""


def test_make_media_failed_inbound_transcription_failed() -> None:
    inbound = make_media_failed_inbound("t1", MediaFailureCode.TRANSCRIPTION_FAILED)
    assert inbound.is_media_failed
    assert inbound.failure_code == MediaFailureCode.TRANSCRIPTION_FAILED


def test_media_failed_text_is_none_not_sentinel() -> None:
    """Media failure must NOT produce '__MEDIA_FAILED__' or any text sentinel."""
    inbound = make_media_failed_inbound("t1", MediaFailureCode.DOWNLOAD_FAILED)
    assert inbound.text is None, (
        "Media failure must set text=None, not '__MEDIA_FAILED__' or any other text sentinel."
    )
    # effective_text is "" (empty) for safe downstream handling, not a magic string.
    assert inbound.effective_text == ""
    assert "__MEDIA_FAILED__" not in (inbound.effective_text or "")


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------

def test_inbound_from_text_compat_non_empty() -> None:
    inbound = inbound_from_text_compat("Oi, tudo bem?")
    assert inbound.text == "Oi, tudo bem?"
    assert inbound.content_type == ContentType.TEXT
    assert inbound.media_status == MediaStatus.NONE
    assert not inbound.is_media_failed


def test_inbound_from_text_compat_empty() -> None:
    inbound = inbound_from_text_compat("")
    assert inbound.text is None
    assert inbound.media_status == MediaStatus.NONE
    assert not inbound.is_media_failed


# ---------------------------------------------------------------------------
# Media failure path in process_turn
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_turn_media_failed_does_not_produce_greeting() -> None:
    """A media failure must produce a recovery message, not a greeting."""
    from sdr.application.process_turn import process_turn
    from sdr.domain.types import BusinessIntent, ConversationCanonicalState, CustomerState

    state = ConversationCanonicalState(
        thread_id="t1",
        customer=CustomerState(phone="5511999999999"),
    )
    inbound = make_media_failed_inbound("t1", MediaFailureCode.TRANSCRIPTION_FAILED)

    async def understand(text, s):
        raise AssertionError("understand must not be called for media-failed inbound")

    result = await process_turn(
        state=state,
        inbound=inbound,
        understand=understand,
    )
    assert result.action_plan.action.value == "media_failed"
    assert result.outbound_texts, "Must produce a recovery response for media failure"
    text_lower = " ".join(result.outbound_texts).lower()
    assert "text" not in text_lower.split()
    assert "áudio" in text_lower or "audio" in text_lower
    greeting_phrases = ["sou a júlia", "soy júlia", "como posso ajudar você hoje"]
    for phrase in greeting_phrases:
        assert phrase not in text_lower, (
            f"Media failure response must not contain greeting phrase {phrase!r}. "
            f"Got: {result.outbound_texts}"
        )


@pytest.mark.asyncio
async def test_process_turn_unknown_intent_does_not_produce_generic_greeting_restart() -> None:
    """UNKNOWN intent on a non-first turn must not produce 'Como posso ajudar você hoje?'.

    Validates the decision engine contract: UNKNOWN → COMMERCIAL_UNKNOWN (not SMALLTALK).
    Uses the template composer path to avoid live API calls.
    """
    from unittest.mock import MagicMock

    from sdr.application.process_turn import process_turn
    from sdr.domain.types import BusinessIntent, ConversationCanonicalState, CustomerState, TurnFacts
    from sdr.understanding import response_composer as rc

    state = ConversationCanonicalState(
        thread_id="t1",
        customer=CustomerState(phone="5511999999999"),
        assistant_turn_count=1,  # Not the first turn
    )

    async def understand(text, s):
        return TurnFacts(intent=BusinessIntent.UNKNOWN)

    # Use template path — we are testing decision + template compose contract.
    original_compose = rc.compose_response

    async def _template_only_compose(s, p, tool_context=None, *, client=None):
        # Force template path regardless of whether an API key is configured.
        from sdr.understanding.response_composer import _template_compose, validate_bubbles
        return validate_bubbles(_template_compose(s, p, tool_context))

    rc.compose_response = _template_only_compose
    try:
        result = await process_turn(
            state=state,
            inbound_text="Vocês têm algum scooter elétrico?",
            understand=understand,
        )
    finally:
        rc.compose_response = original_compose

    assert result.action_plan.action.value == "commercial_unknown"
    text_lower = " ".join(result.outbound_texts).lower()
    # Must not produce generic greeting or restart phrasing.
    restart_phrases = [
        "como posso ajudar você hoje",
        "sou a júlia da facilcar",
    ]
    for phrase in restart_phrases:
        assert phrase not in text_lower, (
            f"UNKNOWN intent on non-first turn must not produce restart phrase {phrase!r}. "
            f"Got: {result.outbound_texts}"
        )
    # Must produce a clarifying question (commercial_unknown template).
    assert result.outbound_texts, "Must produce a clarification response"
    assert "procurando" in text_lower or "posso ajudar" in text_lower, (
        f"COMMERCIAL_UNKNOWN response must be a clarifying question. Got: {result.outbound_texts}"
    )


@pytest.mark.asyncio
async def test_process_turn_injects_crm_linked_vehicles_as_known_facts() -> None:
    from sdr.application.process_turn import process_turn
    from sdr.domain.types import (
        BusinessIntent,
        ConversationCanonicalState,
        CustomerState,
        TurnFacts,
    )

    state = ConversationCanonicalState(
        thread_id="t1",
        customer=CustomerState(phone="5511999999999"),
        assistant_turn_count=1,
    )
    captured: dict[str, object] = {}

    async def understand(text, current):
        captured["crm"] = current.facts.get("crm_linked_vehicles")
        return TurnFacts(intent=BusinessIntent.SMALLTALK)

    result = await process_turn(
        state=state,
        inbound_text="ainda quero aquele",
        understand=understand,
        linked_vehicle_titles=["Honda Civic 2020", " ", "Toyota Corolla"],
    )
    assert captured["crm"] == "Honda Civic 2020, Toyota Corolla"
    assert result.state.facts.get("crm_linked_vehicles") == "Honda Civic 2020, Toyota Corolla"


@pytest.mark.asyncio
async def test_process_turn_media_failed_production_is_silent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Production must not send a customer-facing media failure message."""
    from sdr.application.process_turn import process_turn
    from sdr.config import get_settings
    from sdr.domain.types import ConversationCanonicalState, CustomerState

    monkeypatch.setenv("SDR_ENVIRONMENT", "production")
    get_settings.cache_clear()
    try:
        state = ConversationCanonicalState(
            thread_id="t1",
            customer=CustomerState(phone="5511999999999"),
        )
        inbound = make_media_failed_inbound(
            "t1",
            MediaFailureCode.EXTRACTION_FAILED,
            content_type=ContentType.DOCUMENT,
        )

        async def understand(text, s):
            raise AssertionError("understand must not be called for media-failed inbound")

        result = await process_turn(state=state, inbound=inbound, understand=understand)
        assert result.action_plan.action.value == "no_reply"
        assert result.outbound_texts == []
    finally:
        get_settings.cache_clear()
