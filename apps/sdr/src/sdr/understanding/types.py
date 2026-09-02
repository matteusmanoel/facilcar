"""Prefer domain.types; fall back to temporary shims in ``_compat``.

``sdr.domain.types`` is the source of truth when SDR CORE publishes it.
"""

from __future__ import annotations

try:
    from sdr.domain.types import ActionPlan, ConversationState, TurnFacts
except ImportError:  # pragma: no cover - parallel Wave 1 until domain lands
    from sdr.understanding._compat import ActionPlan, ConversationState, TurnFacts

__all__ = ["ActionPlan", "ConversationState", "TurnFacts"]
