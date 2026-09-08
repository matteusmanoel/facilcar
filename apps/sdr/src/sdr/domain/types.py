"""Canonical domain types for Júlia SDR (pure — no IO)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sdr.domain.budget_status import BudgetStatus
from sdr.domain.pending_interaction import (
    AlternativeScope,
    PendingInteraction,
    PendingResolution,
)


class BusinessIntent(str, Enum):
    PURCHASE = "purchase"
    PURCHASE_FINANCING = "purchase_financing"
    TRADE = "trade"
    SALE = "sale"
    CONSIGNMENT = "consignment"
    REFINANCING = "refinancing"
    SMALLTALK = "smalltalk"
    UNKNOWN = "unknown"


class Action(str, Enum):
    ASK_INFO = "ask_info"
    SHOW_OFFERS = "show_offers"
    SEND_PHOTOS = "send_photos"
    SEND_LOCATION = "send_location"
    REGISTER_VISIT_INTEREST = "register_visit_interest"
    HANDOFF_VENDOR = "handoff_vendor"
    SMALLTALK = "smalltalk"
    # Produced when language could not be understood (not a greeting, not classified).
    # Decision engine must not silently fall back to SMALLTALK for unresolved commercial language.
    COMMERCIAL_UNKNOWN = "commercial_unknown"
    # Produced when media processing failed explicitly.
    MEDIA_FAILED = "media_failed"
    NO_REPLY = "no_reply"


class InventoryOutcome(str, Enum):
    """Typed inventory tool outcome — Composer must not infer stock from error strings."""

    SUCCESS_FOUND = "SUCCESS_FOUND"
    SUCCESS_EMPTY = "SUCCESS_EMPTY"
    SUCCESS_SOLD = "SUCCESS_SOLD"       # vehicle exists in catalog but is sold / unpublished
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_TERMINAL = "FAILED_TERMINAL"
    NOT_EXECUTED = "NOT_EXECUTED"


class LeadTemperature(str, Enum):
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"


class LifecycleStatus(str, Enum):
    BOT_ACTIVE = "BOT_ACTIVE"
    QUALIFYING = "QUALIFYING"
    READY_FOR_HANDOFF = "READY_FOR_HANDOFF"
    HANDOFF_SENT = "HANDOFF_SENT"
    HUMAN_ACTIVE = "HUMAN_ACTIVE"
    HUMAN_CLOSED = "HUMAN_CLOSED"


class Actionability(str, Enum):
    INSUFFICIENT = "INSUFFICIENT"
    ACTIONABLE = "ACTIONABLE"
    HANDOFF_NOW = "HANDOFF_NOW"


class BusinessType(str, Enum):
    """Canonical CRM-facing business type (conversation_state contract)."""

    PURCHASE = "PURCHASE"
    TRADE_IN = "TRADE_IN"
    SALE = "SALE"
    CONSIGNMENT = "CONSIGNMENT"
    REFINANCING = "REFINANCING"
    UNKNOWN = "UNKNOWN"


# Fields that must not be silently overwritten on conflict.
CRITICAL_FACT_KEYS = frozenset({"cpf", "birth_date", "birth", "plate", "cnpj"})


@dataclass(slots=True)
class HandoffSignals:
    explicit_handoff: bool | None = None
    explicit_offer: bool | None = None
    visit_intent: bool | None = None
    high_purchase_intent: bool | None = None
    sensitive_data_refusal: bool | None = None

    def as_dict(self) -> dict[str, bool | None]:
        return {
            "explicit_handoff": self.explicit_handoff,
            "explicit_offer": self.explicit_offer,
            "visit_intent": self.visit_intent,
            "high_purchase_intent": self.high_purchase_intent,
            "sensitive_data_refusal": self.sensitive_data_refusal,
        }


@dataclass(slots=True)
class TurnFacts:
    """LLM output for a single turn — facts only, never full state authority."""

    intent: BusinessIntent = BusinessIntent.UNKNOWN
    language: str | None = None
    facts: dict[str, Any] = field(default_factory=dict)
    signals: HandoffSignals = field(default_factory=HandoffSignals)
    confidence: dict[str, float] = field(default_factory=dict)
    # Field names the customer explicitly corrected this turn.
    explicit_corrections: list[str] = field(default_factory=list)
    # Typed conversational / budget updates (code owns transitions).
    budget_status: BudgetStatus | None = None
    pending_resolution: PendingResolution | None = None
    alternative_scope: AlternativeScope | None = None
    # Protocol: customer asked to send listing photos this turn.
    photo_request: bool | None = None
    # Protocol: customer asked for the store location this turn.
    location_request: bool | None = None


@dataclass(slots=True)
class CustomerState:
    phone: str = ""
    name: str | None = None
    name_confirmed: bool = False


@dataclass(slots=True)
class BusinessState:
    type: BusinessType = BusinessType.UNKNOWN
    actionability: Actionability = Actionability.INSUFFICIENT


@dataclass(slots=True)
class LifecycleState:
    status: LifecycleStatus = LifecycleStatus.BOT_ACTIVE
    handoff_reason: str | None = None


@dataclass(slots=True)
class ConversationCanonicalState:
    """Deterministic conversation state after merge (source of truth for decide)."""

    thread_id: str
    customer: CustomerState = field(default_factory=CustomerState)
    business: BusinessState = field(default_factory=BusinessState)
    lifecycle: LifecycleState = field(default_factory=LifecycleState)
    language: str = "unknown"
    intent: BusinessIntent = BusinessIntent.UNKNOWN
    facts: dict[str, Any] = field(default_factory=dict)
    signals: HandoffSignals = field(default_factory=HandoffSignals)
    pending_confirmation: list[str] = field(default_factory=list)
    temperature: LeadTemperature | None = None
    active_lead_ids: list[str] = field(default_factory=list)
    # Number of bot-generated outbound messages sent so far in this conversation.
    # Tracked deterministically in the orchestrator after each successful send.
    # Used to compute should_introduce = (assistant_turn_count == 0).
    assistant_turn_count: int = 0
    # Operational field — NOT a customer/business fact.
    # Hash of inventory search parameters from the last executed search.
    # Prevents redundant re-searches when search parameters have not changed.
    # Re-search occurs automatically when the hash changes (customer updates preference).
    last_inventory_search_key: str | None = None
    # Last semantic inventory outcome (SUCCESS_FOUND / SUCCESS_EMPTY only).
    # Used so SUCCESS_EMPTY does not immediately become irreversible handoff
    # before the customer can accept/reject alternatives.
    last_inventory_outcome: str | None = None
    # Conversational affordance awaiting customer resolution (code-owned).
    pending_interaction: PendingInteraction = PendingInteraction.NONE
    # How far the current search may deviate from original preference.
    alternative_scope: AlternativeScope = AlternativeScope.NONE
    # Budget qualification status (paired with facts.budget when PROVIDED).
    budget_status: BudgetStatus = BudgetStatus.UNKNOWN
    # Last published vehicles presented this thread (ids only).
    last_shown_vehicle_ids: list[str] = field(default_factory=list)
    # Explicit customer-chosen primary — never inferred from list position.
    primary_vehicle_id: str | None = None
    primary_vehicle_chosen_at: float | None = None
    presented_vehicle_bindings: list[Any] = field(default_factory=list)
    current_offer_set_id: str | None = None
    # Turn-scoped protocol flag — True only when this inbound asked for photos.
    photo_request: bool = False
    # Turn-scoped protocol flag — True only when this inbound asked for the store.
    location_request: bool = False
    # Field asked in the previous bot turn (for "sim/não" resolution).
    pending_question: str | None = None
    # Consecutive inbound turns with ≤3 words and no new facts extracted.
    engagement_low_streak: int = 0
    # Whether the visit invitation question has already been sent this thread.
    visit_invited: bool = False
    # Customer's expressed visit preference (e.g. "manhã", "às 10h").
    visit_preferred_time: str | None = None
    # Documents (CNH / holerite) already requested or received this thread.
    documents_asked: bool = False
    # Remaining financing components (income/residence) already requested once.
    remaining_documents_asked: bool = False
    # Optional asks after the lead became handoff_ready. Capped by policy.
    enrichment_ask_count: int = 0
    # Cadastral snapshots for vehicles presented this thread (id → record).
    presented_vehicle_catalog: dict[str, Any] = field(default_factory=dict)
    # Desired monthly installment already asked (nice-to-have; does not block).
    installment_asked: bool = False
    # Installment-vs-price mismatch already offered this thread.
    installment_mismatch_offered: bool = False
    # Internal capacity (down + installment * 60) when mismatch was offered.
    installment_capacity: float | None = None
    # Published cash price of the last presented vehicle (installment heuristic).
    last_shown_price_cash: float | None = None
    # Turn-scoped: inbound this turn was a successfully processed document.
    document_received: bool = False
    # Completeness vs handoff (refreshed deterministically each turn).
    handoff_ready: bool = False
    profile_complete: bool = False
    missing_fields: list[str] = field(default_factory=list)
    deferred_fields: list[str] = field(default_factory=list)
    collected_fields: list[str] = field(default_factory=list)
    # Visit slots offered this thread (exact labels from scheduling).
    offered_visit_slots: list[str] = field(default_factory=list)
    # Structured visit preference — never mixed into a single string.
    visit_interest: bool = False
    visit_declined: bool = False
    visit_date: str | None = None
    visit_period: str | None = None
    visit_time: str | None = None
    visit_raw: str | None = None
    visit_within_hours: bool | None = None
    visit_accepted_offered: bool = False
    location_sent: bool = False
    # Turn-scoped visit flags — reset on merge.
    visit_courtesy: bool = False
    visit_declined_this_turn: bool = False
    needs_visit_slot_offer: bool = False
    # Turn-scoped: inbound was thanks-only, no new commercial facts.
    courtesy_only: bool = False
    # Turn-scoped commercial questions from this inbound — never persist to Redis.
    unanswered_questions: list[dict[str, Any]] = field(default_factory=list)
    # Turn-scoped: visual resolution ran on this inbound (do not persist).
    visual_applied_this_turn: bool = False
    # Unequivocal listing identity from inbound (id / url / media metadata).
    listing_reference: str | None = None
    last_inventory_match: dict[str, Any] | None = None
    # Last visual vehicle resolution (sanitized dict — no bytes / base64).
    last_visual_resolution: dict[str, Any] | None = None
    # Compare-and-set for CRM sync — stale revisions must not overwrite newer.
    crm_revision: int = 0


@dataclass(slots=True)
class ResponseDirective:
    """Structured input to the Response Composer — what to say, not how.

    The Composer's job: how to say it naturally.
    The ResponseDirective's job: everything the Composer needs to know.
    """

    action: "Action"
    reason_code: str | None = None
    # Deterministic introduction eligibility — never rely on prompt alone.
    should_introduce: bool = False
    # Current inbound (Composer must answer this; never compose SMALLTALK blind).
    inbound_text: str = ""
    # Deterministic "what to say" — Composer only decides how to say it.
    response_objective: str = ""
    intent: BusinessIntent = BusinessIntent.UNKNOWN
    customer_name: str | None = None
    language: str = "pt-BR"
    next_question: str | None = None
    # Tool results keyed by tool name.
    tool_results: dict[str, Any] = field(default_factory=dict)
    # Relevant facts for context (subset — no sensitive fields).
    facts_context: dict[str, Any] = field(default_factory=dict)
    lifecycle_status: str = "BOT_ACTIVE"
    max_bubbles: int = 3
    # Absolute claim prohibitions for this turn.
    claims_forbidden: list[str] = field(default_factory=list)
    # Inventory truth contract — Composer must not invent stock status.
    inventory_outcome: InventoryOutcome = InventoryOutcome.NOT_EXECUTED
    claims_allowed: list[str] = field(default_factory=list)
    inventory_count: int = 0
    inventory_alternatives: list[dict[str, Any]] = field(default_factory=list)
    # Affordance the Composer is allowed to offer this turn (must have Decision path).
    conversational_affordance: PendingInteraction = PendingInteraction.NONE
    alternative_scope: AlternativeScope = AlternativeScope.NONE
    budget_status: BudgetStatus = BudgetStatus.UNKNOWN
    # Original preference still in state (Composer must not treat it as rigid
    # requirement once alternative_scope widens).
    original_desired_model: str | None = None
    # "FULL" = full intro (first turn, SMALLTALK intent); "BRIEF" = one-liner + pivot.
    intro_style: str = "FULL"
    # True when ≥2 consecutive turns had ≤3 words without new facts.
    engagement_low: bool = False
    # Content type of the current inbound (for document ack prefix in Composer).
    inbound_content_type: str = "TEXT"
    # Semantic ack the Composer must phrase warmly — never a canned "Anotei:".
    # deal_purchase | deal_trade | payment_financing | payment_cash | down_payment
    # | desired_installment | document_received
    ack_kind: str | None = None
    # Deterministic cadence — Composer must not choose the rhythm.
    cadence_mode: str | None = None
    # After SEND_LOCATION: location_close. Visit invite: warm_invite | hot_schedule.
    visit_cta_style: str | None = None
    # Extractor document_type when inbound is a document (CNH, …).
    document_kind: str | None = None
    # When True, Composer may include failure_code (sandbox only).
    expose_errors: bool = False
    # Media / tool failure code for sandbox recovery copy.
    failure_code: str | None = None
    # Semantic obligations for this turn (acts, questions, restrictions).
    dialogue_plan: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ActionPlan:
    action: Action
    handoff: bool = False
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    ask_field: str | None = None
    next_question: str | None = None
    reason_code: str | None = None
    reason: str | None = None
    primary_action: str | None = None
    supporting_acts: list[str] = field(default_factory=list)
    forbidden_concurrent_actions: list[str] = field(default_factory=list)
    qualification_trace: dict[str, Any] = field(default_factory=dict)


INTENT_TO_BUSINESS_TYPE: dict[BusinessIntent, BusinessType] = {
    BusinessIntent.PURCHASE: BusinessType.PURCHASE,
    BusinessIntent.PURCHASE_FINANCING: BusinessType.PURCHASE,
    BusinessIntent.TRADE: BusinessType.TRADE_IN,
    BusinessIntent.SALE: BusinessType.SALE,
    BusinessIntent.CONSIGNMENT: BusinessType.CONSIGNMENT,
    BusinessIntent.REFINANCING: BusinessType.REFINANCING,
    BusinessIntent.SMALLTALK: BusinessType.UNKNOWN,
    BusinessIntent.UNKNOWN: BusinessType.UNKNOWN,
}

# Higher = more specific / preferred when merging intents.
INTENT_SPECIFICITY: dict[BusinessIntent, int] = {
    BusinessIntent.UNKNOWN: 0,
    BusinessIntent.SMALLTALK: 1,
    BusinessIntent.PURCHASE: 2,
    BusinessIntent.PURCHASE_FINANCING: 3,
    BusinessIntent.TRADE: 3,
    BusinessIntent.SALE: 3,
    BusinessIntent.CONSIGNMENT: 3,
    BusinessIntent.REFINANCING: 3,
}
