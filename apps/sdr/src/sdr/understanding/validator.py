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


def validate_bubbles(bubbles: list[str]) -> list[str]:
    """Return bubbles with prohibited promise phrasing softened."""
    cleaned: list[str] = []
    for bubble in bubbles:
        if not isinstance(bubble, str):
            continue
        text = bubble.strip()
        if not text:
            continue
        original = text
        for pattern, replacement in _PROMISE_PATTERNS:
            if pattern.search(text):
                text = pattern.sub(replacement, text)
        if text != original:
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
    return validate_bubbles(bubbles), result
