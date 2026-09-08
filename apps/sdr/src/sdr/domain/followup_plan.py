"""Semantic follow-up plan — what to resume, not how to word it.

DialoguePlan owns inbound conversational turns. Follow-up is a proactive
outbound after silence, so it gets a smaller contract:

    reason, authorized_facts, vehicle_label, pending_commitment,
    requested_action, constraints

Code owns the primary action and stock truth. The Composer phrases.
Stock claims must come from the CURRENT inventory tool result, never from
an old snapshot in authorized_facts.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Mapping, Sequence

from sdr.domain.clock import now_brt, parse_clock
from sdr.domain.inventory_outcome import extract_inventory_outcome
from sdr.domain.types import InventoryOutcome

Clock = Callable[[], datetime]


class FollowUpReason(str, Enum):
    DOCUMENTS_PENDING = "documents_pending"
    PARTNER_DECISION = "partner_decision"
    INTERRUPTED_SIMULATION = "interrupted_simulation"
    SPECIFIC_VEHICLE = "specific_vehicle"
    CATEGORY_INTEREST = "category_interest"
    EMPTY = "empty"


class FollowUpAction(str, Enum):
    ASK_DOCUMENTS_STATUS = "ask_documents_status"
    ASK_PARTNER_DECISION = "ask_partner_decision"
    RESUME_SIMULATION = "resume_simulation"
    ASK_VEHICLE_INTEREST = "ask_vehicle_interest"
    ASK_CATEGORY_INTEREST = "ask_category_interest"
    CANCEL_SAFE = "cancel_safe"
    DO_NOT_SEND = "do_not_send"


class FollowUpStrategy(str, Enum):
    COMPOSE = "compose"
    CANCEL_SAFE = "cancel_safe"
    DO_NOT_SEND = "do_not_send"


DEFAULT_CONSTRAINTS: tuple[str, ...] = (
    "one_primary_action",
    "max_two_bubbles",
    "prefer_one_bubble",
    "no_reintroduce",
    "no_absence_shame",
    "no_pressure",
    "no_full_funnel",
    "no_document_obligation",
    "no_availability_promise_without_current_stock",
    "no_financial_promise",
    "no_internal_leak",
    "no_substitute_vehicle",
)

_UNAVAILABLE_OUTCOMES = frozenset(
    {
        InventoryOutcome.SUCCESS_SOLD,
        InventoryOutcome.SUCCESS_EMPTY,
    }
)
_UNCONFIRMED_OUTCOMES = frozenset(
    {
        InventoryOutcome.NOT_EXECUTED,
        InventoryOutcome.FAILED_RETRYABLE,
        InventoryOutcome.FAILED_TERMINAL,
    }
)
_STOCK_BOUND_ACTIONS = frozenset(
    {
        FollowUpAction.ASK_VEHICLE_INTEREST.value,
    }
)
_STOCK_BOUND_REASONS = frozenset(
    {
        FollowUpReason.SPECIFIC_VEHICLE.value,
        FollowUpReason.CATEGORY_INTEREST.value,
    }
)
_SOLD_STATUSES = frozenset({"SOLD", "UNPUBLISHED"})
_RESERVED_STATUSES = frozenset({"RESERVED"})


def resolve_clock(clock: Clock | datetime | str | None = None) -> datetime:
    """Resolve an injectable clock. Never sleeps."""
    if clock is None:
        return now_brt()
    if callable(clock):
        return clock()
    parsed = parse_clock(clock)
    return parsed if parsed is not None else now_brt()


def _as_outcome(raw: Any) -> InventoryOutcome | None:
    if isinstance(raw, InventoryOutcome):
        return raw
    if isinstance(raw, str):
        try:
            return InventoryOutcome(raw)
        except ValueError:
            return None
    return None


def _tool_rows(tool_results: Any) -> list[dict[str, Any]]:
    if tool_results is None:
        return []
    if isinstance(tool_results, InventoryOutcome):
        return [{"tool": "inventory_search", "outcome": tool_results.value}]
    if isinstance(tool_results, Mapping):
        if tool_results.get("tool") or tool_results.get("outcome") or tool_results.get("vehicles"):
            return [dict(tool_results)]
        nested = tool_results.get("tool_results") or tool_results.get("inventory")
        if nested is not None:
            return _tool_rows(nested)
        if tool_results.get("inventory_outcome"):
            return [
                {
                    "tool": "inventory_search",
                    "outcome": tool_results["inventory_outcome"],
                    "vehicles": list(tool_results.get("vehicles") or []),
                    "alternatives": list(tool_results.get("alternatives") or []),
                }
            ]
        return []
    if isinstance(tool_results, Sequence) and not isinstance(tool_results, (str, bytes)):
        rows: list[dict[str, Any]] = []
        for item in tool_results:
            if isinstance(item, Mapping):
                rows.append(dict(item))
            elif isinstance(item, InventoryOutcome):
                rows.append({"tool": "inventory_search", "outcome": item.value})
        return rows
    return []


def _status_token(value: Any) -> str:
    return str(value or "").strip().upper()


def current_inventory_from_tools(
    tool_results: Any,
) -> tuple[InventoryOutcome, str | None, tuple[str, ...]]:
    """Read CURRENT inventory from injected tool results — not a snapshot.

    Returns ``(outcome, availability_detail, alternative_labels)``.
    Detail is ``sold`` / ``reserved`` / ``available`` / None.
    Alternative labels are for the validator to block auto-substitutes.
    """
    rows = _tool_rows(tool_results)
    outcome = extract_inventory_outcome(rows) if rows else InventoryOutcome.NOT_EXECUTED
    detail: str | None = None
    alternatives: list[str] = []

    for row in rows:
        raw_status = row.get("availability_status") or row.get("vehicle_status")
        token = _status_token(raw_status)
        if token in _SOLD_STATUSES:
            detail = "sold"
        elif token in _RESERVED_STATUSES:
            detail = "reserved"
        for vehicle in list(row.get("vehicles") or []):
            if not isinstance(vehicle, Mapping):
                continue
            v_status = _status_token(vehicle.get("status"))
            if v_status in _SOLD_STATUSES:
                detail = "sold"
            elif v_status in _RESERVED_STATUSES:
                detail = "reserved"
        for alt in list(row.get("alternatives") or []):
            if not isinstance(alt, Mapping):
                continue
            for key in ("title", "model", "label"):
                label = str(alt.get(key) or "").strip()
                if label and label not in alternatives:
                    alternatives.append(label)

    if detail is None:
        if outcome == InventoryOutcome.SUCCESS_SOLD:
            detail = "sold"
        elif outcome == InventoryOutcome.SUCCESS_FOUND:
            detail = "available"
    return outcome, detail, tuple(alternatives)


def resolved_vehicle_label(plan: "FollowUpPlan") -> str | None:
    if plan.vehicle_label and str(plan.vehicle_label).strip():
        return str(plan.vehicle_label).strip()
    facts = plan.authorized_facts or {}
    for key in ("vehicle_label", "desired_vehicle_label", "label"):
        value = facts.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    desired = facts.get("desired_vehicle")
    if isinstance(desired, Mapping):
        for key in ("label", "title", "model"):
            value = desired.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


@dataclass(slots=True)
class FollowUpPlan:
    """One primary follow-up action with authorized facts only."""

    reason: str
    requested_action: str
    authorized_facts: dict[str, Any] = field(default_factory=dict)
    vehicle_label: str | None = None
    pending_commitment: str | None = None
    constraints: tuple[str, ...] = DEFAULT_CONSTRAINTS
    inventory_outcome: str | None = None
    availability_detail: str | None = None
    alternative_labels: tuple[str, ...] = ()
    strategy: str = FollowUpStrategy.COMPOSE.value
    strategy_reason: str | None = None
    language: str = "pt-BR"
    max_bubbles: int = 2

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason,
            "requested_action": self.requested_action,
            "authorized_facts": dict(self.authorized_facts),
            "vehicle_label": self.vehicle_label,
            "pending_commitment": self.pending_commitment,
            "constraints": list(self.constraints),
            "inventory_outcome": self.inventory_outcome,
            "availability_detail": self.availability_detail,
            "alternative_labels": list(self.alternative_labels),
            "strategy": self.strategy,
            "strategy_reason": self.strategy_reason,
            "language": self.language,
            "max_bubbles": self.max_bubbles,
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> "FollowUpPlan":
        if not isinstance(raw, Mapping):
            return cls(
                reason=FollowUpReason.EMPTY.value,
                requested_action=FollowUpAction.DO_NOT_SEND.value,
                strategy=FollowUpStrategy.DO_NOT_SEND.value,
                strategy_reason="empty_plan",
            )
        constraints_raw = raw.get("constraints")
        if constraints_raw:
            constraints = tuple(str(c) for c in constraints_raw)
        else:
            constraints = DEFAULT_CONSTRAINTS
        return cls(
            reason=str(raw.get("reason") or FollowUpReason.EMPTY.value),
            requested_action=str(
                raw.get("requested_action") or FollowUpAction.DO_NOT_SEND.value
            ),
            authorized_facts=dict(raw.get("authorized_facts") or {}),
            vehicle_label=(
                str(raw["vehicle_label"]).strip() if raw.get("vehicle_label") else None
            ),
            pending_commitment=(
                str(raw["pending_commitment"]).strip()
                if raw.get("pending_commitment")
                else None
            ),
            constraints=constraints,
            inventory_outcome=(
                str(raw["inventory_outcome"]) if raw.get("inventory_outcome") else None
            ),
            availability_detail=(
                str(raw["availability_detail"])
                if raw.get("availability_detail")
                else None
            ),
            alternative_labels=tuple(str(a) for a in (raw.get("alternative_labels") or ())),
            strategy=str(raw.get("strategy") or FollowUpStrategy.COMPOSE.value),
            strategy_reason=(
                str(raw["strategy_reason"]) if raw.get("strategy_reason") else None
            ),
            language=str(raw.get("language") or "pt-BR"),
            max_bubbles=int(raw.get("max_bubbles") or 2),
        )


def is_empty_plan(plan: FollowUpPlan) -> bool:
    if plan.strategy == FollowUpStrategy.DO_NOT_SEND.value:
        return True
    if plan.requested_action in {
        FollowUpAction.DO_NOT_SEND.value,
        "",
    }:
        return True
    if plan.reason in {FollowUpReason.EMPTY.value, ""}:
        return True
    has_context = bool(
        resolved_vehicle_label(plan)
        or plan.pending_commitment
        or plan.authorized_facts
    )
    return not has_context


def apply_current_inventory(
    plan: FollowUpPlan,
    tool_results: Any = None,
) -> FollowUpPlan:
    """Bind CURRENT inventory outcome. Sold/reserved cancel the original copy."""
    if is_empty_plan(plan):
        return replace(
            plan,
            strategy=FollowUpStrategy.DO_NOT_SEND.value,
            requested_action=FollowUpAction.DO_NOT_SEND.value,
            strategy_reason=plan.strategy_reason or "empty_plan",
        )

    outcome, detail, alternatives = current_inventory_from_tools(tool_results)
    updated = replace(
        plan,
        inventory_outcome=outcome.value,
        availability_detail=detail,
        alternative_labels=alternatives,
    )
    stock_bound = (
        updated.requested_action in _STOCK_BOUND_ACTIONS
        or updated.reason in _STOCK_BOUND_REASONS
    )
    unavailable = detail in {"sold", "reserved"} or outcome in _UNAVAILABLE_OUTCOMES

    if stock_bound and unavailable:
        if detail == "reserved":
            reason = "vehicle_reserved"
        elif detail == "sold" or outcome == InventoryOutcome.SUCCESS_SOLD:
            reason = "vehicle_sold"
        else:
            reason = "vehicle_not_in_current_stock"
        return replace(
            updated,
            strategy=FollowUpStrategy.CANCEL_SAFE.value,
            requested_action=FollowUpAction.ASK_CATEGORY_INTEREST.value,
            strategy_reason=reason,
            availability_detail=detail
            or ("sold" if outcome == InventoryOutcome.SUCCESS_SOLD else detail),
        )
    if outcome in _UNCONFIRMED_OUTCOMES and stock_bound:
        return replace(
            updated,
            strategy=FollowUpStrategy.COMPOSE.value,
            strategy_reason=updated.strategy_reason or "availability_unconfirmed",
        )
    return replace(updated, strategy=FollowUpStrategy.COMPOSE.value)


def fallback_followup_bubbles(plan: FollowUpPlan) -> list[str]:
    """One contextual sentence from authorized facts — not a generic greeting."""
    if plan.strategy == FollowUpStrategy.DO_NOT_SEND.value or is_empty_plan(plan):
        return []

    es = (plan.language or "").lower().startswith("es")
    label = resolved_vehicle_label(plan)
    action = plan.requested_action
    strategy = plan.strategy

    if strategy == FollowUpStrategy.CANCEL_SAFE.value:
        # Sold/reserved/empty: never reuse availability copy; never name a substitute.
        if es:
            return ["¿Sigues buscando en esa categoría?"]
        return ["Continua procurando nessa categoria?"]

    if action == FollowUpAction.ASK_DOCUMENTS_STATUS.value:
        if es:
            return ["¿Conseguiste reunir los comprobantes que ibas a enviar?"]
        return ["Conseguiu reunir os comprovantes que ia enviar?"]

    if action == FollowUpAction.ASK_PARTNER_DECISION.value:
        if label:
            if es:
                return [f"¿Conseguiste conversar sobre el {label}?"]
            return [f"Conseguiu conversar sobre o {label}?"]
        if es:
            return ["¿Conseguiste conversar sobre esa decisión?"]
        return ["Conseguiu conversar sobre essa decisão?"]

    if action == FollowUpAction.RESUME_SIMULATION.value:
        if label:
            if es:
                return [f"¿Aún te ayudo con la simulación del {label}?"]
            return [f"Ainda te ajudo com a simulação do {label}?"]
        if es:
            return ["¿Aún te ayudo con la simulación de financiamiento?"]
        return ["Ainda te ajudo com a simulação de financiamento?"]

    if action == FollowUpAction.ASK_CATEGORY_INTEREST.value:
        if es:
            return ["¿Sigues buscando en esa categoría?"]
        return ["Continua procurando nessa categoria?"]

    if action == FollowUpAction.ASK_VEHICLE_INTEREST.value and label:
        if es:
            return [f"¿El {label} todavía te interesa?"]
        return [f"O {label} ainda te interessa?"]

    if label:
        if es:
            return [f"¿El {label} todavía te interesa?"]
        return [f"O {label} ainda te interessa?"]

    commitment = plan.pending_commitment or plan.authorized_facts.get("pending_commitment")
    if isinstance(commitment, str) and commitment.strip():
        if es:
            return ["¿Pudiste avanzar en lo que habías comentado?"]
        return ["Conseguiu avançar no que tinha comentado?"]
    return []
