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

from dataclasses import dataclass
from typing import Any, Protocol

import asyncpg

from sdr.application.tool_executor import execute_tool_calls, tool_results_to_context
from sdr.context_builder import ConversationContextBuilder
from sdr.domain.decision import decide, inventory_search_key
from sdr.domain.handoff import confirmation_message, mark_handoff_sent
from sdr.domain.inbound import InboundTurn, inbound_from_text_compat
from sdr.domain.inventory_outcome import (
    claims_for_inventory_outcome,
    extract_inventory_outcome,
    inventory_fallback_bubbles,
    is_semantic_inventory_success,
)
from sdr.domain.merge import deterministic_merge
from sdr.domain.pending_interaction import PendingInteraction
from sdr.domain.types import (
    Action,
    ActionPlan,
    ConversationCanonicalState,
    InventoryOutcome,
    ResponseDirective,
    TurnFacts,
)

_context_builder = ConversationContextBuilder()


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


def _build_response_directive(
    merged: ConversationCanonicalState,
    plan: ActionPlan,
    tool_results: list[dict[str, Any]],
) -> ResponseDirective:
    """Build ResponseDirective — single source of truth for Composer inputs."""
    should_introduce = merged.assistant_turn_count == 0

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

    # Only authorize the alternatives CTA when we will record pending_interaction.
    affordance = PendingInteraction.NONE
    if (
        plan.action == Action.SHOW_OFFERS
        and inventory_outcome == InventoryOutcome.SUCCESS_EMPTY
    ):
        affordance = PendingInteraction.OFFER_ALTERNATIVES
        if "ask_if_alternatives_acceptable" not in allowed:
            allowed = [*allowed, "ask_if_alternatives_acceptable"]
    else:
        allowed = [c for c in allowed if c != "ask_if_alternatives_acceptable"]

    claims_forbidden = [
        "approval_guarantee",
        "rate_promise",
        "price_guarantee",
        "assert_engine_from_title",
        *forbidden,
    ]
    if merged.lifecycle.status.value in ("HANDOFF_SENT", "HUMAN_ACTIVE"):
        claims_forbidden.append("any_response")

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

    return ResponseDirective(
        action=plan.action,
        reason_code=plan.reason_code,
        should_introduce=should_introduce,
        intent=merged.intent,
        customer_name=merged.customer.name,
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
    )


