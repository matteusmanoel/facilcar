"""Deterministic decision engine — ActionPlan from canonical state.

Priority:
1. HUMAN_ACTIVE / HANDOFF_SENT → NO_REPLY
2. Pending OFFER_ALTERNATIVES unresolved → clarify (keep pending)
3. Store location request → SEND_LOCATION (before visit/handoff)
4. Document received this turn → ack (do not jump to visit)
5. Explicit gated handoff signals (vendor / offer / visit / immediate close)
6. Inventory when preference known OR widened scope, and search key changed
7. Photo request of a shown vehicle → SEND_PHOTOS
8. Triage actionable → visit invitation, then HANDOFF_VENDOR
9. Budget without model → inventory alternatives
10. Commercial incomplete → ASK_INFO
11. SMALLTALK → SMALLTALK
12. UNKNOWN → COMMERCIAL_UNKNOWN

Inventory-first: vehicle preference + budget alone must not skip inventory
and force irreversible handoff. Triage actionability is evaluated only after
the current search key has already been executed (or no vehicle interest).
"""

from __future__ import annotations

from sdr.domain.budget_status import BudgetStatus
from sdr.domain.handoff import (
    HANDOFF_CONFIRMATION_PT_BR,
    compute_temperature,
    should_handoff_now,
)
from sdr.domain.inventory_search import (
    inventory_search_key,
    inventory_search_key_from_request,
)
from sdr.domain.pending_interaction import (
    AlternativeScope,
    PendingInteraction,
)
from sdr.domain.qualifications import (
    _desired_vehicle,
    is_seller_actionable,
    next_ask_field,
    refresh_actionability,
)
from sdr.domain.types import (
    Action,
    Actionability,
    ActionPlan,
    BusinessIntent,
    ConversationCanonicalState,
    LifecycleStatus,
)

# Intents where a visit invitation is appropriate before handoff.
_VISIT_ELIGIBLE_INTENTS = frozenset({
    BusinessIntent.PURCHASE,
    BusinessIntent.PURCHASE_FINANCING,
    BusinessIntent.TRADE,
    BusinessIntent.SALE,
    BusinessIntent.CONSIGNMENT,
})

# Re-export for callers that imported inventory_search_key from decision.
__all__ = ["decide", "inventory_search_key", "inventory_search_key_from_request"]


def _state_search_key(state: ConversationCanonicalState) -> str:
    return inventory_search_key(
        state.facts,
        alternative_scope=state.alternative_scope,
        budget_status=state.budget_status,
    )


def _needs_inventory_search(state: ConversationCanonicalState) -> bool:
    if state.intent not in (BusinessIntent.PURCHASE, BusinessIntent.PURCHASE_FINANCING):
        return False

    widened = state.alternative_scope in (
        AlternativeScope.SIMILAR,
        AlternativeScope.ANY_VEHICLE,
    )
    if not widened and not _desired_vehicle(state.facts):
        return False

    key = _state_search_key(state)
    return key != state.last_inventory_search_key


