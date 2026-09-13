"""Commercial next-action policy — what the turn must do, not how to word it.

Priority is contextual, not a rigid sequence:
answer question → objection/intent change → acknowledge → vendor/visit →
essential qualification → applicable documents → optional enrichment →
visit invite → handoff.

Remaining financing documents never block ``handoff_ready``.
``profile_complete`` stays false while applicable components are pending.
"""

from __future__ import annotations

from typing import Any

from sdr.domain.document_status import (
    DOCUMENT_COMPONENTS,
    STATUS_DEFERRED,
    STATUS_RECEIVED,
    deferred_components,
    missing_components,
    received_components,
)
from sdr.domain.types import Action, ActionPlan, BusinessIntent, ConversationCanonicalState

ENRICHMENT_ASK_LIMIT = 2

PRIMARY_ANSWER_QUESTION = "answer_direct_question"
PRIMARY_ACKNOWLEDGE = "acknowledge_fact"
PRIMARY_ASK_REMAINING_DOCUMENTS = "ask_remaining_documents"
PRIMARY_ASK_FIELD = "ask_field"
PRIMARY_PRESENT_VEHICLE = "present_vehicle"
PRIMARY_INVITE_VISIT = "invite_visit"
PRIMARY_HANDOFF = "handoff"
PRIMARY_RAPPORT = "rapport"
PRIMARY_CLARIFY = "clarify"

ACT_ASK_REMAINING_DOCUMENTS = "ask_remaining_documents"
ACT_INVITE_VISIT = "invite_visit"
ACT_HANDOFF = "handoff"


def _payment_is_cash(facts: dict[str, Any]) -> bool:
    raw = str(facts.get("payment_method") or facts.get("payment_type") or "").strip().lower()
    folded = raw.replace("à", "a").replace("á", "a")
    return folded in {"cash", "a vista", "a_vista", "avista"}


def financing_documents_applicable(state: ConversationCanonicalState) -> bool:
    """Documentary pack applies only while the live deal is financing."""
    if _payment_is_cash(state.facts):
        return False
    if state.intent == BusinessIntent.PURCHASE_FINANCING:
        return True
    if state.intent == BusinessIntent.TRADE:
        from sdr.domain.qualifications import difference_is_financed

        return difference_is_financed(state.facts)
    return False


def document_status_map(state: ConversationCanonicalState) -> dict[str, Any]:
    raw = state.facts.get("document_status")
    return raw if isinstance(raw, dict) else {}


def remaining_document_components(state: ConversationCanonicalState) -> list[str]:
    if not financing_documents_applicable(state):
        return []
    deferred = set(state.deferred_fields or [])
    status = document_status_map(state)
    remaining: list[str] = []
    for comp in DOCUMENT_COMPONENTS:
        if comp in deferred:
            continue
        if status.get(comp) in {STATUS_RECEIVED, STATUS_DEFERRED}:
            continue
        remaining.append(comp)
    return remaining


def any_document_received(state: ConversationCanonicalState) -> bool:
    if state.document_received:
        return True
    return bool(received_components(document_status_map(state)))


def documents_pack_complete(state: ConversationCanonicalState) -> bool:
    return not remaining_document_components(state)


def should_ask_remaining_documents(state: ConversationCanonicalState) -> bool:
    """Remaining financing proofs are not optional enrichment.

    The enrichment cap must not suppress the single remaining-docs ask after
    a partial receive (e.g. CNH only).
    """
    if not remaining_document_components(state):
        return False
    if getattr(state, "remaining_documents_asked", False):
        return False
    if state.facts.get("documents_deferred") is True and not any_document_received(state):
        return False
    if not any_document_received(state):
        return False
    return True


def isolated_document_unavailability(state: ConversationCanonicalState) -> bool:
    """Document deferral/unavailability without explicit visit evidence.

    Visit interest is never inferred from missing proofs. Prior visit facts
    on the state still count as visit evidence via ``visit_signal_this_turn``.
    """
    if visit_signal_this_turn(state):
        return False
    if getattr(state, "needs_visit_slot_offer", False):
        return False
    if getattr(state, "documents_unavailable_this_turn", False):
        return True
    if state.facts.get("documents_deferred") is True and not remaining_document_components(state):
        return True
    return False


