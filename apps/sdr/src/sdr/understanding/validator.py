"""Response validation — promise language + inventory truth + affordance policy."""

from __future__ import annotations

import logging
import re
from typing import Any

from sdr.domain.inventory_outcome import (
    contains_absence_claim,
    contains_policy_claim,
    inventory_fallback_bubbles,
)
from sdr.domain.introduction import (
    continuation_smalltalk_bubbles,
    is_first_contact_reopen,
    strip_greeting_opener,
)
from sdr.domain.pending_interaction import PendingInteraction
from sdr.domain.types import InventoryOutcome

logger = logging.getLogger(__name__)

_PROMISE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"\b(?:taxa|interes[eé]s?)\s*(?:de\s*)?\d+(?:[.,]\d+)?\s*%",
            re.I,
        ),
        "as condições de taxa dependem da análise da financeira",
    ),
    (
        re.compile(r"\b\d+(?:[.,]\d+)?\s*%\s*(?:ao\s*m[eê]s|a\.?m\.?|am)\b", re.I),
        "as condições de taxa dependem da análise da financeira",
    ),
    (
        re.compile(
            r"\b(?:aprovado|aprovada|garanti(?:do|da)|aprova(?:mos|ção)\s+garantida)\b",
            re.I,
        ),
        "sujeito à análise de crédito",
    ),
    (
        re.compile(r"\b100\s*%\s*financiado\b", re.I),
        "financiamento sem entrada pode ser possível, sujeito à análise",
    ),
    (
        re.compile(r"\bparcela\s*(?:de\s*)?R\$\s*[\d.]+(?:,\d+)?\b", re.I),
        "o valor da parcela depende da análise da financeira",
    ),
]

# CTAs that require a matching conversational_affordance / Decision continuation.
_UNAUTHORIZED_AFFORDANCE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"quer\s+que\s+eu\s+(?:veja|te\s+mostre|mostre)\s+alternativ",
            re.I,
        ),
        "offer_alternatives_without_affordance",
    ),
    (
        re.compile(
            r"\b(?:posso\s+te\s+avisar|te\s+aviso)\s+quando\s+(?:chegar|tiver)\b",
            re.I,
        ),
        "notify_when_available_without_affordance",
    ),
    (
        re.compile(r"\bquer\s+agendar\b", re.I),
        "schedule_without_affordance",
    ),
]

_RIGID_ORIGINAL_MODEL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"que\s+legal\s+que\s+voc[eê]\s+quer\s+(?:um|uma)\s+\w+", re.I),
    re.compile(r"or[cç]amento\s+que\s+voc[eê]\s+est[aá]\s+pensando\s+para\s+o\s+\w+", re.I),
]


_BUDGET_ASK_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bor[cç]amento\b", re.I),
    re.compile(r"valor m[aá]ximo\s+voc[eê]\s+pensa\s+em\s+investir", re.I),
    re.compile(r"qual(?:\s+é)?\s+o\s+seu\s+or[cç]amento", re.I),
    re.compile(r"quanto\s+voc[eê]\s+(?:quer|pensa|pode)\s+investir", re.I),
    re.compile(r"or[cç]amento\s+para\s+o\s+", re.I),
]

# Questions the Decision Engine never plans — Composer must not invent them.
_OFF_ROTEIRO_ASK_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bcons[oó]rcio\b", re.I),
    re.compile(r"uso\s+pessoal\s+ou\s+(?:para\s+)?empresa", re.I),
    re.compile(r"para\s+uso\s+pessoal\s+ou", re.I),
]

_PAYMENT_BOTH_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r",?\s*ou os dois\??", re.I),
    re.compile(r",?\s*o los dos\??", re.I),
]

_ROBOTIC_ACK_LINE = re.compile(
    r"^\s*(?:anotei\b.*|anoté\b.*|"
    r"beleza,\s*então é compra\.?|"
    r"perfecto,\s*entonces es (?:compra|permuta)\.?)\s*$",
    re.I,
)
_DEAL_TYPE_FALLBACK_PT = "Seria compra ou troca?"
_DEAL_TYPE_FALLBACK_ES = "¿Sería compra o permuta?"


def validate_bubbles(bubbles: list[str], *, language: str = "pt-BR") -> list[str]:
    """Return bubbles with prohibited promise/budget-ask phrasing rewritten."""
    cleaned: list[str] = []
    deal_fallback = (
        _DEAL_TYPE_FALLBACK_ES if str(language).lower().startswith("es") else _DEAL_TYPE_FALLBACK_PT
    )
    for bubble in bubbles:
        if not isinstance(bubble, str):
            continue
        text = bubble.strip()
        if not text:
            continue
        original = text
        if _ROBOTIC_ACK_LINE.match(text):
            continue
        for pattern, replacement in _PROMISE_PATTERNS:
            if pattern.search(text):
                text = pattern.sub(replacement, text)
        for pattern in _PAYMENT_BOTH_PATTERNS:
            text = pattern.sub("", text).rstrip(" ,")
        if not text:
            continue
        if any(pattern.search(text) for pattern in _BUDGET_ASK_PATTERNS):
            logger.warning("validate_bubbles: stripped budget solicitation: %r", original)
            text = deal_fallback
        if any(pattern.search(text) for pattern in _OFF_ROTEIRO_ASK_PATTERNS):
            logger.warning("validate_bubbles: stripped off-roteiro question: %r", original)
            continue
        if text != original and text != deal_fallback:
            logger.warning(
                "validate_bubbles: softened promise language: %r -> %r",
                original,
                text,
            )
        cleaned.append(text)
    return cleaned[:3]


