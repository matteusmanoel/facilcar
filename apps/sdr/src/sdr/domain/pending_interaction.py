"""Pending conversational affordances — Composer offers must have Decision continuations.

When the Composer asks whether the customer wants alternatives, the runtime MUST
record ``PendingInteraction.OFFER_ALTERNATIVES``. The next turn's Understanding
may interpret the customer's reply; code owns the state transition.

Resolution (from TurnFacts.pending_resolution):
  ACCEPT    — widen search scope; clear pending; re-run inventory
  REJECT    — clear pending; continue qualification without alternatives
  AMBIGUOUS — keep pending; ask a short clarification (no silent invent)
  None      — no pending context this turn

Never use open keyword lists of "sim/pode mandar" in Decision.
"""

from __future__ import annotations

from enum import Enum


class PendingInteraction(str, Enum):
    NONE = "NONE"
    OFFER_ALTERNATIVES = "OFFER_ALTERNATIVES"


class PendingResolution(str, Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    AMBIGUOUS = "AMBIGUOUS"


class AlternativeScope(str, Enum):
    """How far the current inventory search may deviate from original preference.

    NONE         — stick to stated preference (exact/resilient match)
    SIMILAR      — customer accepted similar alternatives
    ANY_VEHICLE  — customer explicitly widened to any vehicle / any car
    """

    NONE = "NONE"
    SIMILAR = "SIMILAR"
    ANY_VEHICLE = "ANY_VEHICLE"


def parse_pending_interaction(raw: object) -> PendingInteraction:
    if isinstance(raw, PendingInteraction):
        return raw
    text = str(raw or "NONE").strip().upper()
    try:
        return PendingInteraction(text)
    except ValueError:
        return PendingInteraction.NONE


def parse_pending_resolution(raw: object) -> PendingResolution | None:
    if raw is None:
        return None
    if isinstance(raw, PendingResolution):
        return raw
    text = str(raw).strip().upper()
    if not text:
        return None
    aliases = {
        "YES": PendingResolution.ACCEPT,
        "OK": PendingResolution.ACCEPT,
        "ACCEPT_ALTERNATIVES": PendingResolution.ACCEPT,
        "NO": PendingResolution.REJECT,
        "DECLINE": PendingResolution.REJECT,
        "UNCLEAR": PendingResolution.AMBIGUOUS,
    }
    if text in aliases:
        return aliases[text]
    try:
        return PendingResolution(text)
    except ValueError:
        return None


def parse_alternative_scope(raw: object) -> AlternativeScope | None:
    if raw is None:
        return None
    if isinstance(raw, AlternativeScope):
        return raw
    text = str(raw).strip().upper()
    if not text:
        return None
    aliases = {
        "ANY": AlternativeScope.ANY_VEHICLE,
        "ANY_CAR": AlternativeScope.ANY_VEHICLE,
        "BROAD": AlternativeScope.ANY_VEHICLE,
        "SIMILAR_OK": AlternativeScope.SIMILAR,
        "ALTERNATIVES": AlternativeScope.SIMILAR,
    }
    if text in aliases:
        return aliases[text]
    try:
        return AlternativeScope(text)
    except ValueError:
        return None
