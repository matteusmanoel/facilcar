"""Turn processing use-case — injectable understanding + tool executor for testability.

Pipeline:
  InboundTurn → understand → merge → decide → execute tools → compose → validate → outbound

Inventory truth:
  ToolResult.outcome drives ResponseDirective.inventory_outcome.
  Composer may phrase naturally; it must not decide stock emptiness from errors.
  Validator rejects absence claims on failure outcomes and falls back safely.

Conversational affordances:
  Composer may offer alternatives only when ResponseDirective.conversational_affordance
  is set; process_turn then records pending_interaction for Decision continuation.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

import asyncpg

logger = logging.getLogger(__name__)

from sdr.application.inbound_document import document_kind_from_inbound
from sdr.application.tool_executor import execute_tool_calls, tool_results_to_context
from sdr.domain.decision import decide, inventory_search_key
from sdr.domain.document_storage import apply_commercial_document_receipt
from sdr.domain.handoff import (
    compute_temperature,
    is_ai_silenced,
    mark_handoff_sent,
)
from sdr.domain.inbound import InboundTurn, MediaStatus, inbound_from_text_compat
from sdr.domain.introduction import (
    continuation_smalltalk_bubbles,
    introduction_smalltalk_bubbles,
    response_objective_for,
)
from sdr.domain.inventory_outcome import (
    claims_for_inventory_outcome,
    extract_inventory_outcome,
    inventory_fallback_bubbles,
    is_semantic_inventory_success,
)
from sdr.domain.merge import deterministic_merge
from sdr.domain.pending_interaction import PendingInteraction
from sdr.domain.vehicle_presentation import (
    OutboundMedia,
    media_items_from_images,
    media_items_from_vehicles,
    format_vehicle_caption,
    shown_vehicle_ids,
)
from sdr.domain.types import (
    Action,
    ActionPlan,
    ConversationCanonicalState,
    InventoryOutcome,
    LeadTemperature,
    ResponseDirective,
    TurnFacts,
)


class UnderstandingFn(Protocol):
    async def __call__(
        self,
        text: str,
        state: ConversationCanonicalState,
    ) -> TurnFacts: ...


@dataclass(slots=True)
class ProcessTurnResult:
    action_plan: ActionPlan
    state: ConversationCanonicalState
    outbound_texts: list[str]
    turn_facts: TurnFacts
    tool_results: list[dict[str, Any]]
    validator_result: dict[str, Any] | None = None
    response_directive: ResponseDirective | None = None
    outbound_media: list[OutboundMedia] = field(default_factory=list)
    outbound_location: dict[str, Any] | None = None
    question_adherence: dict[str, Any] | None = None
    composer_retries: int = 0
    questions_rejected: int = 0


def _track_engagement(
    merged: ConversationCanonicalState,
    inbound_text: str,
    turn_facts: TurnFacts,
) -> None:
    """Update engagement_low_streak based on current turn quality."""
    word_count = len(inbound_text.strip().split()) if inbound_text.strip() else 0
    has_new_facts = bool(turn_facts.facts)
    if word_count <= 3 and not has_new_facts:
        merged.engagement_low_streak = merged.engagement_low_streak + 1
    else:
        merged.engagement_low_streak = 0


def _is_sandbox() -> bool:
    from sdr.config import get_settings

    return get_settings().sdr_environment != "production"


def _ack_kind_from_facts(
    facts: TurnFacts,
    pending_question: str | None,
) -> str | None:
    """Which field was just answered — Composer owns the wording."""
    collected = facts.facts or {}
    applies = collected.get("payment_applies_to")
    method = collected.get("payment_method")
    if applies == "difference" and method == "financing":
        return "difference_financing"
    if applies == "difference" and method in {"cash", "a_vista"}:
        return "difference_cash"

    def _from_collected() -> str | None:
        if "desired_installment" in collected:
            return "desired_installment"
        if "down_payment" in collected:
            return "down_payment"
        payment = collected.get("payment_method")
        if payment == "financing":
            return "payment_financing"
        if payment in {"cash", "a_vista"}:
            return "payment_cash"
        deal = collected.get("deal_type")
        if deal == "purchase":
            return "deal_purchase"
        if deal == "trade":
            return "deal_trade"
        return None

    if not pending_question:
        return _from_collected()
    if pending_question == "down_payment" and "down_payment" in collected:
        return "down_payment"
    if pending_question == "desired_installment" and "desired_installment" in collected:
        return "desired_installment"
    if pending_question == "payment_method":
        payment = collected.get("payment_method")
        if payment == "financing":
            return "payment_financing"
        if payment in {"cash", "a_vista"}:
            return "payment_cash"
        return None
    if pending_question == "deal_type":
        deal = collected.get("deal_type")
        if deal == "purchase":
            return "deal_purchase"
        if deal == "trade":
            return "deal_trade"
        return None
    return _from_collected()


def _visit_cta_style(merged: ConversationCanonicalState) -> str:
    """HOT gets a concrete day/time ask; WARM/COLD get a low-pressure invite.

    Always recompute temperature — a stale WARM on state must not hide that
    the lead is now seller-actionable (vehicle + docs).
    """
    temp = compute_temperature(merged)
    if temp == LeadTemperature.HOT:
        return "hot_ask_slot"
    return "warm_invite"


def _location_pin_from_tools(tool_results: list[dict[str, Any]]) -> dict[str, Any] | None:
    for result in tool_results:
        if result.get("tool") != "send_location":
            continue
        pin = result.get("pin")
        if isinstance(pin, dict) and pin.get("latitude") is not None and pin.get("longitude") is not None:
            return pin
    return None


def _should_silence_tool_failure(
    plan: ActionPlan,
    tool_results: list[dict[str, Any]],
) -> bool:
    """Production: do not tell the customer that a tool failed — stay silent."""
    if _is_sandbox():
        return False
    if plan.action == Action.SEND_LOCATION:
        # Visit CTA does not depend on pin/address; only silence a hard miss.
        loc = next((r for r in tool_results if r.get("tool") == "send_location"), None)
        return loc is None
    if plan.action == Action.SHOW_OFFERS:
        outcome = extract_inventory_outcome(tool_results)
        return outcome in (
            InventoryOutcome.FAILED_RETRYABLE,
            InventoryOutcome.FAILED_TERMINAL,
        )
    return False


def _availability_status_for_directive(
    merged: ConversationCanonicalState,
    inventory_outcome: InventoryOutcome,
    inv_count: int,
    tool_results: list[dict[str, Any]] | None = None,
) -> str:
    from sdr.domain.visual_resolution import VisualVehicleResolution, availability_status_for

    vis = None
    if merged.last_visual_resolution:
        vis = VisualVehicleResolution.from_mapping(merged.last_visual_resolution)
    match = merged.last_inventory_match if isinstance(merged.last_inventory_match, dict) else {}
    catalog = (merged.facts or {}).get("matched_catalog_status") or match.get("matched_status")
    for result in tool_results or []:
        if result.get("tool") != "inventory_search":
            continue
        params = result.get("search_params") or {}
        catalog = catalog or params.get("matched_status")
        vehicles = result.get("vehicles") or []
        first = vehicles[0] if vehicles and isinstance(vehicles[0], dict) else {}
        catalog = catalog or first.get("status")
    return availability_status_for(
        resolution=vis,
        inventory_outcome=(
            inventory_outcome.value if hasattr(inventory_outcome, "value") else str(inventory_outcome)
        ),
        inventory_count=inv_count,
        catalog_status=str(catalog) if catalog else None,
    )


def _build_response_directive(
    merged: ConversationCanonicalState,
    plan: ActionPlan,
    tool_results: list[dict[str, Any]],
    inbound_text: str = "",
    inbound_content_type: str = "TEXT",
    turn_facts: TurnFacts | None = None,
    prev_pending_question: str | None = None,
    inbound: InboundTurn | None = None,
    prev_primary_vehicle_id: str | None = None,
) -> ResponseDirective:
    """Build ResponseDirective — single source of truth for Composer inputs."""
    should_introduce = merged.assistant_turn_count == 0

    # intro_style: BRIEF when intent was already clear on first turn (not a pure greeting).
    intro_style = "FULL"
    if should_introduce and merged.intent.value not in ("unknown", "smalltalk"):
        intro_style = "BRIEF"

    engagement_low = merged.engagement_low_streak >= 2

    objective = response_objective_for(
        action=plan.action, should_introduce=should_introduce
    )
    if merged.last_shown_vehicle_ids:
        shown = merged.facts.get("desired_model") or merged.facts.get("desired_vehicle_text")
        label = str(shown).strip() if isinstance(shown, str) and shown.strip() else "o veículo já apresentado"
        objective += (
            f" O cliente já viu {label} neste atendimento. "
            "NÃO pergunte modelo, ano ou o que está buscando. "
            "Trate o veículo mostrado como o interesse atual, salvo pedido explícito de outro."
        )
    if (prev_pending_question == "visit" or merged.pending_question == "visit") and plan.action != Action.HANDOFF_VENDOR:
        objective += (
            " O tema deste turno é o convite de visita — peça dia/horário se ainda faltar. "
            "Não reabra o roteiro de financiamento nem a busca de estoque."
        )

    lang = merged.language
    if not lang or lang == "unknown":
        lang = "pt-BR"

    _SENSITIVE = {"cpf", "birth_date", "birth", "cnpj", "plate"}
    facts_context = {
        k: v for k, v in merged.facts.items()
        if k not in _SENSITIVE and not k.startswith("_")
    }

    inventory_outcome = extract_inventory_outcome(tool_results)
    allowed, forbidden = claims_for_inventory_outcome(inventory_outcome)

    # SUCCESS_EMPTY asks for other models directly — no yes/no alternatives gate.
    affordance = PendingInteraction.NONE
    allowed = [c for c in allowed if c != "ask_if_alternatives_acceptable"]

    claims_forbidden = [
        "approval_guarantee",
        "rate_promise",
        "price_guarantee",
        "assert_engine_from_title",
        "ask_budget",
        *forbidden,
    ]
    if merged.lifecycle.status.value == "HUMAN_ACTIVE":
        claims_forbidden.append("any_response")
    if merged.last_shown_vehicle_ids:
        claims_forbidden.append("reask_shown_vehicle")

    # When scope is widened, forbid treating original model as rigid requirement.
    if merged.alternative_scope.value != "NONE":
        claims_forbidden.append("treat_original_model_as_hard_requirement")

    tool_ctx = tool_results_to_context(tool_results)
    inv_count = 0
    alternatives: list[dict[str, Any]] = []
    for r in tool_results:
        if r.get("tool") == "inventory_search":
            inv_count = int(r.get("count") or 0)
            alternatives = list(r.get("alternatives") or r.get("vehicles") or [])[:3]

    original_model = merged.facts.get("desired_model")
    if not isinstance(original_model, str):
        original_model = None

    if inbound_content_type == "DOCUMENT":
        ack_kind = "document_received"
    elif turn_facts:
        ack_kind = _ack_kind_from_facts(turn_facts, prev_pending_question)
    else:
        ack_kind = None

    visit_cta = None
    if plan.action == Action.SEND_LOCATION:
        visit_cta = "location_close"
    elif plan.action == Action.REGISTER_VISIT_INTEREST:
        visit_cta = _visit_cta_style(merged)

    document_kind = (
        document_kind_from_inbound(inbound)
        if inbound_content_type == "DOCUMENT" and inbound is not None
        else None
    )

    from sdr.domain.cadence import cadence_for
    from sdr.domain.dialogue_plan import build_dialogue_plan, dialogue_objective_suffix

    cadence_mode = cadence_for(
        action=plan.action,
        should_introduce=should_introduce,
        ack_kind=ack_kind,
        reason_code=plan.reason_code,
    )

    if plan.reason_code == "installment_tight":
        affordance = PendingInteraction.OFFER_ALTERNATIVES
        if "ask_if_alternatives_acceptable" not in allowed:
            allowed = [*allowed, "ask_if_alternatives_acceptable"]

    dialogue = build_dialogue_plan(
        inbound_text=inbound_text,
        action=plan.action,
        ask_field=plan.ask_field or plan.next_question,
        intent=merged.intent,
        should_introduce=should_introduce,
        assistant_turn_count=merged.assistant_turn_count,
        ack_kind=ack_kind,
        inbound_content_type=inbound_content_type,
        facts_context=facts_context,
        turn_facts=turn_facts,
        state=merged,
        reason_code=plan.reason_code,
        visit_cta_style=visit_cta,
        document_kind=document_kind,
        lifecycle_status=merged.lifecycle.status.value,
        vehicle_chosen_this_turn=bool(
            merged.primary_vehicle_id
            and merged.primary_vehicle_id != prev_primary_vehicle_id
        ),
        availability_status=_availability_status_for_directive(
            merged, inventory_outcome, inv_count, tool_results
        ),
    )
    suffix = dialogue_objective_suffix(dialogue)
    if suffix:
        objective = f"{objective} {suffix}".strip()

    return ResponseDirective(
        action=plan.action,
        reason_code=plan.reason_code,
        should_introduce=should_introduce,
        inbound_text=inbound_text,
        response_objective=objective,
        intent=merged.intent,
        customer_name=(
            merged.customer.name
            or (
                str(facts_context["name"]).strip()
                if isinstance(facts_context.get("name"), str) and str(facts_context["name"]).strip()
                else None
            )
        ),
        language=lang,
        next_question=plan.next_question or plan.ask_field,
        tool_results=tool_ctx,
        facts_context=facts_context,
        lifecycle_status=merged.lifecycle.status.value,
        claims_forbidden=claims_forbidden,
        inventory_outcome=inventory_outcome,
        claims_allowed=allowed,
        inventory_count=inv_count,
        inventory_alternatives=alternatives,
        conversational_affordance=affordance,
        alternative_scope=merged.alternative_scope,
        budget_status=merged.budget_status,
        original_desired_model=original_model,
        intro_style=intro_style,
        engagement_low=engagement_low,
        inbound_content_type=inbound_content_type,
        ack_kind=ack_kind,
        cadence_mode=cadence_mode.value,
        visit_cta_style=visit_cta,
        document_kind=document_kind,
        expose_errors=_is_sandbox(),
        dialogue_plan=dialogue.to_dict(),
    )


def _directive_to_state_and_plan_maps(
    directive: ResponseDirective,
    plan: ActionPlan,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    state_map: dict[str, Any] = {
        "language": directive.language,
        "should_introduce": directive.should_introduce,
        "intro_style": directive.intro_style,
        "engagement_low": directive.engagement_low,
        "inbound_content_type": directive.inbound_content_type,
        "ack_kind": directive.ack_kind,
        "cadence_mode": directive.cadence_mode,
        "visit_cta_style": directive.visit_cta_style,
        "document_kind": directive.document_kind,
        "inbound_text": directive.inbound_text,
        "dialogue_plan": dict(directive.dialogue_plan or {}),
        "response_objective": directive.response_objective,
        "intent": directive.intent.value,
        "customer_name": directive.customer_name,
        "facts": directive.facts_context,
        "lifecycle_status": directive.lifecycle_status,
        "claims_forbidden": directive.claims_forbidden,
        "claims_allowed": directive.claims_allowed,
        "inventory_outcome": directive.inventory_outcome.value,
        "inventory_count": directive.inventory_count,
        "missing_fields": [plan.ask_field] if plan.ask_field else [],
        "conversational_affordance": directive.conversational_affordance.value,
        "alternative_scope": directive.alternative_scope.value,
        "budget_status": directive.budget_status.value,
        "original_desired_model": directive.original_desired_model,
        "offered_visit_slots": list(getattr(directive, "offered_visit_slots", None) or []),
        "visit_preferred_time": getattr(directive, "visit_preferred_time", None),
        "handoff_ready": bool(getattr(directive, "handoff_ready", False)),
        "profile_complete": bool(getattr(directive, "profile_complete", False)),
        "deferred_fields": list(getattr(directive, "deferred_fields", None) or []),
        "collected_fields": list(getattr(directive, "collected_fields", None) or []),
    }
    plan_map: dict[str, Any] = {
        "action": plan.action.value,
        "handoff": plan.handoff,
        "tool_calls": plan.tool_calls,
        "next_question": directive.next_question,
        "reason_code": plan.reason_code,
    }
    tool_ctx = dict(directive.tool_results) if directive.tool_results else {}
    tool_ctx["inventory_outcome"] = directive.inventory_outcome.value
    tool_ctx["inventory_count"] = directive.inventory_count
    if directive.inventory_alternatives:
        tool_ctx["alternatives"] = directive.inventory_alternatives
    tool_ctx["conversational_affordance"] = directive.conversational_affordance.value
    tool_ctx["alternative_scope"] = directive.alternative_scope.value
    tool_ctx["budget_status"] = directive.budget_status.value
    return state_map, plan_map, tool_ctx or None


def _update_inventory_search_key(
    merged: ConversationCanonicalState,
    plan: ActionPlan,
    tool_results: list[dict[str, Any]],
) -> None:
    """Update search key only on semantic success (FOUND or EMPTY).

    After vehicles are recorded on the state, the key must include
    ``last_shown_vehicle_ids`` so the next turn's continuity hash matches.
    """
    outcome = extract_inventory_outcome(tool_results)
    if not is_semantic_inventory_success(outcome):
        return
    merged.last_inventory_search_key = inventory_search_key(
        merged.facts,
        alternative_scope=merged.alternative_scope,
        budget_status=merged.budget_status,
        last_shown_vehicle_ids=merged.last_shown_vehicle_ids or [],
    )
    merged.last_inventory_outcome = outcome.value


def _record_inventory_match(
    merged: ConversationCanonicalState,
    tool_results: list[dict[str, Any]],
) -> None:
    """Persist listing identity + outcome for SUCCESS_SOLD auditability."""
    for result in tool_results:
        if result.get("tool") != "inventory_search":
            continue
        vehicles = result.get("vehicles") or []
        first = vehicles[0] if vehicles and isinstance(vehicles[0], dict) else {}
        matched_id = (
            result.get("matched_inventory_id")
            or result.get("listing_id")
            or first.get("id")
        )
        merged.last_inventory_match = {
            "listing_reference_received": result.get("listing_reference_received")
            or merged.listing_reference,
            "listing_reference_resolved": result.get("listing_reference_resolved")
            or matched_id,
            "matched_inventory_id": matched_id,
            "matched_status": result.get("matched_status") or first.get("status"),
            "inventory_outcome": result.get("outcome") or result.get("inventory_outcome"),
        }
        return


def _apply_pending_after_offers(
    merged: ConversationCanonicalState,
    directive: ResponseDirective,
) -> None:
    """Record pending affordance when Composer was authorized to offer alternatives."""
    if directive.conversational_affordance == PendingInteraction.OFFER_ALTERNATIVES:
        merged.pending_interaction = PendingInteraction.OFFER_ALTERNATIVES


def _record_shown_vehicles(
    merged: ConversationCanonicalState,
    tool_results: list[dict[str, Any]],
) -> None:
    """Persist last presented published vehicle ids after a semantic inventory hit."""
    from sdr.domain.inventory_outcome import extract_inventory_outcome

    if extract_inventory_outcome(tool_results) != InventoryOutcome.SUCCESS_FOUND:
        return
    for result in tool_results:
        if result.get("tool") != "inventory_search":
            continue
        vehicles = result.get("vehicles") or []
        ids = shown_vehicle_ids(vehicles)
        if ids:
            merged.last_shown_vehicle_ids = ids
            merged.current_offer_set_id = str(uuid.uuid4())
            primary = merged.primary_vehicle_id
            if primary and primary not in ids:
                merged.primary_vehicle_id = None
                merged.primary_vehicle_chosen_at = None
        if vehicles:
            from sdr.domain.vehicle_catalog import register_catalog_vehicles

            catalog: dict[str, dict[str, Any]] = dict(getattr(merged, "presented_vehicle_catalog", None) or {})
            snapshots: list[dict[str, Any]] = []
            for item in vehicles:
                if not isinstance(item, dict):
                    continue
                vid = str(item.get("id") or "").strip()
                if not vid:
                    continue
                snap = {
                    "id": vid,
                    "brand": item.get("brand") or item.get("brand_name") or item.get("brandName"),
                    "model": item.get("model"),
                    "version": item.get("version"),
                    "year": item.get("year") or item.get("year_model") or item.get("yearModel"),
                    "title": item.get("title"),
                }
                catalog[vid] = snap
                snapshots.append(snap)
            merged.presented_vehicle_catalog = catalog
            if snapshots:
                register_catalog_vehicles(snapshots)
            first = vehicles[0] if isinstance(vehicles[0], dict) else {}
            price = first.get("priceCash") if isinstance(first, dict) else None
            if price is None and isinstance(first, dict):
                price = first.get("price_cash")
            try:
                merged.last_shown_price_cash = float(price) if price is not None else None
            except (TypeError, ValueError):
                pass
        return


def _outbound_media_from_tools(
    plan: ActionPlan,
    tool_results: list[dict[str, Any]],
    *,
    language: str,
) -> list[OutboundMedia]:
    """Build WhatsApp image items from executed tools. Caption goes on the last photo."""
    if plan.action == Action.SEND_PHOTOS:
        for result in tool_results:
            if result.get("tool") != "send_photos":
                continue
            vehicle = result.get("vehicle") or {}
            images = result.get("images") or []
            if not images:
                return []
            caption = format_vehicle_caption(vehicle, language=language) if vehicle else ""
            vid = str(result.get("vehicle_id") or vehicle.get("id") or "") or None
            return media_items_from_images(
                images,
                caption=caption,
                vehicle_id=vid,
            )
        return []

    if plan.action != Action.SHOW_OFFERS:
        return []
    for result in tool_results:
        if result.get("tool") != "inventory_search":
            continue
        if result.get("outcome") != InventoryOutcome.SUCCESS_FOUND.value:
            return []
        vehicles = result.get("vehicles") or []
        return media_items_from_vehicles(vehicles, language=language)
    return []


async def process_turn(
    *,
    state: ConversationCanonicalState,
    inbound_text: str = "",
    inbound: InboundTurn | None = None,
    understand: UnderstandingFn,
    pool: asyncpg.Pool | None = None,
    linked_vehicle_titles: list[str] | None = None,
    image_bytes: bytes | None = None,
) -> ProcessTurnResult:
    if inbound is None:
        inbound = inbound_from_text_compat(inbound_text, thread_id=state.thread_id)

    from sdr.infrastructure.isolated_inventory import coerce_isolated_pool

    pool = coerce_isolated_pool(pool)

    listing_meta = inbound.raw_message_ref or {}
    listing_ref = listing_meta.get("listing_id") or listing_meta.get("listing_url")
    state.listing_reference = str(listing_ref) if listing_ref else None

    from sdr.understanding.response_composer import reset_compose_meta

    reset_compose_meta()

    # HUMAN_ACTIVE: persist inbound is the orchestrator's job. Do not understand,
    # compose, or run tools. HANDOFF_SENT falls through — vendor is notified
    # but AI stays active (qualify / answer / ack, no second HANDOFF_VENDOR).
    if is_ai_silenced(state):
        return ProcessTurnResult(
            action_plan=ActionPlan(
                action=Action.NO_REPLY,
                reason_code="ai_silenced",
                reason="Thread already with human",
            ),
            state=state,
            outbound_texts=[],
            turn_facts=TurnFacts(),
            tool_results=[],
        )

    if inbound.is_media_failed:
        failure = inbound.failure_code.value if inbound.failure_code else "unknown"
        if not _is_sandbox():
            plan = ActionPlan(
                action=Action.NO_REPLY,
                reason_code="media_processing_failed_silent",
                reason=f"Media could not be processed: {failure}",
            )
            outbound: list[str] = []
        else:
            plan = ActionPlan(
                action=Action.MEDIA_FAILED,
                reason_code="media_processing_failed",
                reason=f"Media could not be processed: {failure}",
            )
            outbound = _compose_media_failed_response(inbound)
        if outbound:
            state.assistant_turn_count = state.assistant_turn_count + 1
        return ProcessTurnResult(
            action_plan=plan,
            state=state,
            outbound_texts=outbound,
            turn_facts=TurnFacts(),
            tool_results=[],
        )

    if linked_vehicle_titles:
        titles = [t.strip() for t in linked_vehicle_titles if t and str(t).strip()]
        if titles:
            state.facts = {
                **state.facts,
                "crm_linked_vehicles": ", ".join(titles),
            }

    facts = await understand(inbound.effective_text, state)
    from sdr.domain.pending_question import overlay_consignment_acceptance, overlay_pending_question

    facts = overlay_pending_question(facts, state, inbound.effective_text)
    facts = overlay_consignment_acceptance(facts, state, inbound.effective_text)
    from sdr.domain.location_request import has_store_location_request_evidence

    if has_store_location_request_evidence(inbound.effective_text):
        facts.location_request = True

    # If an image vehicle-hint was extracted with high confidence and the
    # Understanding LLM did not resolve a vehicle preference from text alone,
    # inject the vision-extracted data so inventory search can proceed without
    # forcing the customer to re-type the vehicle name.
    from sdr.domain.visual_resolution import is_weak_vehicle_text

    vehicle_hint = inbound.raw_message_ref.get("vehicle_hint") if inbound.raw_message_ref else None
    if vehicle_hint and isinstance(vehicle_hint, dict) and vehicle_hint.get("is_vehicle"):
        hint_model = vehicle_hint.get("model")
        hint_brand = vehicle_hint.get("brand")
        hint_color = vehicle_hint.get("color")
        hint_type = vehicle_hint.get("vehicle_type")
        existing_model = facts.facts.get("desired_model")
        existing_text = facts.facts.get("desired_vehicle_text")
        if is_weak_vehicle_text(existing_model) and is_weak_vehicle_text(existing_text):
            injected: dict = {}
            if hint_model:
                injected["desired_model"] = hint_model
            if hint_brand and hint_model:
                injected["desired_vehicle_text"] = f"{hint_brand} {hint_model}"
            elif hint_brand:
                injected["desired_vehicle_text"] = hint_brand
            if hint_color and "desired_color" not in facts.facts:
                injected["desired_color"] = hint_color
            if hint_type and "vehicle_type" not in facts.facts:
                injected["vehicle_type"] = hint_type
            facts.facts = {**facts.facts, **injected}

    # Quoted/reply text is structured context on InboundTurn.quoted — never a
    # substitute for customer-authored desired_vehicle_text (URLs and card
    # captions must not be treated as the customer typing a vehicle).

    # Document extraction is authoritative for identity fields when present.
    # Inject into TurnFacts so merge + CRM persistence do not depend only on
    # the Understanding LLM re-reading the structured inbound text.
    from sdr.application.inbound_document import identity_fields_from_inbound

    identity_patch = {
        key: value
        for key, value in identity_fields_from_inbound(inbound).items()
        if key not in facts.facts
    }
    if identity_patch:
        facts.facts = {**facts.facts, **identity_patch}

    from sdr.domain.followup import (
        FollowUpCancelIntent,
        apply_followup_transition,
        enrich_turn_facts_from_inbound,
        followup_decision,
        inbound_is_followup_pause,
        overlay_followup_suggestions,
    )
    from sdr.application.followup_runtime import immediate_pause_bubbles
    from sdr.domain.followup_cancel import is_opt_out_text
    from sdr.domain.ownership import vendor_already_notified
    from sdr.domain.scheduling import suggest_visit_slots
    from sdr.domain.visit import apply_visit_from_inbound, apply_visit_utterance, parse_visit_utterance

    prev_pending = state.pending_question
    prev_primary = state.primary_vehicle_id
    merged = deterministic_merge(state, facts, inbound_text=inbound.effective_text)
    apply_commercial_document_receipt(merged, inbound)

    inbound_low = (inbound.effective_text or "").lower()
    saturday_ask = "sábado" in inbound_low or "sabado" in inbound_low
    true_pause = inbound_is_followup_pause(
        inbound.effective_text, facts, state=merged
    )
    if true_pause:
        parsed_visit = parse_visit_utterance("", [])
    elif vendor_already_notified(merged):
        parsed_visit = parse_visit_utterance(inbound.effective_text, [])
        apply_visit_utterance(merged, parsed_visit)
    else:
        parsed_visit = apply_visit_from_inbound(merged, inbound.effective_text)
    visit_actionable = (not true_pause) and bool(
        parsed_visit.time
        or parsed_visit.date
        or parsed_visit.accepted_offered
        or parsed_visit.declined
        or parsed_visit.interest
        or parsed_visit.period
    )
    saturday_slots_already = all(
        "sábado" in str(s).lower() or "sabado" in str(s).lower()
        for s in (merged.offered_visit_slots or [])
    ) if merged.offered_visit_slots else False
    if (
        saturday_ask
        and parsed_visit.time is None
        and not parsed_visit.accepted_offered
        and not parsed_visit.declined
        and not saturday_slots_already
    ):
        merged.visit_date = None
        merged.visit_period = None
        if not merged.visit_time:
            merged.visit_preferred_time = None
        merged.offered_visit_slots = suggest_visit_slots(prefer_saturday=True)
        merged.needs_visit_slot_offer = True
    elif (
        not parsed_visit.declined
        and not parsed_visit.courtesy
        and (
            parsed_visit.accepted_offered
            or parsed_visit.date is not None
            or parsed_visit.time is not None
            or parsed_visit.period is not None
        )
    ):
        merged.signals.visit_intent = True

    opted_out_text = is_opt_out_text(inbound.effective_text or "")
    if not visit_actionable or opted_out_text:
        enrich_turn_facts_from_inbound(facts, inbound.effective_text)
        overlay_followup_suggestions(merged.followup, facts)
    followup_pause_decision = followup_decision(
        merged, facts, inbound_text=inbound.effective_text
    )
    apply_pause = (
        not visit_actionable
        or followup_pause_decision.cancel_intent == FollowUpCancelIntent.OPT_OUT
    )
    if apply_pause:
        apply_followup_transition(merged, followup_pause_decision)
    pause_bubbles = immediate_pause_bubbles(followup_pause_decision)
    pause_ack = bool(
        pause_bubbles
        and followup_pause_decision.eligible
        and not visit_actionable
    )

    if followup_pause_decision.cancel_intent == FollowUpCancelIntent.OPT_OUT:
        return ProcessTurnResult(
            action_plan=ActionPlan(
                action=Action.NO_REPLY,
                reason_code="opt_out",
                reason="Customer opt-out",
            ),
            state=merged,
            outbound_texts=[],
            turn_facts=facts,
            tool_results=[],
        )

    from sdr.domain.vehicle_reference import apply_primary_from_inbound

    listing_id = None
    media_url = None
    if inbound.raw_message_ref:
        listing_id = inbound.raw_message_ref.get("listing_id") or inbound.raw_message_ref.get(
            "listing_url"
        )
        media_url = inbound.raw_message_ref.get("media_url") or inbound.raw_message_ref.get("url")
    apply_primary_from_inbound(
        merged,
        conversation_id=merged.thread_id,
        quoted=inbound.quoted,
        inbound_text=inbound.effective_text,
        listing_id=str(listing_id) if listing_id else merged.listing_reference,
        inbound_media_url=str(media_url) if media_url else None,
        inbound_timestamp=inbound.timestamp,
    )
    from sdr.application.visual_inbound import enrich_state_with_visual, quoted_resolution_from_inbound

    await enrich_state_with_visual(
        merged,
        inbound,
        image_bytes=image_bytes,
        pool=pool,
        quoted_resolution=quoted_resolution_from_inbound(merged, inbound),
    )

    from sdr.domain.dialogue_plan import unanswered_questions_for_turn, is_courtesy_only
    from sdr.domain.qualification_policy import annotate_action_plan

    merged.courtesy_only = is_courtesy_only(inbound.effective_text, facts)
    merged.unanswered_questions = unanswered_questions_for_turn(
        inbound.effective_text or "",
        facts_context=merged.facts,
    )

    plan = decide(merged)
    annotate_action_plan(
        plan,
        merged,
        inbound_has_direct_question=bool(merged.unanswered_questions),
    )
    from sdr.domain.visit import should_send_store_location

    if not should_send_store_location(merged):
        plan.tool_calls = [
            tc for tc in (plan.tool_calls or []) if tc.get("tool") != "send_location"
        ]
        if plan.action == Action.SEND_LOCATION:
            plan = ActionPlan(
                action=Action.ASK_INFO,
                handoff=False,
                reason_code="post_handoff_continue" if vendor_already_notified(merged) else plan.reason_code,
                reason="Store location already sent; continue without a second pin",
            )
            annotate_action_plan(
                plan,
                merged,
                inbound_has_direct_question=bool(merged.unanswered_questions),
            )

    # After deciding, persist the field being asked so the next turn can resolve
    # short confirmations ("sim", "exato") against the right context.
    asked = plan.ask_field or plan.next_question
    if plan.reason_code == "answer_direct_question":
        merged.pending_question = None
    elif asked and plan.action in (
        Action.ASK_INFO,
        Action.SHOW_OFFERS,
        Action.SEND_PHOTOS,
        Action.SEND_LOCATION,
    ):
        merged.pending_question = asked
        if asked == "documents":
            merged.documents_asked = True
        if asked == "desired_installment":
            merged.installment_asked = True
        if asked == "visit":
            merged.visit_invited = True
    elif plan.action not in (Action.ASK_INFO, Action.SHOW_OFFERS, Action.SEND_PHOTOS):
        merged.pending_question = None
    # Persist visit question so the next turn can distinguish an unconfirmed invite
    # from a normal post-triage turn. Overrides the None set above.
    if plan.action == Action.REGISTER_VISIT_INTEREST:
        merged.pending_question = "visit"
        from sdr.domain.scheduling import suggest_visit_slots

        inbound_low = (inbound.effective_text or "").lower()
        prefer_sat = "sábado" in inbound_low or "sabado" in inbound_low
        merged.offered_visit_slots = suggest_visit_slots(prefer_saturday=prefer_sat)

    # Track engagement quality based on this turn.
    _track_engagement(merged, inbound.effective_text, facts)

    outbound: list[str] = []
    outbound_media: list[OutboundMedia] = []
    outbound_location: dict[str, Any] | None = None
    tool_results: list[dict[str, Any]] = []
    validator_result: dict[str, Any] | None = None
    directive: ResponseDirective | None = None

    inbound_ctype = inbound.content_type.value if inbound.content_type else "TEXT"
    planned_handoff = plan.action == Action.HANDOFF_VENDOR and bool(plan.handoff)

    if pause_ack:
        silent_vendor = False
        if (planned_handoff or merged.handoff_ready) and not vendor_already_notified(
            merged
        ):
            # Conversational pause_ack only. Vendor still gets one notify so
            # an actionable lead is not invisible. Never a second notify on
            # the follow-up send.
            mark_handoff_sent(merged, "pause_ack_actionable")
            silent_vendor = True
        plan = ActionPlan(
            action=Action.ASK_INFO,
            reason_code="followup_pause_ack",
            reason="Customer paused; follow-up is scheduled",
            handoff=silent_vendor,
        )
        outbound.extend(pause_bubbles[:1])
    elif plan.action == Action.HANDOFF_VENDOR and plan.handoff:
        if plan.tool_calls:
            tool_results = await execute_tool_calls(plan, merged, pool)
            _record_shown_vehicles(merged, tool_results)
            _update_inventory_search_key(merged, plan, tool_results)
            _record_inventory_match(merged, tool_results)
            # Extract location pin so the orchestrator sends it before the handoff text.
            outbound_location = _location_pin_from_tools(tool_results)
            if any(r.get("tool") == "send_location" for r in tool_results):
                merged.location_sent = True
        from sdr.domain.handoff import customer_handoff_bubbles

        outbound.extend(customer_handoff_bubbles(merged, reason_code=plan.reason_code))
        mark_handoff_sent(merged, plan.reason_code)
    elif plan.action == Action.NO_REPLY:
        pass
    else:
        if plan.tool_calls:
            tool_results = await execute_tool_calls(plan, merged, pool)
            _record_shown_vehicles(merged, tool_results)
            _update_inventory_search_key(merged, plan, tool_results)
            _record_inventory_match(merged, tool_results)

        if _should_silence_tool_failure(plan, tool_results):
            silent = ActionPlan(
                action=Action.NO_REPLY,
                reason_code="tool_failed_silent",
                reason=plan.reason or "tool failed in production",
            )
            return ProcessTurnResult(
                action_plan=silent,
                state=merged,
                outbound_texts=[],
                turn_facts=facts,
                tool_results=tool_results,
            )

        outbound_location = _location_pin_from_tools(tool_results)
        if any(r.get("tool") == "send_location" for r in tool_results):
            merged.location_sent = True

        outbound_media = _outbound_media_from_tools(
            plan, tool_results, language=merged.language or "pt-BR"
        )
        if outbound_media or plan.action == Action.SEND_PHOTOS:
            merged.photo_request = False

        directive = _build_response_directive(
            merged,
            plan,
            tool_results,
            inbound.effective_text,
            inbound_ctype,
            facts,
            prev_pending,
            inbound,
            prev_primary,
        )
        state_map, plan_map, tool_ctx = _directive_to_state_and_plan_maps(directive, plan)
        state_map["offered_visit_slots"] = list(merged.offered_visit_slots or [])
        state_map["visit_preferred_time"] = merged.visit_preferred_time
        state_map["handoff_ready"] = bool(merged.handoff_ready)
        state_map["profile_complete"] = bool(merged.profile_complete)
        state_map["deferred_fields"] = list(merged.deferred_fields or [])
        state_map["collected_fields"] = list(merged.collected_fields or [])
        state_map["missing_fields"] = list(merged.missing_fields or [])
        tool_ctx = dict(tool_ctx or {})
        tool_ctx["outbound_media_planned"] = bool(outbound_media)
        tool_ctx["outbound_media_count"] = len(outbound_media)

        # Prefer deterministic inventory templates when outcome is known —
        # prevents LLM from inventing stock absence on tool failure.
        inv_outcome = directive.inventory_outcome
        if (
            plan.action == Action.SHOW_OFFERS
            and inv_outcome != InventoryOutcome.NOT_EXECUTED
        ):
            # Pre-search preview: tell the customer we're looking it up.
            # Only on subsequent turns — first contact intro already says
            # "Deixa eu te enviar umas fotos" so we avoid duplicate phrasing.
            if outbound_media and merged.assistant_turn_count > 0:
                _lang = directive.language or "pt-BR"
                if _lang.startswith("es"):
                    outbound.append("Déjame buscar en nuestro stock...")
                else:
                    outbound.append("Deixa eu dar uma olhadinha no nosso estoque...")
            from sdr.understanding.response_composer import compose_inventory_response
            from sdr.understanding.validator import validate_inventory_policy

            try:
                bubbles = compose_inventory_response(directive, tool_ctx)
                outbound_texts, validator_result = validate_inventory_policy(
                    bubbles,
                    inventory_outcome=inv_outcome,
                    language=directive.language,
                    conversational_affordance=directive.conversational_affordance,
                )
                outbound.extend(outbound_texts)
            except Exception:
                logger.exception("compose_inventory_response failed; using fallback bubbles")
                outbound.extend(inventory_fallback_bubbles(inv_outcome, language=directive.language))
            # Only preserve OFFER_ALTERNATIVES for installment_tight — SUCCESS_EMPTY
            # no longer gates with yes/no; the Composer asks directly for next preference.
            if plan.reason_code == "installment_tight":
                _apply_pending_after_offers(merged, directive)
        elif plan.action == Action.SEND_PHOTOS:
            from sdr.understanding.response_composer import compose_photos_response
            from sdr.understanding.validator import validate_inventory_policy

            bubbles = compose_photos_response(directive, tool_ctx)
            outbound_texts, validator_result = validate_inventory_policy(
                bubbles,
                inventory_outcome=inv_outcome,
                language=directive.language,
                conversational_affordance=directive.conversational_affordance,
            )
            outbound.extend(outbound_texts)
        else:
            try:
                from sdr.understanding.response_composer import compose_response

                bubbles = await compose_response(state_map, plan_map, tool_context=tool_ctx)
                from sdr.understanding.validator import validate_inventory_policy

                outbound_texts, validator_result = validate_inventory_policy(
                    bubbles,
                    inventory_outcome=inv_outcome,
                    language=directive.language,
                    conversational_affordance=directive.conversational_affordance,
                )
                # Safety net: validator may reject all LLM bubbles (e.g. schedule_without_affordance).
                # Fall back to deterministic template rather than producing empty output.
                if outbound_texts:
                    outbound.extend(outbound_texts)
                else:
                    fallback = _hard_fallback(plan, directive)
                    outbound.extend(fallback)
                    if validator_result is not None and isinstance(validator_result, dict):
                        validator_result["fallback_used"] = True
            except Exception:
                outbound.extend(_hard_fallback(plan, directive))
                validator_result = {
                    "pass": False,
                    "fallback_used": True,
                    "violations": ["composer_exception"],
                }

    if outbound or outbound_media or outbound_location:
        merged.assistant_turn_count = state.assistant_turn_count + 1

    from sdr.understanding.response_composer import last_compose_meta

    compose_meta = last_compose_meta()
    return ProcessTurnResult(
        action_plan=plan,
        state=merged,
        outbound_texts=outbound,
        turn_facts=facts,
        tool_results=tool_results,
        validator_result=validator_result,
        response_directive=directive,
        outbound_media=outbound_media,
        outbound_location=outbound_location,
        question_adherence=compose_meta,
        composer_retries=int(compose_meta.get("retries") or 0),
        questions_rejected=int(compose_meta.get("questions_rejected") or 0),
    )


def _compose_media_failed_response(inbound: InboundTurn) -> list[str]:
    labels = {
        "IMAGE": "foto",
        "DOCUMENT": "documento",
        "AUDIO": "áudio",
        "VIDEO": "vídeo",
        "STICKER": "figurinha",
        "TEXT": "arquivo",
    }
    label = labels.get(inbound.content_type.value, "arquivo")
    code = inbound.failure_code.value if inbound.failure_code else "unknown"
    return [
        f"Recebi seu {label}, mas tive um problema para processar ({code}). "
        "Pode tentar novamente ou me contar o que precisa em texto?"
    ]


def _hard_fallback(plan: ActionPlan, directive: ResponseDirective) -> list[str]:
    if directive.inventory_outcome != InventoryOutcome.NOT_EXECUTED:
        return inventory_fallback_bubbles(
            directive.inventory_outcome, language=directive.language
        )
    from sdr.domain.dialogue_plan import DialoguePlan, fallback_bubbles
    from sdr.understanding.response_composer import _required_question

    parsed = DialoguePlan.from_mapping(directive.dialogue_plan)
    question = None
    if plan.ask_field or plan.next_question:
        question = _required_question(
            {
                "language": directive.language,
                "facts": directive.facts_context,
                "intent": directive.intent.value,
            },
            {"ask_field": plan.ask_field, "next_question": plan.next_question, "action": plan.action.value},
            directive.language or "pt-BR",
        )
    bubbles = fallback_bubbles(
        parsed,
        language=directive.language,
        customer_name=directive.customer_name,
        next_question=question,
        document_kind=directive.document_kind,
        should_introduce=directive.should_introduce,
    )
    if bubbles:
        return bubbles
    action = plan.action
    if action == Action.ASK_INFO and plan.next_question:
        return [plan.next_question]
    if action == Action.SMALLTALK:
        if directive.should_introduce:
            return introduction_smalltalk_bubbles(
                directive.language,
                customer_name=directive.customer_name,
                inbound_text=directive.inbound_text,
                skip_intent_menu=parsed.skip_generic_intent_menu,
            )
        return continuation_smalltalk_bubbles(
            directive.language,
            inbound_text=directive.inbound_text,
            courtesy=parsed.courtesy_only,
        )
    if action == Action.COMMERCIAL_UNKNOWN:
        return ["Me conta o que você está procurando que eu te ajudo!"]
    if action == Action.REGISTER_VISIT_INTEREST:
        from sdr.domain.scheduling import format_slot_suggestion, suggest_visit_slots

        slots = suggest_visit_slots()
        return [format_slot_suggestion(slots, lang=directive.language or "pt")]
    if action == Action.MEDIA_FAILED:
        return ["Tive um problema com a mídia. Pode me contar em texto?"]
    return ["Como posso ajudar?"]


async def process_turn_with_facts(
    *,
    state: ConversationCanonicalState,
    facts: TurnFacts,
    pool: asyncpg.Pool | None = None,
) -> ProcessTurnResult:
    async def _fixed(_text: str, _state: ConversationCanonicalState) -> TurnFacts:
        return facts

    return await process_turn(state=state, inbound_text="", understand=_fixed, pool=pool)