def enrichment_cap_reached(state: ConversationCanonicalState) -> bool:
    if not state.handoff_ready:
        return False
    return int(getattr(state, "enrichment_ask_count", 0) or 0) >= ENRICHMENT_ASK_LIMIT


def visit_signal_this_turn(state: ConversationCanonicalState) -> bool:
    if state.signals.visit_intent is True:
        return True
    if state.visit_interest or state.visit_preferred_time:
        return True
    return bool(state.visit_date or state.visit_time or state.visit_period)


def vendor_signal_this_turn(state: ConversationCanonicalState) -> bool:
    return state.signals.explicit_handoff is True


def annotate_action_plan(
    plan: ActionPlan,
    state: ConversationCanonicalState,
    *,
    inbound_has_direct_question: bool = False,
) -> ActionPlan:
    """Attach the auditable primary-action contract to an ActionPlan."""
    remaining = remaining_document_components(state)
    received = received_components(document_status_map(state))
    deferred = deferred_components(document_status_map(state))
    supporting: list[str] = []
    forbidden: list[str] = []
    primary = PRIMARY_ASK_FIELD
    vehicle_label = None
    vehicle_label_source = "none"
    if state.primary_vehicle_id:
        from sdr.domain.vehicle_catalog import conversational_label_for_id

        presented = getattr(state, "presented_vehicle_catalog", None)
        vehicle_label = conversational_label_for_id(
            state.primary_vehicle_id,
            presented=presented if isinstance(presented, dict) else None,
        )
        if vehicle_label:
            vehicle_label_source = "catalog"

    action = plan.action
    has_question = inbound_has_direct_question or bool(getattr(state, "unanswered_questions", None))
    if action == Action.HANDOFF_VENDOR:
        primary = PRIMARY_HANDOFF
        forbidden.append(ACT_ASK_REMAINING_DOCUMENTS)
        if has_question:
            supporting.append(PRIMARY_ANSWER_QUESTION)
    elif has_question:
        primary = PRIMARY_ANSWER_QUESTION
        forbidden.extend([ACT_INVITE_VISIT, ACT_HANDOFF, ACT_ASK_REMAINING_DOCUMENTS])
        if plan.ask_field and plan.ask_field != "documents":
            supporting.append(PRIMARY_ASK_FIELD)
        if state.document_received:
            supporting.append("acknowledge_document")
    elif action == Action.REGISTER_VISIT_INTEREST:
        primary = PRIMARY_INVITE_VISIT
        forbidden.append(ACT_ASK_REMAINING_DOCUMENTS)
        if state.document_received and received:
            supporting.append("acknowledge_document")
    elif action == Action.ASK_INFO and plan.ask_field == "documents" and remaining and any_document_received(state):
        primary = PRIMARY_ASK_REMAINING_DOCUMENTS
        supporting.append("acknowledge_document")
        forbidden.extend([ACT_INVITE_VISIT, ACT_HANDOFF])
    elif action == Action.SHOW_OFFERS:
        primary = PRIMARY_PRESENT_VEHICLE
    elif action == Action.SMALLTALK:
        primary = PRIMARY_RAPPORT
    elif action == Action.COMMERCIAL_UNKNOWN:
        primary = PRIMARY_CLARIFY
    elif action == Action.ASK_INFO:
        primary = PRIMARY_ASK_FIELD
        if state.document_received:
            supporting.append("acknowledge_document")

    plan.primary_action = primary
    plan.supporting_acts = supporting
    plan.forbidden_concurrent_actions = forbidden
    plan.qualification_trace = {
        "handoff_ready": bool(state.handoff_ready),
        "profile_complete": bool(state.profile_complete),
        "primary_vehicle_id": state.primary_vehicle_id,
        "primary_vehicle_label": vehicle_label,
        "vehicle_label_source": vehicle_label_source,
        "documents_received": received,
        "documents_missing": remaining,
        "documents_deferred": deferred,
        "remaining_documents_asked": bool(getattr(state, "remaining_documents_asked", False)),
        "enrichment_ask_count": int(getattr(state, "enrichment_ask_count", 0) or 0),
        "enrichment_limit": ENRICHMENT_ASK_LIMIT,
        "direct_question_detected": bool(has_question),
        "next_question": plan.ask_field or plan.next_question,
    }
    return plan
