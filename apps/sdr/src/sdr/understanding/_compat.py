"""Temporary type shims when ``sdr.domain.types`` is not yet available.

Source of truth: ``sdr.domain.types`` (SDR CORE). Prefer importing from there.
This module exists only so Wave 1 understanding can type-check and run in
parallel before domain contracts land. Delete once domain.types exports
``TurnFacts``, ``ActionPlan``, and conversation state shapes.
"""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class TurnFactsSignals(TypedDict, total=False):
    explicit_handoff: bool
    explicit_offer: bool
    visit_intent: bool
    high_purchase_intent: bool
    sensitive_data_refusal: bool


class TurnFacts(TypedDict):
    intent: str
    facts: dict[str, Any]
    signals: TurnFactsSignals
    language: NotRequired[str]
    confidence: NotRequired[dict[str, Any]]


class ActionPlan(TypedDict):
    action: str
    handoff: bool
    tool_calls: list[dict[str, Any]]
    next_question: NotRequired[str | None]
    reason_code: NotRequired[str | None]


class ConversationState(TypedDict, total=False):
    thread_id: str
    language: str
    customer: dict[str, Any]
    business: dict[str, Any]
    lifecycle: dict[str, Any]
    missing_fields: list[str]
    summary: str


def load_turn_facts_type() -> type:
    try:
        from sdr.domain.types import TurnFacts as DomainTurnFacts  # type: ignore[attr-defined]

        return DomainTurnFacts
    except Exception:
        return TurnFacts


def load_action_plan_type() -> type:
    try:
        from sdr.domain.types import ActionPlan as DomainActionPlan  # type: ignore[attr-defined]

        return DomainActionPlan
    except Exception:
        return ActionPlan


def load_conversation_state_type() -> type:
    try:
        from sdr.domain.types import ConversationState as DomainConversationState  # type: ignore[attr-defined]

        return DomainConversationState
    except Exception:
        return ConversationState
