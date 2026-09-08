"""Follow-up cancellation reasons and inbound/consent policy.

Pending automation must never outrun a later customer turn, HUMAN_ACTIVE,
opt-out, or conversation reset. Code owns cancel; the LLM does not.

Lead.status is never an ownership source. Only an unequivocal commercial
close (WON / LOST / SPAM) may cancel follow-up via an explicit close event.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Protocol

from sdr.domain.types import LifecycleStatus, TurnFacts


class FollowUpCancelReason(str, Enum):
    CUSTOMER_REPLIED = "CUSTOMER_REPLIED"
    HUMAN_ASSUMED = "HUMAN_ASSUMED"
    OPT_OUT = "OPT_OUT"
    CONVERSATION_RESET = "CONVERSATION_RESET"
    LEAD_WON = "LEAD_WON"
    LEAD_LOST = "LEAD_LOST"
    SPAM = "SPAM"
    SUPERSEDED = "SUPERSEDED"
    CONTEXT_CHANGED = "CONTEXT_CHANGED"
    VEHICLE_NO_LONGER_APPLICABLE = "VEHICLE_NO_LONGER_APPLICABLE"
    MAX_ATTEMPTS = "MAX_ATTEMPTS"
    MANUAL_CANCEL = "MANUAL_CANCEL"


class FollowUpTaskStatus(str, Enum):
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    SENT = "SENT"
    CANCELLED = "CANCELLED"


# Terminal for cancel: SENT is never moved back to PENDING.
CANCELLABLE_STATUSES = frozenset(
    {FollowUpTaskStatus.PENDING, FollowUpTaskStatus.CLAIMED}
)

_UNEQUIVOCAL_LEAD_CLOSE: dict[str, FollowUpCancelReason] = {
    "WON": FollowUpCancelReason.LEAD_WON,
    "LOST": FollowUpCancelReason.LEAD_LOST,
    "SPAM": FollowUpCancelReason.SPAM,
}

# Consent / LGPD stop-contact — PROTOCOL_DETERMINISTIC, not commercial language.
_OPT_OUT_PHRASES = (
    "pare de me enviar",
    "parar de me enviar",
    "pare de me mandar",
    "não quero mais contato",
    "nao quero mais contato",
    "não me envie mais",
    "nao me envie mais",
    "não me mande mais",
    "nao me mande mais",
    "remova meu número",
    "remova meu numero",
    "não quero mais mensagens",
    "nao quero mais mensagens",
    "não quero mais receber",
    "nao quero mais receber",
    "parar de receber",
    "opt out",
    "opt-out",
    "descadastre",
    "descadastrar",
)


class FollowUpCanceller(Protocol):
    """Minimal cancel contract. Frente B's store implements this."""

    async def cancel_for_conversation(self, conversation_id: str, reason: str) -> int:
        """Cancel PENDING/CLAIMED tasks. Idempotent. SENT is left SENT.

        Returns the number of tasks newly moved to CANCELLED.
        """
        ...


def normalize_cancel_reason(reason: str | FollowUpCancelReason) -> str:
    if isinstance(reason, FollowUpCancelReason):
        return reason.value
    return str(reason or FollowUpCancelReason.MANUAL_CANCEL.value)


def cancel_reason_for_lead_close(status: str | None) -> FollowUpCancelReason | None:
    """Map an explicit commercial close event — not a poll of Lead.status.

    QUALIFIED / CONTACTED / NEW / IN_PROGRESS are not close events.
    """
    if not status:
        return None
    return _UNEQUIVOCAL_LEAD_CLOSE.get(str(status).strip().upper())


def is_opt_out_text(text: str | None) -> bool:
    if not text:
        return False
    folded = " ".join(str(text).strip().casefold().split())
    if not folded:
        return False
    return any(phrase in folded for phrase in _OPT_OUT_PHRASES)


def is_opt_out_signal(
    text: str | None,
    turn_facts: TurnFacts | None = None,
) -> bool:
    """True when inbound text policy or TurnFacts carry an opt-out."""
    if is_opt_out_text(text):
        return True
    if turn_facts is None:
        return False
    facts = turn_facts.facts or {}
    if facts.get("opt_out") is True:
        return True
    signals = turn_facts.signals
    if getattr(signals, "opt_out", None) is True:
        return True
    return False


def inbound_cancel_reason(
    text: str | None,
    *,
    context_changed: bool = False,
) -> FollowUpCancelReason:
    """Reason used when cancelling pending follow-up before understand."""
    if is_opt_out_text(text):
        return FollowUpCancelReason.OPT_OUT
    if context_changed:
        return FollowUpCancelReason.CONTEXT_CHANGED
    return FollowUpCancelReason.CUSTOMER_REPLIED


def followup_send_blocked(
    *,
    task_status: str | FollowUpTaskStatus | None,
    bot_status: str | None,
) -> bool:
    """HUMAN_ACTIVE / cancel win the race against send. SENT is not re-sent."""
    status = (
        task_status.value
        if isinstance(task_status, FollowUpTaskStatus)
        else str(task_status or "")
    )
    if status == FollowUpTaskStatus.CANCELLED.value:
        return True
    if status == FollowUpTaskStatus.SENT.value:
        return True
    if bot_status == LifecycleStatus.HUMAN_ACTIVE.value:
        return True
    return False


def task_status_value(status: Any) -> str:
    if isinstance(status, FollowUpTaskStatus):
        return status.value
    if hasattr(status, "value"):
        return str(status.value)
    return str(status or "")
