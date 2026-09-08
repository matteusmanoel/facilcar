"""Phase 3 — quote → presented vehicle → explicit primary; no inventory re-search."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from sdr.application.process_turn import process_turn
from sdr.domain.inbound import ContentType, InboundTurn, MediaStatus, QuotedContext
from sdr.domain.inventory_search import (
    InventorySearchRequest,
    inventory_search_key_from_request,
)
from sdr.domain.types import (
    Action,
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    TurnFacts,
)
from sdr.domain.vehicle_reference import (
    RESOLUTION_AMBIGUOUS,
    RESOLUTION_EXPLICIT_REPLY,
    RESOLUTION_LISTING,
    RESOLUTION_NONE,
    RESOLUTION_UNIQUE_CONTEXT,
    PresentedVehicleBinding,
    apply_primary_vehicle_choice,
    bindings_for_offer_set,
    next_primary_vehicle_id,
    resolve_vehicle_reference,
    select_explicit_primary_id,
)
from sdr.replay import run_replay


STRADA_2021 = "veh-strada-2021"
STRADA_2017 = "veh-strada-2017"
STRADA_2018 = "veh-strada-2018"
CONV = "syn-conv-stradas"


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
            media_url="https://cdn.example/strada-2021.jpg",
        ),
        PresentedVehicleBinding(
            conversation_id=CONV,
            provider_message_id="prov-cap-2021",
            vehicle_id=STRADA_2021,
            presentation_type="CAPTION",
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
            media_url="https://cdn.example/strada-2018.jpg",
        ),
    ]


def _shown_state(**overrides) -> ConversationCanonicalState:
    extra_facts = overrides.pop("facts", {})
    facts = {
        "desired_model": "Strada",
        "desired_vehicle_text": "Strada",
        **extra_facts,
    }
    shown = [STRADA_2021, STRADA_2017, STRADA_2018]
    req = InventorySearchRequest(original_model="Strada", original_vehicle_text="Strada")
    key = inventory_search_key_from_request(req, last_shown_vehicle_ids=shown)
    state = ConversationCanonicalState(
        thread_id=CONV,
        customer=CustomerState(phone="5511900000001", name="Mateus"),
        intent=BusinessIntent.PURCHASE,
        language="pt-BR",
        facts=facts,
        last_inventory_search_key=key,
        last_shown_vehicle_ids=shown,
        presented_vehicle_bindings=_bindings(),
        assistant_turn_count=2,
    )
    for key_name, value in overrides.items():
        setattr(state, key_name, value)
    return state


def test_a_reply_on_third_offer_selects_that_vehicle() -> None:
    resolved = resolve_vehicle_reference(
        conversation_id=CONV,
        quoted=[QuotedContext(stanza_id="prov-img-2018")],
        bindings=_bindings(),
        last_shown_vehicle_ids=[STRADA_2021, STRADA_2017, STRADA_2018],
        inbound_text="Gostei dessa opção. Financia 100%?",
    )
    assert resolved.vehicle_id == STRADA_2018
    assert resolved.reason == RESOLUTION_EXPLICIT_REPLY
    state = _shown_state()
    apply_primary_vehicle_choice(state, resolved)
    assert state.primary_vehicle_id == STRADA_2018
    assert STRADA_2021 in state.last_shown_vehicle_ids
    assert STRADA_2017 in state.last_shown_vehicle_ids
    assert (
        select_explicit_primary_id(
            [
                {"vehicleId": STRADA_2021, "isPrimary": False},
                {"vehicleId": STRADA_2017, "isPrimary": False},
                {"vehicleId": STRADA_2018, "isPrimary": True},
            ]
        )
        == STRADA_2018
    )


@pytest.mark.parametrize(
    "stanza, expected",
    [
        ("prov-img-2021", STRADA_2021),
        ("prov-img-2017", STRADA_2017),
        ("prov-img-2018", STRADA_2018),
    ],
)
def test_b_reply_is_not_position_based(stanza: str, expected: str) -> None:
    resolved = resolve_vehicle_reference(
        conversation_id=CONV,
        quoted=[QuotedContext(stanza_id=stanza)],
        bindings=_bindings(),
        last_shown_vehicle_ids=[STRADA_2021, STRADA_2017, STRADA_2018],
        inbound_text="Gostei dessa",
    )
    assert resolved.vehicle_id == expected


def test_c_any_citable_message_of_same_vehicle_resolves() -> None:
    for stanza in ("prov-img-2021", "prov-cap-2021"):
        resolved = resolve_vehicle_reference(
            conversation_id=CONV,
            quoted=[QuotedContext(stanza_id=stanza)],
            bindings=_bindings(),
            last_shown_vehicle_ids=[STRADA_2021, STRADA_2017, STRADA_2018],
            inbound_text="essa",
        )
        assert resolved.vehicle_id == STRADA_2021


def test_d_cross_conversation_quote_is_ignored() -> None:
    resolved = resolve_vehicle_reference(
        conversation_id="other-conv",
        quoted=[QuotedContext(stanza_id="prov-img-2018")],
        bindings=_bindings(),
        last_shown_vehicle_ids=[STRADA_2021, STRADA_2017, STRADA_2018],
        inbound_text="Gostei dessa opção",
    )
    assert resolved.vehicle_id is None
    assert resolved.reason in {RESOLUTION_NONE, RESOLUTION_AMBIGUOUS}


def test_e_unknown_quote_does_not_pick_first() -> None:
    resolved = resolve_vehicle_reference(
        conversation_id=CONV,
        quoted=[QuotedContext(stanza_id="prov-unknown")],
        bindings=_bindings(),
        last_shown_vehicle_ids=[STRADA_2021, STRADA_2017, STRADA_2018],
        inbound_text="Gostei dessa",
    )
    assert resolved.vehicle_id is None


def test_f_no_quote_with_multiple_options_is_ambiguous() -> None:
    resolved = resolve_vehicle_reference(
        conversation_id=CONV,
        quoted=[],
        bindings=_bindings(),
        last_shown_vehicle_ids=[STRADA_2021, STRADA_2017, STRADA_2018],
        inbound_text="Gostei dessa opção",
    )
    assert resolved.reason == RESOLUTION_AMBIGUOUS
    assert resolved.vehicle_id is None


def test_g_singular_reference_with_one_shown_vehicle() -> None:
    only = [
        PresentedVehicleBinding(
            conversation_id=CONV,
            provider_message_id="prov-only",
            vehicle_id=STRADA_2018,
            presentation_type="IMAGE",
            position=0,
            offer_set_id="offer-one",
        )
    ]
    resolved = resolve_vehicle_reference(
        conversation_id=CONV,
        quoted=[],
        bindings=only,
        last_shown_vehicle_ids=[STRADA_2018],
        inbound_text="Gostei dessa opção",
    )
    assert resolved.vehicle_id == STRADA_2018
    assert resolved.reason == RESOLUTION_UNIQUE_CONTEXT


def test_h_reprocessing_same_reply_is_idempotent() -> None:
    state = _shown_state()
    resolved = resolve_vehicle_reference(
        conversation_id=CONV,
        quoted=[QuotedContext(stanza_id="prov-img-2018")],
        bindings=_bindings(),
        last_shown_vehicle_ids=state.last_shown_vehicle_ids,
        inbound_text="Gostei",
        inbound_timestamp=100.0,
    )
    apply_primary_vehicle_choice(state, resolved)
    first_at = state.primary_vehicle_chosen_at
    apply_primary_vehicle_choice(state, resolved)
    assert state.primary_vehicle_id == STRADA_2018
    assert state.primary_vehicle_chosen_at == first_at


def test_i_later_choice_replaces_primary_and_keeps_history() -> None:
    state = _shown_state()
    first = resolve_vehicle_reference(
        conversation_id=CONV,
        quoted=[QuotedContext(stanza_id="prov-img-2021")],
        bindings=_bindings(),
        last_shown_vehicle_ids=state.last_shown_vehicle_ids,
        inbound_text="essa",
        inbound_timestamp=10.0,
    )
    apply_primary_vehicle_choice(state, first)
    second = resolve_vehicle_reference(
        conversation_id=CONV,
        quoted=[QuotedContext(stanza_id="prov-img-2018")],
        bindings=_bindings(),
        last_shown_vehicle_ids=state.last_shown_vehicle_ids,
        inbound_text="na verdade essa",
        inbound_timestamp=20.0,
    )
    apply_primary_vehicle_choice(state, second)
    assert state.primary_vehicle_id == STRADA_2018
    stale = resolve_vehicle_reference(
        conversation_id=CONV,
        quoted=[QuotedContext(stanza_id="prov-img-2017")],
        bindings=_bindings(),
        last_shown_vehicle_ids=state.last_shown_vehicle_ids,
        inbound_text="essa",
        inbound_timestamp=5.0,
    )
    apply_primary_vehicle_choice(state, stale)
    assert state.primary_vehicle_id == STRADA_2018
    assert set(state.last_shown_vehicle_ids) == {STRADA_2021, STRADA_2017, STRADA_2018}


def test_o_quoted_url_is_not_author_text() -> None:
    inbound = InboundTurn(
        thread_id=CONV,
        content_type=ContentType.TEXT,
        text="Gostei dessa opção. Financia 100%?",
        media_status=MediaStatus.NONE,
        quoted=[
            QuotedContext(
                stanza_id="prov-img-2018",
                quoted_text="https://cdn.example/strada-2018.jpg Strada 2018",
            )
        ],
    )
    assert "https://cdn.example" not in (inbound.effective_text or "")


def test_p_listing_id_resolves_deterministically() -> None:
    resolved = resolve_vehicle_reference(
        conversation_id=CONV,
        quoted=[],
        bindings=_bindings(),
        last_shown_vehicle_ids=[STRADA_2021, STRADA_2017, STRADA_2018],
        inbound_text="Esse veículo ainda está disponível?",
        listing_id=STRADA_2018,
    )
    assert resolved.vehicle_id == STRADA_2018
    assert resolved.reason == RESOLUTION_LISTING


def test_p_exact_media_url_resolves() -> None:
    resolved = resolve_vehicle_reference(
        conversation_id=CONV,
        quoted=[],
        bindings=_bindings(),
        last_shown_vehicle_ids=[STRADA_2021, STRADA_2017, STRADA_2018],
        inbound_text="Esse ainda está disponível?",
        inbound_media_url="https://cdn.example/strada-2018.jpg",
    )
    assert resolved.vehicle_id == STRADA_2018
    assert resolved.reason == RESOLUTION_LISTING


def test_q_ambiguous_image_does_not_invent_vehicle_id() -> None:
    resolved = resolve_vehicle_reference(
        conversation_id=CONV,
        quoted=[],
        bindings=_bindings(),
        last_shown_vehicle_ids=[STRADA_2021, STRADA_2017, STRADA_2018],
        inbound_text="Esse veículo ainda está disponível?",
        inbound_media_url="https://cdn.example/random-customer-photo.jpg",
    )
    assert resolved.vehicle_id is None
    assert resolved.reason in {RESOLUTION_AMBIGUOUS, RESOLUTION_NONE}


def test_bindings_same_offer_set_keep_all_positions() -> None:
    grouped = bindings_for_offer_set(_bindings(), "offer-set-strada-1")
    assert {b.vehicle_id for b in grouped} == {STRADA_2021, STRADA_2017, STRADA_2018}


def test_m_api_primary_is_explicit_never_first_fallback() -> None:
    assert (
        select_explicit_primary_id(
            [
                {"vehicleId": STRADA_2021, "isPrimary": False},
                {"vehicleId": STRADA_2018, "isPrimary": True},
                {"vehicleId": STRADA_2017, "isPrimary": False},
            ]
        )
        == STRADA_2018
    )
    assert (
        select_explicit_primary_id(
            [
                {"vehicleId": STRADA_2021, "isPrimary": False},
                {"vehicleId": STRADA_2017, "isPrimary": False},
            ]
        )
        is None
    )


def test_m_saving_interests_preserves_primary() -> None:
    assert (
        next_primary_vehicle_id(
            selected_ids=[STRADA_2017, STRADA_2018, STRADA_2021],
            current_primary_id=STRADA_2018,
        )
        == STRADA_2018
    )
    assert (
        next_primary_vehicle_id(
            selected_ids=[STRADA_2017, STRADA_2021],
            current_primary_id=STRADA_2018,
        )
        is None
    )


@pytest.mark.asyncio
async def test_a_process_turn_reply_third_does_not_research() -> None:
    state = _shown_state()

    async def understand(text, _state):
        return TurnFacts(
            intent=BusinessIntent.PURCHASE_FINANCING,
            facts={"payment_method": "financing", "down_payment": 0},
        )

    inbound = InboundTurn(
        thread_id=CONV,
        content_type=ContentType.TEXT,
        text="Gostei dessa opção. Financia 100%?",
        quoted=[QuotedContext(stanza_id="prov-img-2018")],
    )
    result = await process_turn(state=state, inbound=inbound, understand=understand)
    assert result.action_plan.action != Action.SHOW_OFFERS
    assert result.state.primary_vehicle_id == STRADA_2018
    assert result.state.last_shown_vehicle_ids == [STRADA_2021, STRADA_2017, STRADA_2018]


@pytest.mark.asyncio
async def test_n_run_replay_accepts_with_db_without_connecting() -> None:
    fake_pool = SimpleNamespace(closed=False)

    async def _fake_process_turn(**kwargs):
        assert kwargs.get("pool") is fake_pool
        from sdr.application.process_turn import ProcessTurnResult
        from sdr.domain.types import ActionPlan

        return ProcessTurnResult(
            action_plan=ActionPlan(action=Action.NO_REPLY, reason_code="stub"),
            state=kwargs["state"],
            outbound_texts=[],
            turn_facts=TurnFacts(),
            tool_results=[],
        )

    import importlib

    mod = importlib.import_module("sdr.application.process_turn")
    saved = mod.process_turn
    mod.process_turn = _fake_process_turn
    try:
        ok = await run_replay(
            "corolla_engine_displacement",
            mode="deterministic",
            with_db=True,
            pool=fake_pool,
        )
    finally:
        mod.process_turn = saved
    assert isinstance(ok, bool)


@pytest.mark.asyncio
async def test_j_admiring_comment_does_not_research() -> None:
    state = _shown_state()

    async def understand(text, _state):
        return TurnFacts(intent=BusinessIntent.PURCHASE, facts={})

    result = await process_turn(
        state=state, inbound_text="Lindo esse branco", understand=understand
    )
    assert result.action_plan.action != Action.SHOW_OFFERS


@pytest.mark.asyncio
async def test_k_color_answer_does_not_research() -> None:
    state = _shown_state(pending_question="desired_color")

    async def understand(text, _state):
        return TurnFacts(intent=BusinessIntent.PURCHASE, facts={"desired_color": "preto"})

    result = await process_turn(
        state=state, inbound_text="Pode ser preto", understand=understand
    )
    assert result.action_plan.action != Action.SHOW_OFFERS


@pytest.mark.asyncio
async def test_l_real_criteria_change_does_research() -> None:
    state = _shown_state()

    async def understand(text, _state):
        return TurnFacts(
            intent=BusinessIntent.PURCHASE,
            facts={"desired_model": "Civic", "desired_vehicle_text": "Civic"},
        )

    result = await process_turn(
        state=state, inbound_text="Na verdade quero um Civic", understand=understand
    )
    assert result.action_plan.action == Action.SHOW_OFFERS
