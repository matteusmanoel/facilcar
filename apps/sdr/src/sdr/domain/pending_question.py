"""Protocol overlays — resolve the field the bot just asked.

This is PROTOCOL_DETERMINISTIC: the Decision Engine asked one field; a short
customer reply must fill that field. It is not a product-term heuristic.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from sdr.domain.facts_schema import normalize_facts, normalize_money_value
from sdr.domain.pending_interaction import PendingResolution
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
    r"valor\s+todo|100\s*%|nenhuma\s+entrada|"
    r"financia(?:r)?\s+(?:em\s+)?100\s*%|financi(?:a|ar|ado)\s+100)",
    re.I,
)
_SHORT_YES = re.compile(
    r"^\s*(?:sim|pode|claro|ok|okay|vou|vamos|consigo|essa\s+semana|"
    r"ainda\s+essa\s+semana|pode\s+ser|fechado|combinado)\b",
    re.I,
)
_SHORT_NO = re.compile(
    r"^\s*(?:n[aã]o|agora\s+n[aã]o|dispenso|seguir(?:mos)?\s+com\s+esse)\b",
    re.I,
)
_VISIT_POSITIVE = re.compile(
    r"(?:seria\s+[oó]timo|[oó]timo|legal|quero\s+ir|topa|combinado|pode\s+ser|fechado)",
    re.I,
)
_VISIT_TIME = re.compile(
    r"\b(?:hoje|amanh[ãa]|essa\s+semana|segunda|ter[cç]a|quarta|quinta|sexta|s[áa]bado|domingo|"
    r"manh[ãa]|tarde|noite|\d{1,2}\s*h(?:oras)?|\d{1,2}:\d{2})\b"
    r"(?:\s+(?:ao?\s+)?(?:meio[\s-]dia|manh[ãa]|tarde|noite|\d{1,2}:\d{2}|\d{1,2}h))?",
    re.I,
)
_INSTALLMENT_SKIP = re.compile(
    r"\b(?:n[aã]o\s+sei|qualquer|tanto\s+faz|sem\s+prefer[eê]ncia)\b",
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

    # Answering "entrada" / parcela is not an inventory budget or engine.
    # Drop LLM leaks from the same utterance so search key does not change.
    _MONEY_LEAK_KEYS = (
        "budget",
        "max_price",
        "desired_engine_displacement_liters",
        "desired_engine_flexible",
        "desired_engine_any",
    )
    if pending in {"down_payment", "desired_installment"}:
        facts.facts = {
            k: v for k, v in facts.facts.items() if k not in _MONEY_LEAK_KEYS
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
            # "Financiado. Financia 100%?" → skip the entrada question next.
            if _NO_DOWN.search(text) and "down_payment" not in facts.facts:
                extra["down_payment"] = 0
        elif _CASH.search(text):
            extra["payment_method"] = "cash"
    elif pending == "down_payment":
        if _NO_DOWN.search(text) and "down_payment" not in facts.facts:
            extra["down_payment"] = 0
        elif "down_payment" not in facts.facts:
            money = normalize_money_value(text)
            if money is not None:
                extra["down_payment"] = money
    elif pending == "desired_installment":
        if _INSTALLMENT_SKIP.search(text):
            pass
        elif "desired_installment" not in facts.facts:
            money = normalize_money_value(text)
            if money is not None:
                extra["desired_installment"] = money
    elif pending == "visit":
        # Protocol: we just invited a visit. A concrete slot is confirmation;
        # a short yes without time still counts as visit_intent; a positive
        # without a slot stays on the visit question so Decision can ask when.
        time_m = _VISIT_TIME.search(text)
        if time_m:
            extra["timeline"] = time_m.group(0)
            facts.signals.visit_intent = True
        elif _SHORT_YES.search(text) and len(text.split()) <= 8:
            facts.signals.visit_intent = True
        elif _VISIT_POSITIVE.search(text) and len(text.split()) <= 12:
            pass
    elif pending == "alternatives_ok" and facts.pending_resolution is None:
        if _SHORT_YES.search(text) and len(text.split()) <= 10:
            facts.pending_resolution = PendingResolution.ACCEPT
        elif _SHORT_NO.search(text) and len(text.split()) <= 12:
            facts.pending_resolution = PendingResolution.REJECT

    # Financing language records payment mode only when this utterance says so
    # and the field is not already canonical. Re-emitting known facts every turn
    # made the Composer ack "financiado" on unrelated inbound (documents, etc.).
    if _FINANCING.search(text) and not state.facts.get("payment_method"):
        extra.setdefault("payment_method", "financing")
        if facts.intent in (BusinessIntent.UNKNOWN, BusinessIntent.PURCHASE, BusinessIntent.SMALLTALK):
            facts.intent = BusinessIntent.PURCHASE_FINANCING

    # Explicit "financia 100% / sem entrada" preference — independent of which
    # roteiro field was pending, as long as down_payment is still unknown.
    if (
        _NO_DOWN.search(text)
        and "down_payment" not in facts.facts
        and state.facts.get("down_payment") is None
        and (
            extra.get("payment_method") == "financing"
            or state.facts.get("payment_method") == "financing"
            or facts.intent == BusinessIntent.PURCHASE_FINANCING
            or _FINANCING.search(text)
        )
    ):
        extra.setdefault("down_payment", 0)

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