def _parse_affordance(raw: Any) -> PendingInteraction:
    if isinstance(raw, PendingInteraction):
        return raw
    try:
        return PendingInteraction(str(raw or "NONE"))
    except ValueError:
        return PendingInteraction.NONE


def validate_inventory_policy(
    bubbles: list[str],
    *,
    inventory_outcome: InventoryOutcome | str | None,
    language: str = "pt-BR",
    conversational_affordance: PendingInteraction | str | None = None,
    alternative_scope: str | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """Enforce inventory truth + conversational affordance on composed bubbles.

    Returns ``(bubbles_or_fallback, validation_result)``.
    On policy violation, replaces with deterministic safe fallback.
    """
    if inventory_outcome is None:
        outcome = InventoryOutcome.NOT_EXECUTED
    elif isinstance(inventory_outcome, InventoryOutcome):
        outcome = inventory_outcome
    else:
        try:
            outcome = InventoryOutcome(str(inventory_outcome))
        except ValueError:
            outcome = InventoryOutcome.NOT_EXECUTED

    affordance = _parse_affordance(conversational_affordance)
    joined = " ".join(b for b in bubbles if isinstance(b, str))
    result: dict[str, Any] = {
        "outcome": outcome.value,
        "pass": True,
        "violations": [],
        "affordance": affordance.value,
    }

    if outcome in (
        InventoryOutcome.FAILED_RETRYABLE,
        InventoryOutcome.FAILED_TERMINAL,
        InventoryOutcome.NOT_EXECUTED,
    ):
        if contains_absence_claim(joined):
            result["pass"] = False
            result["violations"].append("absence_claim_on_failure")
        if contains_policy_claim(joined):
            result["pass"] = False
            result["violations"].append("policy_claim_on_failure")

    if outcome == InventoryOutcome.SUCCESS_EMPTY:
        if contains_policy_claim(joined):
            result["pass"] = False
            result["violations"].append("permanent_policy_claim_on_empty")

    # Composer must not invent CTAs the Decision Engine cannot consume.
    if affordance != PendingInteraction.OFFER_ALTERNATIVES:
        for pattern, code in _UNAUTHORIZED_AFFORDANCE_PATTERNS:
            if pattern.search(joined):
                # alternatives CTA specifically
                if code == "offer_alternatives_without_affordance":
                    result["pass"] = False
                    result["violations"].append(code)
                elif code in (
                    "notify_when_available_without_affordance",
                    "schedule_without_affordance",
                ):
                    result["pass"] = False
                    result["violations"].append(code)

    scope = (alternative_scope or "").upper()
    if scope in {"ANY_VEHICLE", "SIMILAR"}:
        for pattern in _RIGID_ORIGINAL_MODEL_PATTERNS:
            if pattern.search(joined):
                result["pass"] = False
                result["violations"].append("rigid_original_model_after_scope_widen")
                break

    if not result["pass"]:
        logger.warning(
            "validate_inventory_policy: rejected bubbles for outcome=%s violations=%s text=%r",
            outcome.value,
            result["violations"],
            joined[:200],
        )
        # Affordance-aware empty fallback: only ask alternatives when authorized.
        if (
            outcome == InventoryOutcome.SUCCESS_EMPTY
            and affordance == PendingInteraction.OFFER_ALTERNATIVES
        ):
            fallback = inventory_fallback_bubbles(outcome, language=language)
        elif outcome == InventoryOutcome.SUCCESS_EMPTY:
            es = language.lower().startswith("es")
            fallback = [
                "No encontré una opción con ese perfil en el stock actual."
                if es
                else "Não encontrei uma opção com esse perfil no estoque atual."
            ]
        else:
            fallback = inventory_fallback_bubbles(outcome, language=language)
        result["fallback_used"] = True
        return fallback, result

    result["fallback_used"] = False
    return validate_bubbles(bubbles, language=language), result


def validate_introduction_policy(
    bubbles: list[str],
    *,
    should_introduce: bool,
    action: str = "",
    language: str = "pt-BR",
) -> tuple[list[str], dict[str, Any]]:
    """Reject first-contact reopenings when the assistant has already spoken.

    Continuation turns must not open as a new greeting. This is protocol
    (conversation phase), not a product-term heuristic.
    """
    result: dict[str, Any] = {
        "pass": True,
        "violations": [],
        "fallback_used": False,
    }
    if should_introduce or not is_first_contact_reopen(bubbles):
        return bubbles, result

    result["pass"] = False
    result["violations"].append("first_contact_reopen")
    result["fallback_used"] = True
    logger.warning(
        "validate_introduction_policy: first-contact reopen action=%s text=%r",
        action,
        " ".join(bubbles)[:200],
    )
    if action == "smalltalk":
        return continuation_smalltalk_bubbles(language), result

    stripped: list[str] = []
    for i, bubble in enumerate(bubbles):
        text = bubble.strip() if isinstance(bubble, str) else ""
        if not text:
            continue
        if i == 0:
            text = strip_greeting_opener(text)
        if text and not is_first_contact_reopen([text]):
            stripped.append(text)
    if stripped:
        return stripped, result
    return continuation_smalltalk_bubbles(language), result
