"""Deterministic merge of TurnFacts into ConversationCanonicalState."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
import re

from sdr.domain.budget_status import BUDGET_RESOLVED, BudgetStatus
from sdr.domain.document_status import (
    DOCUMENT_COMPONENTS,
    STATUS_RECEIVED,
    merge_document_status,
    parse_document_deferral,
)
from sdr.domain.engine_displacement import as_engine_list, engine_list_for_json
from sdr.domain.pending_interaction import (
    AlternativeScope,
    PendingInteraction,
    PendingResolution,
)
from sdr.domain.types import (
    CRITICAL_FACT_KEYS,
    INTENT_SPECIFICITY,
    INTENT_TO_BUSINESS_TYPE,
    BusinessIntent,
    ConversationCanonicalState,
    HandoffSignals,
    LifecycleStatus,
    TurnFacts,
)
from sdr.domain.vehicle_roles import (
    CUSTOMER_VEHICLE_KEY,
    DESIRED_VEHICLE_KEY,
    apply_desired_vehicle_substitution,
    canonicalize_vehicle_roles,
    merge_vehicle_dicts,
)
from sdr.domain.vendor_summary import is_placeholder_display_name

_UNKNOWN_TOKENS = frozenset({"unknown", "unk", "n/a", "na", "?"})


def _is_unknown(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip().lower() in _UNKNOWN_TOKENS:
        return True
    return False


def _norm_critical(value: Any) -> str:
    if value is None:
        return ""
    return "".join(ch for ch in str(value).strip().lower() if ch.isalnum())


def _prefer_intent(prev: BusinessIntent, incoming: BusinessIntent) -> BusinessIntent:
    prev_rank = INTENT_SPECIFICITY.get(prev, 0)
    new_rank = INTENT_SPECIFICITY.get(incoming, 0)
    if new_rank > prev_rank:
        return incoming
    if new_rank == prev_rank and incoming != BusinessIntent.UNKNOWN:
        return incoming
    return prev


def _merge_language(prev: str, incoming: str | None) -> str:
    if incoming is None or _is_unknown(incoming):
        return prev or "unknown"
    return incoming


def _merge_signal(prev: bool | None, incoming: bool | None, *, sticky_true: bool) -> bool | None:
    """unknown/omission never becomes false; sticky True for handoff signals."""
    if incoming is None:
        return prev
    if sticky_true and prev is True:
        return True
    return incoming


def _merge_signals(prev: HandoffSignals, incoming: HandoffSignals) -> HandoffSignals:
    return HandoffSignals(
        explicit_handoff=_merge_signal(
            prev.explicit_handoff, incoming.explicit_handoff, sticky_true=True
        ),
        explicit_offer=_merge_signal(
            prev.explicit_offer, incoming.explicit_offer, sticky_true=True
        ),
        visit_intent=_merge_signal(
            prev.visit_intent, incoming.visit_intent, sticky_true=True
        ),
        high_purchase_intent=_merge_signal(
            prev.high_purchase_intent,
            incoming.high_purchase_intent,
            sticky_true=True,
        ),
        sensitive_data_refusal=_merge_signal(
            prev.sensitive_data_refusal,
            incoming.sensitive_data_refusal,
            sticky_true=True,
        ),
    )


def _merge_facts(
    prev_facts: dict[str, Any],
    incoming: dict[str, Any],
    explicit_corrections: list[str],
    pending: list[str],
    inbound_text: str = "",
) -> tuple[dict[str, Any], list[str]]:
    merged = deepcopy(prev_facts)
    pending_out = list(pending)
    corrections = {c.strip() for c in explicit_corrections if c and c.strip()}

    for key, raw_value in incoming.items():
        if key.startswith("_"):
            continue
        if _is_unknown(raw_value):
            # Omission / unknown must not delete or falsify known data.
            continue

        if key in (DESIRED_VEHICLE_KEY, CUSTOMER_VEHICLE_KEY) and isinstance(raw_value, dict):
            prev_vehicle = merged.get(key) if isinstance(merged.get(key), dict) else {}
            if key == DESIRED_VEHICLE_KEY:
                from sdr.domain.vehicle_roles import desired_identity_changed, substitute_desired_vehicle

                if desired_identity_changed(prev_vehicle, raw_value.get("model")):
                    merged[key] = substitute_desired_vehicle(prev_vehicle, raw_value, inbound_text)
                    continue
            merged[key] = merge_vehicle_dicts(prev_vehicle, raw_value)
            continue

        prev_value = merged.get(key)
        if prev_value is None or _is_unknown(prev_value):
            merged[key] = raw_value
            continue

        if key in CRITICAL_FACT_KEYS:
            if _norm_critical(prev_value) == _norm_critical(raw_value):
                merged[key] = raw_value
                continue
            if key in corrections:
                merged[key] = raw_value
                if key in pending_out:
                    pending_out.remove(key)
                continue
            # Conflict: keep previous, flag confirmation — never silent overwrite.
            if key not in pending_out:
                pending_out.append(key)
            continue

        # Non-critical: explicit new value overwrites (including corrections).
        # Never delete desired_model by omission — only overwrite with a new value.
        merged[key] = raw_value

    return merged, pending_out


def _merge_budget_status(
    prev: BudgetStatus,
    incoming: BudgetStatus | None,
    facts: dict[str, Any],
) -> BudgetStatus:
    """Apply typed budget status; numeric budget implies PROVIDED when explicit."""
    if incoming is not None:
        return incoming
    # Infer PROVIDED only when a new numeric budget is present and status was UNKNOWN.
    if prev == BudgetStatus.UNKNOWN and facts.get("budget") is not None:
        return BudgetStatus.PROVIDED
    # Later numeric budget upgrades UNDEFINED/DECLINED/FLEXIBLE → PROVIDED.
    if incoming is None and facts.get("budget") is not None and prev in (
        BudgetStatus.UNDEFINED,
        BudgetStatus.DECLINED,
        BudgetStatus.FLEXIBLE,
        BudgetStatus.UNKNOWN,
    ):
        # Only upgrade when facts just received a budget this turn — handled via
        # incoming status or when prev was UNKNOWN. For UNDEFINED→PROVIDED the
        # extractor must set budget_status=PROVIDED with the value.
        if prev == BudgetStatus.UNKNOWN:
            return BudgetStatus.PROVIDED
    return prev


def _apply_pending_and_scope(
    state: ConversationCanonicalState,
    facts: TurnFacts,
) -> None:
    """Consume pending_interaction and apply alternative_scope from TurnFacts.

    LLM interprets meaning; code owns transitions.
    Original desired_model is never cleared here.
    """
    pending = state.pending_interaction

    # Explicit scope from customer (e.g. "qualquer opção de carro") always applies.
    if facts.alternative_scope is not None:
        state.alternative_scope = facts.alternative_scope
        # Explicit scope widening consumes a pending alternatives offer.
        if pending == PendingInteraction.OFFER_ALTERNATIVES and facts.alternative_scope in (
            AlternativeScope.SIMILAR,
            AlternativeScope.ANY_VEHICLE,
        ):
            state.pending_interaction = PendingInteraction.NONE
            return

    resolution = facts.pending_resolution

    if pending == PendingInteraction.NONE:
        # No pending affordance — ignore stray resolution.
        return

    if pending == PendingInteraction.OFFER_ALTERNATIVES:
        if resolution == PendingResolution.ACCEPT:
            # Default to SIMILAR unless caller already set ANY_VEHICLE this turn.
            if facts.alternative_scope is None and state.alternative_scope == AlternativeScope.NONE:
                state.alternative_scope = AlternativeScope.SIMILAR
            state.pending_interaction = PendingInteraction.NONE
            if state.installment_capacity is not None:
                state.facts["budget"] = state.installment_capacity
                state.facts["max_price"] = state.installment_capacity
                state.budget_status = BudgetStatus.PROVIDED
            return
        if resolution == PendingResolution.REJECT:
            state.pending_interaction = PendingInteraction.NONE
            return
        if resolution == PendingResolution.AMBIGUOUS:
            # Keep pending — Decision will ask for clarification.
            return
        # No resolution provided while pending remains → Decision clarifies.
        return


def _apply_document_deferral(state: ConversationCanonicalState, inbound_text: str) -> None:
    deferred = list(state.deferred_fields or [])
    status = merge_document_status(state.facts.get("document_status"), None)
    parsed = parse_document_deferral(inbound_text)

    def _add(*names: str) -> None:
        nonlocal deferred
        for name in names:
            if status.get(name) == STATUS_RECEIVED:
                continue
            if name not in deferred:
                deferred.append(name)
            status[name] = "deferred"

    if parsed:
        for name, value in parsed.items():
            if value == "deferred":
                _add(name)
        state.facts["documents_deferred"] = True
        state.facts["document_status"] = status
        state.documents_asked = True
    elif state.facts.get("documents_deferred") is True:
        # LLM flagged deferral without a parseable utterance — unspecified pack.
        if not any(status.get(k) == "deferred" for k in DOCUMENT_COMPONENTS):
            _add(*DOCUMENT_COMPONENTS)
        state.facts["document_status"] = status
        state.documents_asked = True
    state.deferred_fields = deferred
    collected = [c for c in (state.collected_fields or []) if c not in deferred]
    if "documents" in deferred or any(c in deferred for c in DOCUMENT_COMPONENTS):
        collected = [c for c in collected if c != "documents"]
    state.collected_fields = collected


def _bump_lifecycle(state: ConversationCanonicalState) -> None:
    """Advance bot lifecycle without touching irreversible human states."""
    status = state.lifecycle.status
    if status in (
        LifecycleStatus.HANDOFF_SENT,
        LifecycleStatus.HUMAN_ACTIVE,
        LifecycleStatus.HUMAN_CLOSED,
        LifecycleStatus.READY_FOR_HANDOFF,
        LifecycleStatus.AI_RESUMED,
    ):
        return

    commercial = state.intent not in (
        BusinessIntent.UNKNOWN,
        BusinessIntent.SMALLTALK,
    )
    signals = state.signals
    handoff_now = any(
        (
            signals.explicit_handoff is True,
            signals.explicit_offer is True,
            signals.high_purchase_intent is True,
            signals.visit_intent is True,
        )
    )

    if handoff_now:
        state.lifecycle.status = LifecycleStatus.READY_FOR_HANDOFF
        return
    if commercial and status == LifecycleStatus.BOT_ACTIVE:
        state.lifecycle.status = LifecycleStatus.QUALIFYING


def deterministic_merge(
    prev: ConversationCanonicalState,
    facts: TurnFacts,
    inbound_text: str = "",
) -> ConversationCanonicalState:
    """Merge turn facts into prior state.

    Invariants:
    - omission never deletes known fields
    - unknown != false for booleans/signals
    - explicit correction overwrites
    - critical conflicts (cpf/birth/plate) set pending_confirmation
    - prefer more specific commercial intent
    - pending_interaction transitions are code-owned
    """
    state = ConversationCanonicalState(
        thread_id=prev.thread_id,
        customer=deepcopy(prev.customer),
        business=deepcopy(prev.business),
        lifecycle=deepcopy(prev.lifecycle),
        language=prev.language,
        intent=prev.intent,
        facts=deepcopy(prev.facts),
        signals=deepcopy(prev.signals),
        pending_confirmation=list(prev.pending_confirmation),
        temperature=prev.temperature,
        active_lead_ids=list(prev.active_lead_ids),
        assistant_turn_count=prev.assistant_turn_count,
        last_inventory_search_key=prev.last_inventory_search_key,
        last_inventory_outcome=prev.last_inventory_outcome,
        pending_interaction=prev.pending_interaction,
        alternative_scope=prev.alternative_scope,
        budget_status=prev.budget_status,
        last_shown_vehicle_ids=list(prev.last_shown_vehicle_ids),
        primary_vehicle_id=prev.primary_vehicle_id,
        primary_vehicle_chosen_at=prev.primary_vehicle_chosen_at,
        presented_vehicle_bindings=list(prev.presented_vehicle_bindings or []),
        current_offer_set_id=prev.current_offer_set_id,
        photo_request=False,
        location_request=False,
        document_received=False,
        pending_question=prev.pending_question,
        engagement_low_streak=prev.engagement_low_streak,
        visit_invited=prev.visit_invited,
        visit_preferred_time=prev.visit_preferred_time,
        visit_interest=prev.visit_interest,
        visit_declined=prev.visit_declined,
        visit_date=prev.visit_date,
        visit_period=prev.visit_period,
        visit_time=prev.visit_time,
        visit_raw=prev.visit_raw,
        visit_within_hours=prev.visit_within_hours,
        visit_accepted_offered=prev.visit_accepted_offered,
        location_sent=prev.location_sent,
        visit_courtesy=False,
        visit_declined_this_turn=False,
        needs_visit_slot_offer=False,
        courtesy_only=False,
        unanswered_questions=[],
        visual_applied_this_turn=False,
        documents_asked=prev.documents_asked,
        remaining_documents_asked=bool(getattr(prev, "remaining_documents_asked", False)),
        enrichment_ask_count=int(getattr(prev, "enrichment_ask_count", 0) or 0),
        presented_vehicle_catalog=dict(getattr(prev, "presented_vehicle_catalog", None) or {}),
        installment_asked=prev.installment_asked,
        installment_mismatch_offered=prev.installment_mismatch_offered,
        installment_capacity=prev.installment_capacity,
        last_shown_price_cash=prev.last_shown_price_cash,
        deferred_fields=list(prev.deferred_fields),
        offered_visit_slots=list(prev.offered_visit_slots),
        listing_reference=prev.listing_reference,
        last_inventory_match=deepcopy(prev.last_inventory_match) if prev.last_inventory_match else None,
        last_visual_resolution=deepcopy(prev.last_visual_resolution)
        if getattr(prev, "last_visual_resolution", None)
        else None,
        crm_revision=int(getattr(prev, "crm_revision", 0) or 0),
        ownership_revision=int(getattr(prev, "ownership_revision", 0) or 0),
        assumed_by_user_id=getattr(prev, "assumed_by_user_id", None),
        assumed_at=getattr(prev, "assumed_at", None),
        resumed_by_user_id=getattr(prev, "resumed_by_user_id", None),
        resumed_at=getattr(prev, "resumed_at", None),
        resume_reason=getattr(prev, "resume_reason", None),
        handoff_at=getattr(prev, "handoff_at", None),
        vendor_notified_at=getattr(prev, "vendor_notified_at", None),
        handoff_ready=prev.handoff_ready,
        profile_complete=prev.profile_complete,
        missing_fields=list(prev.missing_fields),
        collected_fields=list(prev.collected_fields),
    )

    state.language = _merge_language(state.language, facts.language)
    state.intent = _prefer_intent(state.intent, facts.intent)
    state.business.type = INTENT_TO_BUSINESS_TYPE.get(
        state.intent, state.business.type
    )

    # Customer name from facts when present. Placeholders are not real names.
    if not _is_unknown(facts.facts.get("name")):
        incoming = str(facts.facts.get("name") or "").strip()
        if incoming and not is_placeholder_display_name(incoming):
            current = (state.customer.name or "").strip()
            current_is_placeholder = is_placeholder_display_name(current)
            if (
                current
                and not current_is_placeholder
                and state.customer.name_confirmed
                and incoming != current
                and "name" not in facts.explicit_corrections
            ):
                if "name" not in state.pending_confirmation:
                    state.pending_confirmation.append("name")
            else:
                state.customer.name = incoming
                if "name" in facts.explicit_corrections:
                    state.customer.name_confirmed = True

    if facts.facts.get("name_confirmed") is True:
        state.customer.name_confirmed = True

    state.facts, state.pending_confirmation = _merge_facts(
        state.facts,
        facts.facts,
        facts.explicit_corrections,
        state.pending_confirmation,
        inbound_text=inbound_text,
    )
    state.facts = canonicalize_vehicle_roles(state.facts, state.intent)
    state.facts = apply_desired_vehicle_substitution(
        state.facts,
        prev.facts,
        facts.facts,
        inbound_text,
    )
    state.facts = canonicalize_vehicle_roles(state.facts, state.intent)
    _apply_document_deferral(state, inbound_text)
    if state.facts.get("documents_deferred") is True:
        state.documents_asked = True
    if state.facts.get("payment_method") == "financing" and state.intent == BusinessIntent.PURCHASE:
        state.intent = BusinessIntent.PURCHASE_FINANCING
        state.business.type = INTENT_TO_BUSINESS_TYPE[BusinessIntent.PURCHASE_FINANCING]
    if (
        state.facts.get("payment_method") in {"cash", "a_vista"}
        and state.intent == BusinessIntent.PURCHASE_FINANCING
    ):
        state.intent = BusinessIntent.PURCHASE
        state.business.type = INTENT_TO_BUSINESS_TYPE[BusinessIntent.PURCHASE]
    if facts.facts.get("desired_engine_any") is True:
        state.facts.pop("desired_engine_displacement_liters", None)
        state.facts["desired_engine_any"] = True
        state.facts.pop("desired_engine_flexible", None)
    elif facts.facts.get("desired_engine_flexible") is True:
        prev_engines = as_engine_list(prev.facts.get("desired_engine_displacement_liters"))
        new_engines = as_engine_list(state.facts.get("desired_engine_displacement_liters"))
        unioned = engine_list_for_json(prev_engines + new_engines)
        if unioned is not None:
            state.facts["desired_engine_displacement_liters"] = unioned
        state.facts["desired_engine_flexible"] = True
        state.facts.pop("desired_engine_any", None)
    elif as_engine_list(facts.facts.get("desired_engine_displacement_liters")):
        # Explicit engine this turn without "também" / "qualquer" → replace, do not union.
        state.facts.pop("desired_engine_flexible", None)
        state.facts.pop("desired_engine_any", None)
    state.signals = _merge_signals(state.signals, facts.signals)

    # Budget status: explicit TurnFacts wins; numeric budget upgrades UNKNOWN.
    if facts.budget_status is not None:
        state.budget_status = facts.budget_status
    elif state.budget_status == BudgetStatus.UNKNOWN and state.facts.get("budget") is not None:
        state.budget_status = BudgetStatus.PROVIDED
    elif (
        facts.facts.get("budget") is not None
        and facts.budget_status is None
        and state.budget_status in BUDGET_RESOLVED
        and state.budget_status != BudgetStatus.PROVIDED
    ):
        # Later explicit numeric value after UNDEFINED/DECLINED/FLEXIBLE → PROVIDED.
        state.budget_status = BudgetStatus.PROVIDED

    # Photo / location requests are turn-scoped protocol; omission never invents True.
    if facts.photo_request is True:
        state.photo_request = True
    if facts.location_request is True:
        state.location_request = True

    _apply_pending_and_scope(state, facts)
    _bump_lifecycle(state)
    return state
