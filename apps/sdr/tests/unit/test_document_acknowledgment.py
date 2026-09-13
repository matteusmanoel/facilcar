"""Phase 9R Frente C — acknowledge exactly the documents received.

C1–C12 are semantic/state contracts. Exact copy is pinned only for the
deliberate ``Recebi sua CNH`` receipt when that is the deterministic ack.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdr.application.process_turn import process_turn
from sdr.domain.decision import decide, inventory_search_key
from sdr.domain.dialogue_plan import DialogueAct, build_dialogue_plan
from sdr.domain.document_status import merge_document_status
from sdr.domain.document_storage import apply_commercial_document_receipt
from sdr.domain.inbound import ContentType, InboundTurn, MediaStatus
from sdr.domain.inbound_batch import InboundSegment, compose_inbound_turn
from sdr.domain.merge import deterministic_merge
from sdr.domain.qualification_policy import (
    ACT_ASK_REMAINING_DOCUMENTS,
    PRIMARY_ASK_REMAINING_DOCUMENTS,
    PRIMARY_INVITE_VISIT,
    annotate_action_plan,
    remaining_document_components,
    should_ask_remaining_documents,
)
from sdr.domain.qualifications import next_ask_field, refresh_actionability
from sdr.domain.types import (
    Action,
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    TurnFacts,
)
from sdr.replay.inbound import build_replay_inbound
from sdr.understanding.response_composer import _document_received_bubbles, _template_compose

PHASE9 = Path(__file__).resolve().parents[1] / "golden" / "phase9"
STORAGE_LEAKS = ("storage", "bucket", "s3", "salvo no sistema", "salva no sistema")


def _financing_ready(**kwargs) -> ConversationCanonicalState:
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
    base = ConversationCanonicalState(
        thread_id="t-doc-ack",
        customer=CustomerState(phone="5511988002200", name="Bruno Azevedo"),
        intent=BusinessIntent.PURCHASE_FINANCING,
        language="pt-BR",
        facts=facts,
        last_inventory_search_key=inventory_search_key(facts),
        last_shown_vehicle_ids=shown,
        documents_asked=True,
        installment_asked=True,
        assistant_turn_count=4,
        primary_vehicle_id="VH-STRADA-2018",
    )
    for key, value in kwargs.items():
        setattr(base, key, value)
    return refresh_actionability(base)


def _doc_segment(message_id: str, document_type: str, text: str, *, order: int = 0, **extra) -> InboundSegment:
    extracted = {"document_type": document_type, **extra}
    return InboundSegment(
        message_id=message_id,
        content_type=ContentType.DOCUMENT,
        text=text,
        media_status=MediaStatus.OK,
        mime_type="application/pdf",
        document_extracted=extracted,
        order=order,
    )


def _inbound_from_segments(*segments: InboundSegment) -> InboundTurn:
    return compose_inbound_turn(
        thread_id="t-doc-ack",
        segments=list(segments),
        batch_id="batch-doc-ack",
    )


def _ack_bubbles(*, received: dict[str, str], kind: str = "CNH", primary: str | None = None) -> list[str]:
    remaining = [
        name
        for name, status in {
            "cnh": "missing",
            "proof_of_income": "missing",
            "proof_of_residence": "missing",
            **received,
        }.items()
        if status not in {"received", "deferred"}
    ]
    return _document_received_bubbles(
        {
            "language": "pt-BR",
            "document_kind": kind,
            "customer_name": "Bruno Azevedo",
            "facts": {"document_status": received, "name": "Bruno Azevedo"},
            "dialogue_plan": {
                "primary_action": primary
                or ("ask_remaining_documents" if remaining else "invite_visit"),
                "remaining_documents": remaining,
                "supporting_acts": ["acknowledge_document"],
            },
        },
        "pt-BR",
    )


def _mentions_received(text: str, *needles: str) -> None:
    lowered = text.lower()
    for needle in needles:
        assert needle in lowered, f"ack missing {needle!r} in {text!r}"


def _does_not_claim_received(text: str, *needles: str) -> None:
    lowered = text.lower()
    for needle in needles:
        assert needle not in lowered, f"ack claimed unreceived {needle!r} in {text!r}"


def _asks_remaining_docs(text: str) -> bool:
    lowered = text.lower()
    return any(
        cue in lowered
        for cue in ("envie", "enviar", "me manda", "comprovante", "holerite")
    ) and any(cue in lowered for cue in ("renda", "resid", "cnh"))


async def _process_with_template(state: ConversationCanonicalState, inbound: InboundTurn):
    async def understand(_text, _state):
        return TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING)

    from sdr.understanding import response_composer as rc

    original = rc.compose_response

    async def _template_only(s, p, tool_context=None, *, client=None):
        return rc.validate_bubbles(_template_compose(s, p, tool_context))

    rc.compose_response = _template_only
    try:
        return await process_turn(state=state, inbound=inbound, understand=understand)
    finally:
        rc.compose_response = original


# ---------------------------------------------------------------------------
# C1–C3  exact received components in the ack
# ---------------------------------------------------------------------------


def test_c1_only_cnh_acknowledges_cnh() -> None:
    inbound = _inbound_from_segments(_doc_segment("cnh", "CNH", "Segue minha CNH", name="Bruno Azevedo"))
    state = _financing_ready()
    apply_commercial_document_receipt(state, inbound)
    assert state.facts["document_status"]["cnh"] == "received"
    assert state.facts["document_status"]["proof_of_income"] != "received"
    assert state.facts["document_status"]["proof_of_residence"] != "received"

    bubbles = _ack_bubbles(received={"cnh": "received"})
    ack = bubbles[0]
    assert "Recebi sua CNH" in ack
    assert "Bruno" in ack
    _does_not_claim_received(ack, "renda", "resid")
    assert remaining_document_components(state) == ["proof_of_residence", "proof_of_income"]
    plan = decide(state)
    annotate_action_plan(plan, state)
    assert plan.primary_action == PRIMARY_ASK_REMAINING_DOCUMENTS
    assert plan.primary_action != PRIMARY_INVITE_VISIT


def test_c2_cnh_and_income_acknowledges_both() -> None:
    inbound = _inbound_from_segments(
        _doc_segment("cnh", "CNH", "CNH", order=0, name="Bruno Azevedo"),
        _doc_segment("inc", "INCOME_PROOF", "comprovante de renda", order=1),
    )
    state = _financing_ready()
    apply_commercial_document_receipt(state, inbound)
    status = state.facts["document_status"]
    assert status["cnh"] == "received"
    assert status["proof_of_income"] == "received"
    assert status["proof_of_residence"] != "received"

    bubbles = _ack_bubbles(
        received={"cnh": "received", "proof_of_income": "received"},
        kind="CNH",
    )
    ack = bubbles[0]
    _mentions_received(ack, "cnh", "renda")
    _does_not_claim_received(ack, "residência", "residencia")
    extra = " ".join(bubbles[1:]).lower()
    if extra:
        assert "resid" in extra
        assert "renda" not in extra


def test_c3_full_pack_acknowledges_all_three() -> None:
    scenario = json.loads((PHASE9 / "p9_10_todos_documentos.json").read_text(encoding="utf-8"))
    inbound, _, _ = build_replay_inbound(scenario["turns"][0], thread_id="p9-10", turn_idx=0)
    types = [
        (seg.document_extracted or {}).get("document_type")
        for seg in inbound.segments
        if getattr(seg, "content_type", None) == ContentType.DOCUMENT
    ]
    assert "CNH" in types
    assert "INCOME_PROOF" in types
    assert "RESIDENCE_PROOF" in types

    state = _financing_ready()
    apply_commercial_document_receipt(state, inbound)
    status = state.facts["document_status"]
    assert status["cnh"] == "received"
    assert status["proof_of_income"] == "received"
    assert status["proof_of_residence"] == "received"
    assert remaining_document_components(state) == []

    bubbles = _ack_bubbles(
        received={
            "cnh": "received",
            "proof_of_income": "received",
            "proof_of_residence": "received",
        },
        kind="CNH",
        primary="invite_visit",
    )
    joined = " ".join(bubbles)
    _mentions_received(joined, "cnh", "renda", "resid")
    assert not _asks_remaining_docs(joined) or "recebi" in joined.lower()
    assert "envie" not in joined.lower()


# ---------------------------------------------------------------------------
# C4  CNH + bring the rest to the store
# ---------------------------------------------------------------------------


def test_c4_cnh_plus_bring_rest_to_store_acks_cnh_and_defers() -> None:
    inbound = _inbound_from_segments(
        _doc_segment("cnh", "CNH", "Segue a CNH. Levo o restante na loja", name="Bruno Azevedo"),
    )
    prev = _financing_ready()
    merged = deterministic_merge(
        prev,
        TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING, facts={"name": "Bruno Azevedo"}),
        inbound_text=inbound.effective_text,
    )
    apply_commercial_document_receipt(merged, inbound)
    merged = refresh_actionability(merged)
    status = merged.facts.get("document_status") or {}
    assert status.get("cnh") == "received"
    assert status.get("proof_of_income") == "deferred"
    assert status.get("proof_of_residence") == "deferred"
    assert should_ask_remaining_documents(merged) is False

    plan = decide(merged)
    annotate_action_plan(plan, merged)
    assert plan.action == Action.REGISTER_VISIT_INTEREST
    assert plan.primary_action == PRIMARY_INVITE_VISIT
    assert "acknowledge_document" in (plan.supporting_acts or [])
    assert ACT_ASK_REMAINING_DOCUMENTS in (plan.forbidden_concurrent_actions or [])

    dialogue = build_dialogue_plan(
        inbound_text=inbound.effective_text,
        action=plan.action,
        ask_field=plan.ask_field,
        intent=merged.intent,
        ack_kind="document_received",
        inbound_content_type="DOCUMENT",
        document_kind="CNH",
        state=merged,
        reason_code=plan.reason_code,
    )
    assert dialogue.primary_action == PRIMARY_INVITE_VISIT
    assert "acknowledge_document" in dialogue.supporting_acts
    assert DialogueAct.INVITE_VISIT.value in dialogue.acts or plan.action == Action.REGISTER_VISIT_INTEREST

    bubbles = _template_compose(
        {
            "language": "pt-BR",
            "ack_kind": "document_received",
            "document_kind": "CNH",
            "customer_name": "Bruno Azevedo",
            "inbound_content_type": "DOCUMENT",
            "facts": merged.facts,
            "dialogue_plan": dialogue.to_dict(),
        },
        {"action": "register_visit_interest", "handoff": False, "tool_calls": []},
        {},
    )
    joined = " ".join(bubbles)
    assert "Recebi sua CNH" in joined
    assert "envie" not in joined.lower()
    assert "enviar" not in joined.lower() or "loja" in joined.lower()


# ---------------------------------------------------------------------------
# C5–C6  commercial receipt survives corruption / storage failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_c5_corrupted_cnh_is_still_commercially_received() -> None:
    inbound = InboundTurn(
        thread_id="t-doc-ack",
        content_type=ContentType.DOCUMENT,
        text="tipo: CNH",
        media_status=MediaStatus.OK,
        mime_type="application/pdf",
        raw_message_ref={
            "document_extracted": {"document_type": "CNH", "extraction_ok": False},
            "storage_simulated": {"status": "permanent_failure", "bucket_kind": "private", "public": False},
        },
        segments=[
            InboundSegment(
                message_id="cnh-corrupt",
                content_type=ContentType.DOCUMENT,
                text="tipo: CNH",
                media_status=MediaStatus.OK,
                document_extracted={"document_type": "CNH", "name": None, "cpf": None},
            )
        ],
    )
    result = await _process_with_template(_financing_ready(), inbound)
    joined = " ".join(result.outbound_texts)
    assert "Recebi sua CNH" in joined
    assert result.state.document_received is True
    assert result.state.facts.get("document_status", {}).get("cnh") == "received"
    for leak in STORAGE_LEAKS:
        assert leak not in joined.lower()


@pytest.mark.asyncio
async def test_c6_storage_failure_does_not_leak() -> None:
    inbound = InboundTurn(
        thread_id="t-doc-ack",
        content_type=ContentType.DOCUMENT,
        text="tipo: CNH",
        media_status=MediaStatus.OK,
        raw_message_ref={
            "document_extracted": {"document_type": "CNH", "name": "Bruno Azevedo"},
            "storage_simulated": {
                "status": "retryable_failure",
                "bucket_kind": "private",
                "public": False,
                "error": "NoSuchBucket:s3://facilcar-sdr-documents",
            },
        },
        segments=[
            _doc_segment("cnh", "CNH", "tipo: CNH", name="Bruno Azevedo"),
        ],
    )
    result = await _process_with_template(_financing_ready(), inbound)
    joined = " ".join(result.outbound_texts).lower()
    assert "recebi sua cnh" in joined
    for leak in ("bucket", "s3", "storage", "nosuchbucket", "salva no sistema"):
        assert leak not in joined


# ---------------------------------------------------------------------------
# C7–C9  state: do not ack missing, do not regress received, do not re-ask deferred
# ---------------------------------------------------------------------------


def test_c7_not_received_document_is_not_acknowledged() -> None:
    inbound = _inbound_from_segments(_doc_segment("cnh", "CNH", "CNH", name="Bruno Azevedo"))
    state = _financing_ready()
    apply_commercial_document_receipt(state, inbound)
    bubbles = _ack_bubbles(received={"cnh": "received"})
    ack = bubbles[0]
    assert "Recebi sua CNH" in ack
    _does_not_claim_received(ack, "renda", "residência", "residencia")


def test_c8_received_does_not_regress_to_deferred() -> None:
    prev = _financing_ready(facts={"document_status": {"cnh": "received"}})
    prev.document_received = True
    merged = deterministic_merge(
        prev,
        TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING, facts={"documents_deferred": True}),
        inbound_text="Levo o restante na loja",
    )
    status = merged.facts.get("document_status") or {}
    assert status.get("cnh") == "received"
    assert status.get("proof_of_income") == "deferred"
    assert status.get("proof_of_residence") == "deferred"
    again = merge_document_status(status, {"cnh": "deferred", "proof_of_income": "missing"})
    assert again["cnh"] == "received"
    assert again["proof_of_income"] == "deferred"


def test_c9_deferred_docs_are_not_asked_again() -> None:
    prev = _financing_ready(facts={"document_status": {"cnh": "received"}})
    merged = deterministic_merge(
        prev,
        TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING, facts={"documents_deferred": True}),
        inbound_text="Levo o restante na loja",
    )
    merged = refresh_actionability(merged)
    assert should_ask_remaining_documents(merged) is False
    plan = decide(merged)
    assert plan.ask_field != "documents"
    assert plan.primary_action != PRIMARY_ASK_REMAINING_DOCUMENTS


# ---------------------------------------------------------------------------
# C10–C12  visit remains primary; no storage claim; extracted name not re-asked
# ---------------------------------------------------------------------------


def test_c10_ack_plus_visit_keeps_visit_as_only_primary() -> None:
    state = _financing_ready(
        document_received=True,
        facts={
            "document_status": {
                "cnh": "received",
                "proof_of_income": "received",
                "proof_of_residence": "received",
            }
        },
    )
    plan = decide(state)
    annotate_action_plan(plan, state)
    assert plan.action == Action.REGISTER_VISIT_INTEREST
    assert plan.primary_action == PRIMARY_INVITE_VISIT
    assert "acknowledge_document" in (plan.supporting_acts or [])
    assert plan.supporting_acts.count("acknowledge_document") == 1
    assert ACT_ASK_REMAINING_DOCUMENTS in (plan.forbidden_concurrent_actions or [])

    dialogue = build_dialogue_plan(
        inbound_text="Seguem CNH, renda e residência",
        action=plan.action,
        ask_field=plan.ask_field,
        intent=state.intent,
        ack_kind="document_received",
        inbound_content_type="DOCUMENT",
        document_kind="CNH",
        state=state,
        reason_code=plan.reason_code,
    )
    assert dialogue.primary_action == PRIMARY_INVITE_VISIT
    assert "acknowledge_document" in dialogue.supporting_acts
    assert dialogue.primary_action != PRIMARY_ASK_REMAINING_DOCUMENTS


def test_c11_ack_does_not_say_saved_in_the_system() -> None:
    bubbles = _ack_bubbles(
        received={
            "cnh": "received",
            "proof_of_income": "received",
            "proof_of_residence": "received",
        },
        primary="invite_visit",
    )
    joined = " ".join(bubbles).lower()
    for leak in STORAGE_LEAKS:
        assert leak not in joined
    assert "salva na sua ficha" not in joined
    assert "disponível para o vendedor" not in joined


@pytest.mark.asyncio
async def test_c12_extracted_name_is_not_reasked() -> None:
    inbound = _inbound_from_segments(
        _doc_segment("cnh", "CNH", "tipo: CNH\nnome: Bruno Azevedo", name="Bruno Azevedo"),
    )
    result = await _process_with_template(_financing_ready(facts={"name": None}), inbound)
    assert result.state.facts.get("name") == "Bruno Azevedo" or result.state.customer.name == "Bruno Azevedo"
    assert next_ask_field(result.state) != "name"
    assert result.action_plan.ask_field != "name"
    joined = " ".join(result.outbound_texts).lower()
    assert "seu nome" not in joined
    assert "me diga seu nome" not in joined