def decide(state: ConversationCanonicalState) -> ActionPlan:
    """Decide next action from canonical state."""
    refresh_actionability(state)
    status = state.lifecycle.status

    if status in (LifecycleStatus.HUMAN_ACTIVE, LifecycleStatus.HANDOFF_SENT):
        return ActionPlan(
            action=Action.NO_REPLY,
            handoff=False,
            reason_code="human_or_handoff_silence",
            reason="Conversation already with human or handoff confirmation sent",
        )

    if status == LifecycleStatus.HUMAN_CLOSED:
        if state.intent in (BusinessIntent.UNKNOWN, BusinessIntent.SMALLTALK):
            return ActionPlan(
                action=Action.NO_REPLY,
                handoff=False,
                reason_code="human_closed",
                reason="Thread closed; no new commercial intent",
            )

    # Pending affordance without a resolution this turn → clarify, do not invent.
    if state.pending_interaction == PendingInteraction.OFFER_ALTERNATIVES:
        return ActionPlan(
            action=Action.ASK_INFO,
            handoff=False,
            ask_field="alternatives_ok",
            next_question="alternatives_ok",
            reason_code="pending_alternatives_clarify",
            reason="Customer reply to alternatives offer was ambiguous or missing",
        )

    # Store location is a capability request — execute before visit/handoff.
    if state.location_request:
        return ActionPlan(
            action=Action.SEND_LOCATION,
            handoff=False,
            tool_calls=[{"tool": "send_location"}],
            ask_field="visit",
            next_question="visit",
            reason_code="explicit_location_request",
            reason="Send store pin and invite a visit",
        )

    # A received document this turn is acknowledged before visit/handoff.
    if state.document_received:
        return ActionPlan(
            action=Action.ASK_INFO,
            handoff=False,
            reason_code="document_received_ack",
            reason="Acknowledge extracted document; do not jump to visit this turn",
        )

    # Irreversible handoff only from gated explicit signals — never from budget alone.
    if should_handoff_now(state):
        reason = _handoff_reason(state)
        state.lifecycle.status = LifecycleStatus.READY_FOR_HANDOFF
        state.lifecycle.handoff_reason = reason
        state.business.actionability = Actionability.HANDOFF_NOW
        state.temperature = compute_temperature(state)
        tool_calls: list[dict] = []
        if state.signals.visit_intent is True:
            tool_calls.append({"tool": "register_visit_interest"})
        return ActionPlan(
            action=Action.HANDOFF_VENDOR,
            handoff=True,
            tool_calls=tool_calls,
            reason_code=reason,
            reason=HANDOFF_CONFIRMATION_PT_BR,
        )

    # Inventory BEFORE triage handoff — respect preference and widened scope.
    if _needs_inventory_search(state):
        key = _state_search_key(state)
        ask = next_ask_field(state)
        follow = ask if ask and ask not in (None, "intent", "desired_model") else None
        return ActionPlan(
            action=Action.SHOW_OFFERS,
            handoff=False,
            tool_calls=[{"tool": "inventory_search", "_search_key": key}],
            ask_field=follow,
            next_question=follow,
            reason_code=(
                "widened_inventory_lookup"
                if state.alternative_scope != AlternativeScope.NONE
                else "model_known_inventory_lookup"
            ),
            reason="Show published inventory for current authorized search scope",
        )

    # Explicit photo request of a vehicle already presented — execute, don't ask permission.
    if state.photo_request and state.last_shown_vehicle_ids:
        vehicle_id = state.last_shown_vehicle_ids[0]
        ask = next_ask_field(state)
        follow = ask if ask and ask not in (None, "intent") else None
        return ActionPlan(
            action=Action.SEND_PHOTOS,
            handoff=False,
            tool_calls=[{"tool": "send_photos", "vehicle_id": vehicle_id}],
            ask_field=follow,
            next_question=follow,
            reason_code="explicit_photo_request",
            reason="Send listing photos of the last presented vehicle",
        )

    # Triage actionable only after inventory opportunity has been consumed.
    if is_seller_actionable(state):
        # Visit invitation before irreversible handoff (non-blocking: max 1 turn).
        if state.intent in _VISIT_ELIGIBLE_INTENTS and not state.visit_invited:
            state.visit_invited = True
            return ActionPlan(
                action=Action.REGISTER_VISIT_INTEREST,
                handoff=False,
                tool_calls=[{"tool": "register_visit_interest"}],
                reason_code="visit_invitation_pre_handoff",
                reason="Invite customer to visit store before handoff",
            )
        state.lifecycle.status = LifecycleStatus.READY_FOR_HANDOFF
        state.lifecycle.handoff_reason = "triage_actionable"
        state.business.actionability = Actionability.ACTIONABLE
        state.temperature = compute_temperature(state)
        return ActionPlan(
            action=Action.HANDOFF_VENDOR,
            handoff=True,
            reason_code="triage_actionable",
            reason=HANDOFF_CONFIRMATION_PT_BR,
        )

    # Budget known but no vehicle preference yet → alternatives by budget.
    if (
        state.intent in (BusinessIntent.PURCHASE, BusinessIntent.PURCHASE_FINANCING)
        and next_ask_field(state) == "desired_model"
        and state.budget_status == BudgetStatus.PROVIDED
        and state.facts.get("budget")
    ):
        key = _state_search_key(state)
        if key != state.last_inventory_search_key:
            return ActionPlan(
                action=Action.SHOW_OFFERS,
                handoff=False,
                tool_calls=[{"tool": "inventory_search", "_search_key": key}],
                reason_code="budget_without_model",
                reason="Show published alternatives for known budget",
            )

    ask = next_ask_field(state)
    if (
        state.intent not in (BusinessIntent.UNKNOWN, BusinessIntent.SMALLTALK)
        or ask not in (None, "intent")
    ):
        if ask and ask != "intent":
            if state.lifecycle.status == LifecycleStatus.BOT_ACTIVE:
                state.lifecycle.status = LifecycleStatus.QUALIFYING
            return ActionPlan(
                action=Action.ASK_INFO,
                handoff=False,
                ask_field=ask,
                next_question=ask,
                reason_code="need_field",
                reason=f"Ask one field: {ask}",
            )

    if state.intent == BusinessIntent.SMALLTALK:
        return ActionPlan(
            action=Action.SMALLTALK,
            handoff=False,
            reason_code="greeting_or_chitchat",
            reason="Recognized as greeting or chitchat",
        )

    return ActionPlan(
        action=Action.COMMERCIAL_UNKNOWN,
        handoff=False,
        reason_code="unresolved_intent",
        reason=(
            "Intent could not be resolved. "
            "Ask a focused clarifying question to progress without restarting."
        ),
    )


def _handoff_reason(state: ConversationCanonicalState) -> str:
    sig = state.signals
    if sig.explicit_handoff is True:
        return "explicit_vendor"
    if sig.explicit_offer is True:
        return "explicit_offer"
    if sig.high_purchase_intent is True:
        return "high_purchase_intent"
    if sig.visit_intent is True:
        return "visit_intent"
    return "handoff_now"
