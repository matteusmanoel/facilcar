"""Typed budget status — value presence alone is not enough.

UNKNOWN   — never asked / not answered; may ask when needed for next step
PROVIDED  — numeric budget in facts; use it as a filter when searching
UNDEFINED — customer said they have no defined band; do not re-ask immediately
DECLINED  — customer prefers not to share; respect and do not insist
FLEXIBLE  — customer authorized search without a price filter

Explicit later information may upgrade status and value.
Never invent a monetary amount from status alone.
"""

from __future__ import annotations

from enum import Enum


class BudgetStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    PROVIDED = "PROVIDED"
    UNDEFINED = "UNDEFINED"
    DECLINED = "DECLINED"
    FLEXIBLE = "FLEXIBLE"


# Statuses that mean "budget question is resolved for now" — do not re-ask.
BUDGET_RESOLVED: frozenset[BudgetStatus] = frozenset(
    {
        BudgetStatus.PROVIDED,
        BudgetStatus.UNDEFINED,
        BudgetStatus.DECLINED,
        BudgetStatus.FLEXIBLE,
    }
)

# Statuses that authorize inventory without a price filter.
BUDGET_NO_PRICE_FILTER: frozenset[BudgetStatus] = frozenset(
    {
        BudgetStatus.UNKNOWN,  # may still search by preference alone
        BudgetStatus.UNDEFINED,
        BudgetStatus.DECLINED,
        BudgetStatus.FLEXIBLE,
    }
)


def parse_budget_status(raw: object) -> BudgetStatus | None:
    if raw is None:
        return None
    if isinstance(raw, BudgetStatus):
        return raw
    text = str(raw).strip().upper()
    if not text:
        return None
    try:
        return BudgetStatus(text)
    except ValueError:
        aliases = {
            "UNSET": BudgetStatus.UNKNOWN,
            "NONE": BudgetStatus.UNKNOWN,
            "OPEN": BudgetStatus.FLEXIBLE,
            "NO_BUDGET": BudgetStatus.UNDEFINED,
            "NOT_DEFINED": BudgetStatus.UNDEFINED,
            "REFUSED": BudgetStatus.DECLINED,
        }
        return aliases.get(text)
