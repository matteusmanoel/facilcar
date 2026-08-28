"""Protocol overlays — resolve the field the bot just asked.

This is PROTOCOL_DETERMINISTIC: the Decision Engine asked one field; a short
customer reply must fill that field. It is not a product-term heuristic.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from sdr.domain.facts_schema import normalize_facts, normalize_money_value
from sdr.domain.types import BusinessIntent, ConversationCanonicalState, TurnFacts

_CASH = re.compile(
    r"\b(?:[aà]\s*vista|avista|dinheiro|pix|cart[aã]o)\b",
    re.I,
)
_FINANCING = re.compile(
    r"\b(?:financ\w*|financiar|financiado|financiamento|parcelar|parcelado|presta[cç][oõ]es)\b",
    re.I,
)
_NO_DOWN = re.compile(
    r"(?:sem\s+entrada|financiar\s+(?:o\s+)?(?:carro\s+)?(?:todo|inteiro|tudo)|"
    r"valor\s+todo|100\s*%|nenhuma\s+entrada)",
    re.I,
)
_SHORT_YES = re.compile(
    r"^\s*(?:sim|pode|claro|ok|okay|vou|vamos|consigo|essa\s+semana|"
    r"ainda\s+essa\s+semana|pode\s+ser|fechado|combinado)\b",
    re.I,
)
_TRADE = re.compile(r"\b(?:troca|trocar|permuta)\b", re.I)
_PURCHASE = re.compile(r"\b(?:compra|comprar|comprando)\b", re.I)


def _norm(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")


def overlay_pending_question(
    facts: TurnFacts,
    state: ConversationCanonicalState,
    inbound_text: str,
) -> TurnFacts:
    """Fill the asked field from a short confirmation / mode answer.

    Never deletes known facts. Never invents a field we did not ask.
    """
    pending = state.pending_question
    text = _norm(inbound_text)
    extra: dict[str, Any] = {}

    # Answering "entrada" is not an inventory budget. Drop LLM/heuristic budget
    # extracted from the same utterance so search key does not change.
    if pending == "down_payment":
        facts.facts = {
            k: v for k, v in facts.facts.items() if k not in {"budget", "max_price"}
        }
        facts.budget_status = None

    if pending == "deal_type":
        if _TRADE.search(text) and _PURCHASE.search(text):
            extra["deal_type"] = "both"
        elif _TRADE.search(text):
            extra["deal_type"] = "trade"
        elif _PURCHASE.search(text):
            extra["deal_type"] = "purchase"
    elif pending == "payment_method":
        if _FINANCING.search(text):
            extra["payment_method"] = "financing"
        elif _CASH.search(text):
            extra["payment_method"] = "cash"
    elif pending == "down_payment":
        if _NO_DOWN.search(text) and "down_payment" not in facts.facts:
            extra["down_payment"] = 0
        elif "down_payment" not in facts.facts:
            money = normalize_money_value(text)
            if money is not None:
                extra["down_payment"] = money
    elif pending == "visit":
        # Protocol: we just invited a visit; a short confirmation is the answer.
        if _SHORT_YES.search(text) and len(text.split()) <= 8:
            facts.signals.visit_intent = True

    # Financing language records payment mode only when this utterance says so
    # and the field is not already canonical. Re-emitting known facts every turn
    # made the Composer ack "financiado" on unrelated inbound (documents, etc.).
    if _FINANCING.search(text) and not state.facts.get("payment_method"):
        extra.setdefault("payment_method", "financing")
        if facts.intent in (BusinessIntent.UNKNOWN, BusinessIntent.PURCHASE, BusinessIntent.SMALLTALK):
            facts.intent = BusinessIntent.PURCHASE_FINANCING

    if (
        facts.intent == BusinessIntent.PURCHASE_FINANCING
        and not state.facts.get("deal_type")
        and "deal_type" not in facts.facts
    ):
        extra.setdefault("deal_type", "purchase")

    if not extra:
        return facts

    canonical_extra, _rejected = normalize_facts(extra, source_text=inbound_text)
    facts.facts = {**facts.facts, **canonical_extra}
    return facts
