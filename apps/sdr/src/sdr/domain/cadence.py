"""Deterministic response cadence — Composer phrases, Decision chooses the mode.

Modes are protocol, not product-term heuristics:
  engage_question   — first contact (greeting + one next step)
  recap_question    — commercial fact that the customer may correct
  confirm_question  — receipt ack + next roteiro question
  question_only     — operational field, no extra engagement
  indirect          — offer / visit without interrogation
"""

from __future__ import annotations

from enum import Enum

from sdr.domain.types import Action


class CadenceMode(str, Enum):
    ENGAGE_QUESTION = "engage_question"
    RECAP_QUESTION = "recap_question"
    CONFIRM_QUESTION = "confirm_question"
    QUESTION_ONLY = "question_only"
    INDIRECT = "indirect"


_ACK_TO_CADENCE: dict[str, CadenceMode] = {
    "deal_purchase": CadenceMode.RECAP_QUESTION,
    "deal_trade": CadenceMode.RECAP_QUESTION,
    "payment_financing": CadenceMode.CONFIRM_QUESTION,
    "payment_cash": CadenceMode.CONFIRM_QUESTION,
    "down_payment": CadenceMode.CONFIRM_QUESTION,
    "desired_installment": CadenceMode.CONFIRM_QUESTION,
    "difference_financing": CadenceMode.CONFIRM_QUESTION,
    "difference_cash": CadenceMode.CONFIRM_QUESTION,
    "document_received": CadenceMode.CONFIRM_QUESTION,
    "visit_preference": CadenceMode.CONFIRM_QUESTION,
}


def cadence_for(
    *,
    action: Action | str,
    should_introduce: bool,
    ack_kind: str | None,
    reason_code: str | None = None,
) -> CadenceMode:
    """Map turn context to a cadence mode. Never inferred from brand/model language."""
    action_val = action.value if isinstance(action, Action) else str(action or "")
    if should_introduce:
        return CadenceMode.ENGAGE_QUESTION
    if reason_code == "installment_tight":
        return CadenceMode.INDIRECT
    if action_val in (
        Action.REGISTER_VISIT_INTEREST.value,
        Action.SEND_LOCATION.value,
    ):
        return CadenceMode.INDIRECT
    if ack_kind and ack_kind in _ACK_TO_CADENCE:
        return _ACK_TO_CADENCE[ack_kind]
    if action_val == Action.ASK_INFO.value:
        return CadenceMode.QUESTION_ONLY
    return CadenceMode.QUESTION_ONLY