def _directive_to_state_and_plan_maps(
    directive: ResponseDirective,
    plan: ActionPlan,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    state_map: dict[str, Any] = {
        "language": directive.language,
        "should_introduce": directive.should_introduce,
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
    """Update search key only on semantic success (FOUND or EMPTY)."""
    outcome = extract_inventory_outcome(tool_results)
    if not is_semantic_inventory_success(outcome):
        return
    for tc in plan.tool_calls:
        if tc.get("tool") == "inventory_search":
            key = tc.get("_search_key") or inventory_search_key(
                merged.facts,
                alternative_scope=merged.alternative_scope,
                budget_status=merged.budget_status,
            )
            merged.last_inventory_search_key = key
            merged.last_inventory_outcome = outcome.value
            return
    merged.last_inventory_search_key = inventory_search_key(
        merged.facts,
        alternative_scope=merged.alternative_scope,
        budget_status=merged.budget_status,
    )
    merged.last_inventory_outcome = outcome.value


def _apply_pending_after_offers(
    merged: ConversationCanonicalState,
    directive: ResponseDirective,
) -> None:
    """Record pending affordance when Composer was authorized to offer alternatives."""
    if directive.conversational_affordance == PendingInteraction.OFFER_ALTERNATIVES:
        merged.pending_interaction = PendingInteraction.OFFER_ALTERNATIVES


async def process_turn(
    *,
    state: ConversationCanonicalState,
    inbound_text: str = "",
    inbound: InboundTurn | None = None,
    understand: UnderstandingFn,
    pool: asyncpg.Pool | None = None,
) -> ProcessTurnResult:
    if inbound is None:
        inbound = inbound_from_text_compat(inbound_text, thread_id=state.thread_id)

    if inbound.is_media_failed:
        plan = ActionPlan(
            action=Action.MEDIA_FAILED,
            reason_code="media_processing_failed",
            reason=f"Media could not be processed: {inbound.failure_code}",
        )
        return ProcessTurnResult(
            action_plan=plan,
            state=state,
            outbound_texts=_compose_media_failed_response(inbound),
            turn_facts=TurnFacts(),
            tool_results=[],
        )

    facts = await understand(inbound.effective_text, state)
    merged = deterministic_merge(state, facts)
    plan = decide(merged)

    outbound: list[str] = []
    tool_results: list[dict[str, Any]] = []
    validator_result: dict[str, Any] | None = None
    directive: ResponseDirective | None = None

    if plan.action == Action.HANDOFF_VENDOR and plan.handoff:
        if plan.tool_calls:
            tool_results = await execute_tool_calls(plan, merged, pool)
            _update_inventory_search_key(merged, plan, tool_results)
        outbound.append(confirmation_message(merged))
        mark_handoff_sent(merged, plan.reason_code)
    elif plan.action == Action.NO_REPLY:
        pass
    else:
        if plan.tool_calls:
            tool_results = await execute_tool_calls(plan, merged, pool)
            _update_inventory_search_key(merged, plan, tool_results)

        directive = _build_response_directive(merged, plan, tool_results)
        state_map, plan_map, tool_ctx = _directive_to_state_and_plan_maps(directive, plan)

        # Prefer deterministic inventory templates when outcome is known —
        # prevents LLM from inventing stock absence on tool failure.
        inv_outcome = directive.inventory_outcome
        if (
            plan.action == Action.SHOW_OFFERS
            and inv_outcome != InventoryOutcome.NOT_EXECUTED
        ):
            from sdr.understanding.response_composer import compose_inventory_response

            bubbles = compose_inventory_response(directive, tool_ctx)
            from sdr.understanding.validator import validate_inventory_policy

            outbound_texts, validator_result = validate_inventory_policy(
                bubbles,
                inventory_outcome=inv_outcome,
                language=directive.language,
                conversational_affordance=directive.conversational_affordance,
            )
            outbound.extend(outbound_texts)
            _apply_pending_after_offers(merged, directive)
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
                outbound.extend(outbound_texts)
            except Exception:
                outbound.extend(_hard_fallback(plan, directive))
                validator_result = {
                    "pass": False,
                    "fallback_used": True,
                    "violations": ["composer_exception"],
                }

    return ProcessTurnResult(
        action_plan=plan,
        state=merged,
        outbound_texts=outbound,
        turn_facts=facts,
        tool_results=tool_results,
        validator_result=validator_result,
        response_directive=directive,
    )


def _compose_media_failed_response(inbound: InboundTurn) -> list[str]:
    content_label = inbound.content_type.value.lower()
    return [
        f"Recebi seu {content_label}, mas tive um problema para processar. "
        "Pode tentar novamente ou me contar o que precisa em texto?"
    ]


def _hard_fallback(plan: ActionPlan, directive: ResponseDirective) -> list[str]:
    if directive.inventory_outcome != InventoryOutcome.NOT_EXECUTED:
        return inventory_fallback_bubbles(
            directive.inventory_outcome, language=directive.language
        )
    action = plan.action
    if action == Action.ASK_INFO and plan.next_question:
        return [plan.next_question]
    if action == Action.SMALLTALK:
        if directive.should_introduce:
            return ["Oi! Sou a Júlia da FacilCar. Como posso te ajudar?"]
        return ["Como posso ajudar?"]
    if action == Action.COMMERCIAL_UNKNOWN:
        return ["Me conta o que você está procurando que eu te ajudo!"]
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
