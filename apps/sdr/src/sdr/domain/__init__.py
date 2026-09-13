"""Domain package exports."""

from sdr.domain.decision import decide
from sdr.domain.handoff import (
    HANDOFF_CONFIRMATION_PT_BR,
    confirmation_message,
    is_ai_silenced,
    mark_handoff_sent,
    mark_human_active,
)
from sdr.domain.merge import deterministic_merge
from sdr.domain.ownership import (
    OwnershipConflict,
    StaleOwnershipRevision,
    assume_human,
    automation_enabled,
    confirm_vendor_dispatch,
    handoff_sent,
    human_active,
    resume_ai,
    vendor_already_notified,
)
from sdr.domain.phone import normalize_phone, phone_from_jid
from sdr.domain.qualifications import is_seller_actionable, next_ask_field
from sdr.domain.types import (
    Action,
    ActionPlan,
    BusinessIntent,
    ConversationCanonicalState,
    HandoffSignals,
    LeadTemperature,
    LifecycleStatus,
    TurnFacts,
)

__all__ = [
    "Action",
    "ActionPlan",
    "BusinessIntent",
    "ConversationCanonicalState",
    "HANDOFF_CONFIRMATION_PT_BR",
    "HandoffSignals",
    "LeadTemperature",
    "LifecycleStatus",
    "OwnershipConflict",
    "StaleOwnershipRevision",
    "TurnFacts",
    "assume_human",
    "automation_enabled",
    "confirm_vendor_dispatch",
    "confirmation_message",
    "decide",
    "deterministic_merge",
    "handoff_sent",
    "human_active",
    "is_ai_silenced",
    "is_seller_actionable",
    "mark_handoff_sent",
    "mark_human_active",
    "next_ask_field",
    "normalize_phone",
    "phone_from_jid",
    "resume_ai",
    "vendor_already_notified",
]
