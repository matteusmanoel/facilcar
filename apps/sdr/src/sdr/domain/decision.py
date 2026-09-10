"""Deterministic decision engine — ActionPlan from canonical state.

Priority:
1. HUMAN_ACTIVE → NO_REPLY
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
from sdr.domain.ownership import vendor_already_notified
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
    is_handoff_ready,
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

# After a vehicle is on the table, financing/docs answers must not re-SHOW_OFFERS.
# "name" is intentionally excluded: if the customer changes their model preference
# (a genuine new search), the decision engine must not block the re-search just
# because the only remaining field is "name". Name does not affect the search key,
# so if the key changed, it must be due to a real preference change.
_POST_SHOW_ROTEIRO = frozenset({
    "down_payment",
    "desired_installment",
    "documents",
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


def _defer_remaining_if_path_changed(state: ConversationCanonicalState) -> None:
    """Visit/vendor path: remaining components become deferred, never received."""
    from sdr.domain.document_status import STATUS_DEFERRED, merge_document_status
    from sdr.domain.qualification_policy import remaining_document_components

    remaining = remaining_document_components(state)
    if not remaining:
        return
    deferred = list(state.deferred_fields or [])
    patch = {name: STATUS_DEFERRED for name in remaining}
    for name in remaining:
        if name not in deferred:
            deferred.append(name)
    state.deferred_fields = deferred
    state.facts["document_status"] = merge_document_status(state.facts.get("document_status"), patch)
    state.facts["documents_deferred"] = True
    state.remaining_documents_asked = True


def _mark_enrichment_ask(state: ConversationCanonicalState, *, remaining: bool) -> None:
    if remaining:
        state.remaining_documents_asked = True
        state.documents_asked = True
    if state.handoff_ready:
        state.enrichment_ask_count = int(getattr(state, "enrichment_ask_count", 0) or 0) + 1


def _needs_inventory_search(state: ConversationCanonicalState) -> bool:
    if state.intent not in (
        BusinessIntent.PURCHASE,
        BusinessIntent.PURCHASE_FINANCING,
        BusinessIntent.TRADE,
    ):
        return False

    widened = state.alternative_scope in (
        AlternativeScope.SIMILAR,
        AlternativeScope.ANY_VEHICLE,
    )
    if not widened and not _desired_vehicle(state.facts) and not state.primary_vehicle_id:
        return False

    key = _state_search_key(state)
    if key == state.last_inventory_search_key:
        return False
    if state.last_shown_vehicle_ids:
        # Tests and older turns may have stored the hash before last_shown
        # was recorded (vehicle_text still in the payload). Treat that as
        # the same search unless identity fields actually changed.
        req = build_inventory_search_request(
            state.facts,
            alternative_scope=state.alternative_scope,
            budget_status=state.budget_status,
        )
        legacy = inventory_search_key_from_request(req, last_shown_vehicle_ids=None)
        if legacy == state.last_inventory_search_key:
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
    if state.visit_invited and is_handoff_ready(state):
        return False
    return True


def decide(state: ConversationCanonicalState) -> ActionPlan:
    """Decide next action from canonical state."""
    refresh_actionability(state)
    status = state.lifecycle.status

    from sdr.domain.qualification_policy import (
        annotate_action_plan,
        remaining_document_components,
        should_ask_remaining_documents,
        isolated_document_unavailability,
        vendor_signal_this_turn,
        visit_signal_this_turn,
    )

    def _finish(plan: ActionPlan) -> ActionPlan:
        return annotate_action_plan(
            plan,
            state,
            inbound_has_direct_question=bool(getattr(state, "unanswered_questions", None)),
        )

    def _has_unanswered_question() -> bool:
        return bool(getattr(state, "unanswered_questions", None))

    def _answer_unanswered_question() -> ActionPlan:
        return _finish(ActionPlan(
            action=Action.ASK_INFO,
            handoff=False,
            reason_code="answer_direct_question",
            reason="Answer the customer's unanswered commercial question before visit or handoff",
        ))

    if status == LifecycleStatus.HUMAN_ACTIVE:
        return _finish(ActionPlan(
            action=Action.NO_REPLY,
            handoff=False,
            reason_code="human_or_handoff_silence",
            reason="Conversation already with human",
        ))

    if status == LifecycleStatus.HUMAN_CLOSED:
        if state.intent in (BusinessIntent.UNKNOWN, BusinessIntent.SMALLTALK):
            return _finish(ActionPlan(
                action=Action.NO_REPLY,
                handoff=False,
                reason_code="human_closed",
                reason="Thread closed; no new commercial intent",
            ))

    # Desired vehicle unavailable in a TRADE: do not continue the evaluation
    # roteiro as if that specific swap can still close. If the preference
    # changed, inventory must run first.
    if (
        state.last_inventory_outcome in ("SUCCESS_EMPTY", "SUCCESS_SOLD")
        and state.intent == BusinessIntent.TRADE
        and state.alternative_scope == AlternativeScope.NONE
        and state.pending_interaction == PendingInteraction.NONE
        and not state.last_shown_vehicle_ids
        and not _needs_inventory_search(state)
    ):
        return _finish(ActionPlan(
            action=Action.ASK_INFO,
            handoff=False,
            ask_field="alternatives_ok",
            next_question="alternatives_ok",
            reason_code="desired_unavailable_clarify",
            reason="Desired vehicle is unavailable; clarify alternatives before continuing",
        ))
    if state.pending_interaction == PendingInteraction.OFFER_ALTERNATIVES:
        return _finish(ActionPlan(
            action=Action.ASK_INFO,
            handoff=False,
            ask_field="alternatives_ok",
            next_question="alternatives_ok",
            reason_code="pending_alternatives_clarify",
            reason="Customer reply to alternatives offer was ambiguous or missing",
        ))

    # Store location is a capability request — execute before visit/handoff.
    if state.location_request:
        from sdr.domain.visit import should_send_store_location

        if should_send_store_location(state):
            return _finish(ActionPlan(
                action=Action.SEND_LOCATION,
                handoff=False,
                tool_calls=[{"tool": "send_location"}],
                ask_field="visit",
                next_question="visit",
                reason_code="explicit_location_request",
                reason="Send store pin and invite a visit",
            ))

    # Irreversible handoff from gated explicit signals — vendor beats documents.
    # A commercial question is not a vendor emergency; explicit_handoff may still win.
    if should_handoff_now(state):
        if _has_unanswered_question() and not vendor_signal_this_turn(state):
            return _answer_unanswered_question()
        reason = _handoff_reason(state)
        if vendor_signal_this_turn(state) or visit_signal_this_turn(state):
            _defer_remaining_if_path_changed(state)
        state.lifecycle.status = LifecycleStatus.READY_FOR_HANDOFF
        state.lifecycle.handoff_reason = reason
        state.business.actionability = Actionability.HANDOFF_NOW
        state.temperature = compute_temperature(state)
        tool_calls: list[dict] = []
        if state.signals.visit_intent is True:
            tool_calls.append({"tool": "register_visit_interest"})
            from sdr.domain.visit import should_send_store_location

            if should_send_store_location(state):
                tool_calls.append({"tool": "send_location"})
        return _finish(ActionPlan(
            action=Action.HANDOFF_VENDOR,
            handoff=True,
            tool_calls=tool_calls,
            reason_code=reason,
            reason=HANDOFF_CONFIRMATION_PT_BR,
        ))

    # Visit during documentary collection is an alternative path, not a concurrent ask.
    if visit_signal_this_turn(state) and remaining_document_components(state):
        if _has_unanswered_question():
            return _answer_unanswered_question()
        _defer_remaining_if_path_changed(state)
        if state.intent in _VISIT_ELIGIBLE_INTENTS and not state.visit_invited:
            state.visit_invited = True
            return _finish(ActionPlan(
                action=Action.REGISTER_VISIT_INTEREST,
                handoff=False,
                tool_calls=[{"tool": "register_visit_interest"}],
                reason_code="visit_prevails_over_documents",
                reason="Visit manifestation replaces remaining document collection",
            ))

    # A received document this turn is acknowledged before visit/handoff.
    if state.document_received:
        if _has_unanswered_question():
            return _answer_unanswered_question()
        ask = next_ask_field(state)
        if (
            not vendor_already_notified(state)
            and ask
            and ask not in (None, "intent", "documents")
        ):
            _mark_enrichment_ask(state, remaining=False)
            return _finish(ActionPlan(
                action=Action.ASK_INFO,
                handoff=False,
                ask_field=ask,
                next_question=ask,
                reason_code="document_received_ack",
                reason="Acknowledge extracted document; continue roteiro",
            ))
        if (
            should_ask_remaining_documents(state)
            and not visit_signal_this_turn(state)
            and not vendor_signal_this_turn(state)
        ):
            _mark_enrichment_ask(state, remaining=True)
            return _finish(ActionPlan(
                action=Action.ASK_INFO,
                handoff=False,
                ask_field="documents",
                next_question="documents",
                reason_code="remaining_documents",
                reason="Acknowledge received document and ask remaining pack once",
            ))
        if not vendor_already_notified(state):
            if remaining_document_components(state) and not visit_signal_this_turn(state):
                return _finish(ActionPlan(
                    action=Action.ASK_INFO,
                    handoff=False,
                    reason_code="document_received_ack",
                    reason="Acknowledge received document; remaining pack is still pending",
                ))
            if (
                state.intent in _VISIT_ELIGIBLE_INTENTS
                and not state.visit_invited
                and not isolated_document_unavailability(state)
                and not remaining_document_components(state)
            ):
                state.visit_invited = True
                return _finish(ActionPlan(
                    action=Action.REGISTER_VISIT_INTEREST,
                    handoff=False,
                    tool_calls=[{"tool": "register_visit_interest"}],
                    reason_code="document_pack_complete_visit",
                    reason="Acknowledge document without a concurrent remaining-doc ask",
                ))
        # After vendor notified: ack only. Fall through to visit/handoff close path.

    # Courtesy-only inbound must not reopen qualification questions.
    # If nothing useful remains to ask, keep the visit/handoff close path.
    if getattr(state, "courtesy_only", False) and not state.document_received:
        remaining = next_ask_field(state)
        if remaining and remaining not in (None, "intent"):
            return _finish(ActionPlan(
                action=Action.SMALLTALK,
                handoff=False,
                reason_code="courtesy",
                reason="Acknowledge thanks without reopening the roteiro",
            ))

    from sdr.domain.visual_resolution import visual_search_override

    visual_override = visual_search_override(state)
    if visual_override is not None:
        _block, ask, reason = visual_override
        if _block:
            return _finish(ActionPlan(
                action=Action.ASK_INFO,
                handoff=False,
                ask_field=ask,
                next_question=ask,
                reason_code=reason,
                reason="Visual identification is not a unique inventory match",
            ))

    # Inventory BEFORE triage handoff — respect preference and widened scope.
    if _needs_inventory_search(state):
        key = _state_search_key(state)
        ask = next_ask_field(state)
        follow = ask if ask and ask not in (None, "intent", "desired_model") else None
        return _finish(ActionPlan(
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
        ))

    # Explicit photo request of a vehicle already presented — execute, don't ask permission.
    # Never pick the first presented vehicle when primary is missing and several remain.
    if state.photo_request and state.last_shown_vehicle_ids:
        vehicle_id = state.primary_vehicle_id
        if not vehicle_id and len(state.last_shown_vehicle_ids) == 1:
            vehicle_id = state.last_shown_vehicle_ids[0]
        if vehicle_id:
            ask = next_ask_field(state)
            follow = ask if ask and ask not in (None, "intent") else None
            return _finish(ActionPlan(
                action=Action.SEND_PHOTOS,
                handoff=False,
                tool_calls=[{"tool": "send_photos", "vehicle_id": vehicle_id}],
                ask_field=follow,
                next_question=follow,
                reason_code="explicit_photo_request",
                reason="Send listing photos of the last presented vehicle",
            ))

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
        return _finish(ActionPlan(
            action=Action.ASK_INFO,
            handoff=False,
            ask_field="alternatives_ok",
            next_question="alternatives_ok",
            reason_code="installment_tight",
            reason="Desired installment is tight vs published cash price",
        ))

    # Budget known but no vehicle preference yet → alternatives by budget.
    if (
        state.intent in (BusinessIntent.PURCHASE, BusinessIntent.PURCHASE_FINANCING)
        and next_ask_field(state) == "desired_model"
        and state.budget_status == BudgetStatus.PROVIDED
        and state.facts.get("budget")
    ):
        key = _state_search_key(state)
        if key != state.last_inventory_search_key:
            return _finish(ActionPlan(
                action=Action.SHOW_OFFERS,
                handoff=False,
                tool_calls=[{"tool": "inventory_search", "_search_key": key}],
                reason_code="budget_without_model",
                reason="Show published alternatives for known budget",
            ))

    # Collect applicable fields before closing. Incomplete leads still hand off
    # on explicit signals (handled above) or once the minimum roteiro is done.
    ask = next_ask_field(state)
    if vendor_already_notified(state) and ask == "documents":
        if not should_ask_remaining_documents(state):
            ask = None
    if ask and ask != "intent":
        remaining_ask = ask == "documents" and should_ask_remaining_documents(state)
        if _has_unanswered_question() and (remaining_ask or ask == "documents"):
            return _answer_unanswered_question()
        if state.lifecycle.status == LifecycleStatus.BOT_ACTIVE:
            state.lifecycle.status = LifecycleStatus.QUALIFYING
        _mark_enrichment_ask(state, remaining=remaining_ask)
        return _finish(ActionPlan(
            action=Action.ASK_INFO,
            handoff=False,
            ask_field=ask,
            next_question=ask,
            reason_code="need_field",
            reason=f"Ask one field: {ask}",
        ))

    if is_handoff_ready(state) or is_seller_actionable(state):
        if _has_unanswered_question():
            return _answer_unanswered_question()
        from sdr.domain.visit import has_visit_preference, should_send_store_location

        if getattr(state, "needs_visit_slot_offer", False):
            state.visit_invited = True
            return _finish(ActionPlan(
                action=Action.REGISTER_VISIT_INTEREST,
                handoff=False,
                tool_calls=[{"tool": "register_visit_interest"}],
                reason_code="visit_invitation_pre_handoff",
                reason="Offer visit times that match the customer's day request",
            ))

        already_scheduled = (
            has_visit_preference(state)
            or state.visit_accepted_offered
            or state.visit_declined
        )
        if isolated_document_unavailability(state):
            already_scheduled = True
        if should_ask_remaining_documents(state) and not visit_signal_this_turn(state):
            already_scheduled = True
        if (
            state.intent in _VISIT_ELIGIBLE_INTENTS
            and not state.visit_invited
            and not already_scheduled
        ):
            state.visit_invited = True
            return _finish(ActionPlan(
                action=Action.REGISTER_VISIT_INTEREST,
                handoff=False,
                tool_calls=[{"tool": "register_visit_interest"}],
                reason_code="visit_invitation_pre_handoff",
                reason="Invite customer to visit store before handoff",
            ))
        if vendor_already_notified(state):
            return _finish(ActionPlan(
                action=Action.ASK_INFO,
                handoff=False,
                reason_code="post_handoff_continue",
                reason="Vendor already notified; continue without a second handoff",
            ))
        reason = "triage_actionable" if is_seller_actionable(state) else "handoff_ready"
        state.lifecycle.status = LifecycleStatus.READY_FOR_HANDOFF
        state.lifecycle.handoff_reason = reason
        state.business.actionability = Actionability.ACTIONABLE
        state.temperature = compute_temperature(state)
        tool_calls: list[dict] = []
        if (
            state.signals.visit_intent is True
            or has_visit_preference(state)
            or state.visit_accepted_offered
        ):
            tool_calls.append({"tool": "register_visit_interest"})
        if should_send_store_location(state):
            tool_calls.append({"tool": "send_location"})
        return _finish(ActionPlan(
            action=Action.HANDOFF_VENDOR,
            handoff=True,
            tool_calls=tool_calls,
            reason_code=reason,
            reason=HANDOFF_CONFIRMATION_PT_BR,
        ))

    if state.intent == BusinessIntent.SMALLTALK:
        return _finish(ActionPlan(
            action=Action.SMALLTALK,
            handoff=False,
            reason_code="greeting_or_chitchat",
            reason="Recognized as greeting or chitchat",
        ))

    return _finish(ActionPlan(
        action=Action.COMMERCIAL_UNKNOWN,
        handoff=False,
        reason_code="unresolved_intent",
        reason=(
            "Intent could not be resolved. "
            "Ask a focused clarifying question to progress without restarting."
        ),
    ))


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
