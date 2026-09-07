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
from sdr.domain.installment import installment_capacity, is_installment_tight
from sdr.domain.inventory_search import (
    build_inventory_search_request,
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
    LeadTemperature,
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

# After a vehicle is on the table, financing/docs/name answers must not re-SHOW_OFFERS.
_POST_SHOW_ROTEIRO = frozenset({
    "down_payment",
    "desired_installment",
    "documents",
    "name",
    "trade_model",
    "trade_year",
    "trade_color",
    "mileage",
    "trade_has_financing",
    "trade_installment_value",
    "trade_installments_remaining",
    "trade_has_debts",
    "trade_price_expectation",
    "trade_renavam",
})


def _state_search_key(state: ConversationCanonicalState) -> str:
    req = build_inventory_search_request(
        state.facts,
        alternative_scope=state.alternative_scope,
        budget_status=state.budget_status,
    )
    return inventory_search_key_from_request(
        req,
        last_shown_vehicle_ids=state.last_shown_vehicle_ids or [],
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
    if key == state.last_inventory_search_key:
        return False
    # Vehicle already presented: answering the financing roteiro must not
    # reopen inventory because an LLM leaked engine/budget into the hash.
    if (
        state.last_shown_vehicle_ids
        and state.alternative_scope == AlternativeScope.NONE
        and next_ask_field(state) in _POST_SHOW_ROTEIRO
    ):
        return False
    # Post-visit: a visit was already invited and triage is actionable — inventory
    # was already presented. Any new fact that changes the hash (e.g. visit_intent
    # signal extraction) must not reopen the catalog. The next action is handoff.
    if state.visit_invited and is_seller_actionable(state):
        return False
    return True


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
        ask = next_ask_field(state)
        if ask and ask not in (None, "intent"):
            return ActionPlan(
                action=Action.ASK_INFO,
                handoff=False,
                ask_field=ask,
                next_question=ask,
                reason_code="document_received_ack",
                reason="Acknowledge extracted document; continue roteiro",
            )
        if state.intent in _VISIT_ELIGIBLE_INTENTS and not state.visit_invited:
            state.visit_invited = True
            return ActionPlan(
                action=Action.REGISTER_VISIT_INTEREST,
                handoff=False,
                tool_calls=[{"tool": "register_visit_interest"}],
                reason_code="document_received_visit",
                reason="Acknowledge document and invite a visit",
            )
        return ActionPlan(
            action=Action.ASK_INFO,
            handoff=False,
            reason_code="document_received_ack",
            reason="Acknowledge extracted document; do not invent a question",
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
            # When the customer confirmed a specific slot, send the location pin
            # alongside the handoff confirmation so they have the store address.
            if state.visit_preferred_time:
                tool_calls.append({"tool": "send_location"})
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

    # Desired installment vs published price — offer cheaper options once.
    if (
        not state.installment_mismatch_offered
        and state.pending_interaction == PendingInteraction.NONE
        and is_installment_tight(
            price_cash=state.last_shown_price_cash,
            down_payment=state.facts.get("down_payment"),
            desired_installment=state.facts.get("desired_installment"),
        )
    ):
        capacity = installment_capacity(
            state.facts.get("down_payment"),
            state.facts.get("desired_installment"),
        )
        state.installment_mismatch_offered = True
        state.installment_capacity = capacity
        state.pending_interaction = PendingInteraction.OFFER_ALTERNATIVES
        return ActionPlan(
            action=Action.ASK_INFO,
            handoff=False,
            ask_field="alternatives_ok",
            next_question="alternatives_ok",
            reason_code="installment_tight",
            reason="Desired installment is tight vs published cash price",
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
        # If the visit question was just asked this turn (pending_question="visit"),
        # allow one turn for natural response before handoff. The subsequent turn
        # (pending_question cleared) always handoffs. This prevents "Obrigado" or
        # a new question from being treated as implicit visit confirmation.
        if state.pending_question == "visit":
            # Hot lead already invited: ask for a slot instead of inventing a
            # new commercial question (COMMERCIAL_UNKNOWN restarted the roteiro).
            if compute_temperature(state) == LeadTemperature.HOT:
                return ActionPlan(
                    action=Action.ASK_INFO,
                    handoff=False,
                    ask_field="visit",
                    next_question="visit",
                    reason_code="visit_schedule_ask",
                    reason="Ask for visit day/time before handoff",
                )
            pass  # fall through to COMMERCIAL_UNKNOWN / location / smalltalk
        else:
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
